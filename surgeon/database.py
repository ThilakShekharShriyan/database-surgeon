import json
import csv
import io
import os
import re
import statistics
import subprocess
from collections import Counter
from decimal import Decimal

from .workload import EVAL_SCHEMAS, FIXTURE_SCHEMAS


def validate_sql(sql):
    """Conservative single-query guard; database permissions remain the boundary."""
    sql = sql.strip()
    # Mask quoted strings/identifiers and comments before checking SQL keywords.
    token = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*.*?\*/", re.S)
    def mask(match):
        value = match.group()
        if value.startswith('"'):
            # Quoting a function name must not bypass the disallowed-function check.
            return value[1:-1].replace('""', '"')
        if value.startswith("/*") and "/*" in value[2:]:
            raise ValueError("Nested block comments are unsupported.")
        return " " * len(value)
    masked = token.sub(mask, sql)
    if sql.endswith(";") and masked.endswith(";"):
        sql, masked = sql[:-1], masked[:-1]
    # Describing a result uses psql input; reject backslashes even inside literals
    # to keep SQL escaping differences from turning input into a psql command.
    if ";" in masked or "$" in masked or "\\" in sql:
        raise ValueError("Only one SELECT statement is permitted; no dollar quoting or psql commands.")
    if not re.match(r"\s*(SELECT|WITH)\b", masked, re.I):
        raise ValueError("Only SELECT or read-only WITH is allowed.")
    blocked = r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|COPY|CALL|DO|SET|RESET|GRANT|REVOKE|INTO|FOR|LOCK)\b"
    if re.search(blocked, masked, re.I) or re.search(r"\b(pg_\w+|dblink\w*|lo_\w+|set_config|nextval|setval)\s*\(", masked, re.I):
        raise ValueError("Candidate contains a disallowed operation or function.")
    return sql


class Database:
    def __init__(self, timeout_ms=5000):
        self.timeout_ms = timeout_ms

    def _env(self, schema):
        env = dict(os.environ)
        env.update({"PGHOST": os.getenv("PGHOST", "127.0.0.1"),
                    "PGPORT": os.getenv("PGPORT", "55432"),
                    "PGDATABASE": os.getenv("PGDATABASE", "surgeon"),
                    "PGUSER": os.getenv("PGUSER", "surgeon_reader"),
                    "PGPASSWORD": os.getenv("PGPASSWORD", "local-benchmark-only"),
                    "PGCONNECT_TIMEOUT": "3"})
        env["PGOPTIONS"] = (f"-c default_transaction_read_only=on -c statement_timeout={self.timeout_ms} "
                            f"-c search_path={schema},pg_catalog")
        return env

    def execute(self, sql, schema="bench", describe=False):
        if schema not in EVAL_SCHEMAS:
            raise ValueError("Unknown fixture schema.")
        env = self._env(schema)
        command = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"]
        if describe:
            # gdesc parses the query without executing it, including on empty results.
            command += ["--csv", "-f", "-"]
        else:
            command += ["-A", "-t", "-c", sql]
        result = subprocess.run(command, input=sql + "\n\\gdesc\n" if describe else None,
                                env=env, capture_output=True, text=True, timeout=self.timeout_ms / 1000 + 8)
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[:1500])
        return result.stdout.strip()

    def rows(self, sql, schema="bench"):
        sql = validate_sql(sql)
        return json.loads(self.execute(
            f"SELECT coalesce(json_agg(row_to_json(ds_result)), '[]'::json) FROM ({sql}\n) AS ds_result", schema),
            object_pairs_hook=unique_columns, parse_float=Decimal)

    def rows_many(self, sql, schemas):
        """Result rows on several schemas through one psql session (one process)."""
        sql = validate_sql(sql)
        for schema in schemas:
            if schema not in EVAL_SCHEMAS:
                raise ValueError("Unknown fixture schema.")
        script = "".join(
            f"SET search_path = {schema}, pg_catalog;\n"
            f"SELECT coalesce(json_agg(row_to_json(ds_result)), '[]'::json) FROM ({sql}\n) AS ds_result;\n"
            for schema in schemas)
        env = self._env(schemas[0])
        result = subprocess.run(["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-f", "-"],
                                input=script, env=env, capture_output=True, text=True,
                                timeout=len(schemas) * self.timeout_ms / 1000 + 8)
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[:1500])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if len(lines) != len(schemas):
            raise RuntimeError("Unexpected psql output while reading results.")
        return {schema: json.loads(line, object_pairs_hook=unique_columns, parse_float=Decimal)
                for schema, line in zip(schemas, lines)}

    def columns(self, sql):
        description = list(csv.reader(io.StringIO(self.execute(validate_sql(sql), describe=True))))
        names = [row[0] for row in description[1:]]
        if not names:
            raise ValueError("Could not determine result columns.")
        if len(names) != len(set(names)):
            raise ValueError("Duplicate result column names are unsupported.")
        return names

    def preflight(self, schemas=FIXTURE_SCHEMAS):
        """Identify the actual fixtures and verify the model's restricted connection."""
        role = self.execute("SELECT current_user")
        if role != "surgeon_reader":
            raise ValueError("Evaluation requires the surgeon_reader database role.")
        elevated = self.execute("SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication "
                                "OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        if elevated != "f":
            raise ValueError("surgeon_reader must not have elevated database privileges.")
        fixtures = {}
        for schema in schemas:
            fixtures[schema] = {}
            from .lab import EXTRA_TABLES
            tables = ["customers", "orders"]
            for extra in EXTRA_TABLES:
                if self.execute(f"SELECT to_regclass('{schema}.{extra}') IS NOT NULL") == "t":
                    tables.append(extra)
            for table in tables:
                fixtures[schema][table] = json.loads(self.execute(
                    "SELECT json_build_object('rows', count(*), 'md5', "
                    "md5(coalesce(string_agg(row_to_json(t)::text, E'\\n' ORDER BY row_to_json(t)::text), ''))) "
                    f"FROM {table} t", schema))
        indexes = json.loads(self.execute(
            "SELECT coalesce(json_agg(i ORDER BY schemaname, indexname), '[]'::json) FROM "
            "(SELECT schemaname, indexname, indexdef FROM pg_indexes WHERE schemaname IN ("
            + ",".join("'" + schema + "'" for schema in schemas) + ")) i"))
        settings = json.loads(self.execute(
            "SELECT json_build_object(" + ",".join(
                f"'{name}', current_setting('{name}')" for name in (
                    "work_mem", "shared_buffers", "effective_cache_size", "random_page_cost",
                    "max_parallel_workers_per_gather", "jit", "TimeZone"))
            + ", 'lc_collate', (SELECT datcollate FROM pg_database WHERE datname = current_database()))"))
        return {"role": role, "version": self.execute("SHOW server_version"), "fixtures": fixtures,
                "indexes": indexes, "settings": settings}

    def plan(self, sql, analyze=False):
        sql = validate_sql(sql)
        flags = "ANALYZE, BUFFERS, TIMING OFF, " if analyze else ""
        return json.loads(self.execute(f"EXPLAIN ({flags}FORMAT JSON) {sql}"))[0]

    def check(self, original, candidate, schemas=FIXTURE_SCHEMAS, expected_cache=None, ordered=False):
        """Compare results on every schema; a failure carries a small counterexample.
        ordered=True is only sound when the original's ORDER BY ends in a unique
        key, because tied rows may legally come back in any order."""
        # Empty bags still have a schema; aliases must not disappear from evaluation.
        if self.columns(original) != self.columns(candidate):
            return {"equivalent": False, "reason": "Result column names or order differ."}
        if getattr(self, "enforce_types", False):
            def signature(sql):
                return list(csv.reader(io.StringIO(self.execute(validate_sql(sql), describe=True))))[1:]
            if signature(original) != signature(candidate):
                return {"equivalent": False, "reason": "Result output types differ."}
        ordered = ordered and has_top_level_order(original)
        missing = [s for s in schemas if expected_cache is None or (original, s) not in expected_cache]
        fresh = self.rows_many(original, missing) if missing else {}
        if expected_cache is not None:
            expected_cache.update({(original, s): rows for s, rows in fresh.items()})
        observed = self.rows_many(candidate, list(schemas))
        for schema in schemas:
            expected = fresh[schema] if schema in fresh else expected_cache[(original, schema)]
            actual = observed[schema]
            if not equivalent(expected, actual, ordered):
                return {"equivalent": False, "reason": "Result mismatch on an evaluation instance.",
                        "schema": schema, "expected_rows": len(expected), "actual_rows": len(actual),
                        "counterexample": counterexample(expected, actual)}
        scope = "ordered rows" if ordered else "unordered row multisets"
        return {"equivalent": True, "scope": f"{len(schemas)} instances; {scope}"}

    def plans_analyzed(self, sqls, schema="bench"):
        """EXPLAIN ANALYZE several queries, in order, in one session (one process)."""
        sqls = [validate_sql(sql) for sql in sqls]
        marker = "--ds-plan-boundary--"
        script = "".join(f"EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON) {sql};\n\\echo {marker}\n"
                         for sql in sqls)
        result = subprocess.run(["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-f", "-"],
                                input=script, env=self._env(schema), capture_output=True, text=True,
                                timeout=len(sqls) * self.timeout_ms / 1000 + 8)
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[:1500])
        chunks = [c for c in result.stdout.split(marker)][:len(sqls)]
        if len(chunks) != len(sqls):
            raise RuntimeError("Unexpected psql output while timing.")
        return [json.loads(chunk)[0] for chunk in chunks]

    def benchmark(self, original, candidate, repeats=5):
        if repeats < 3:
            raise ValueError("At least three paired timing trials are required.")
        # One warm-up each, then pairs whose order alternates so neither query
        # always benefits from running second.
        sequence = [("original", original), ("candidate", candidate)]
        for i in range(repeats):
            pair = [("original", original), ("candidate", candidate)]
            sequence += pair[::-1] if i % 2 else pair
        plans = self.plans_analyzed([sql for _, sql in sequence])
        timings = {"original": [], "candidate": []}
        buffers = {}
        for (name, _), plan in list(zip(sequence, plans))[2:]:
            timings[name].append(plan["Execution Time"])
            buffers[name] = {k: v for k, v in plan["Plan"].items() if "Blocks" in k}
        before, after = (statistics.median(timings[n]) for n in ("original", "candidate"))
        reductions = [1 - after / before if before else 0
                      for before, after in zip(timings["original"], timings["candidate"])]
        return {"original_ms": before, "candidate_ms": after,
                "speedup": before / after if after else None,
                "reduction": 1 - after / before if before else 0,
                "samples_ms": timings, "paired_reductions": reductions,
                "candidate_win_rate": sum(r > 0 for r in reductions) / repeats,
                "original_mad_ms": statistics.median(abs(t - before) for t in timings["original"]),
                "candidate_mad_ms": statistics.median(abs(t - after) for t in timings["candidate"]),
                "last_buffers": buffers}


def freeze(value):
    if isinstance(value, dict):
        return ("object", tuple(sorted((k, freeze(v)) for k, v in value.items())))
    if isinstance(value, list):
        return ("array", tuple(freeze(v) for v in value))
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float, Decimal)):
        return ("number", Decimal(str(value)))
    return ("string", value)


def equivalent(expected, actual, ordered=False):
    # Preserve duplicates and NULLs. SQL without a top-level ORDER BY is a bag.
    if ordered:
        return [freeze(r) for r in expected] == [freeze(r) for r in actual]
    encode = lambda rows: Counter(freeze(r) for r in rows)
    return encode(expected) == encode(actual)


def counterexample(expected, actual, limit=3):
    want, got = Counter(freeze(r) for r in expected), Counter(freeze(r) for r in actual)
    by_key = {freeze(r): r for r in list(expected) + list(actual)}
    missing = [by_key[k] for k in (want - got)][:limit]
    extra = [by_key[k] for k in (got - want)][:limit]
    if not missing and not extra:
        return {"note": "Same rows in a different order."}
    return {"missing_rows": missing, "unexpected_rows": extra}


def has_top_level_order(sql):
    """True when ORDER BY appears outside every parenthesis (the outer query)."""
    masked = re.sub(r"'(?:''|[^'])*'", "''", sql)
    depth, top = 0, []
    for ch in masked:
        depth += ch == "("
        depth -= ch == ")"
        top.append(ch if depth == 0 else " ")
    return re.search(r"\bORDER\s+BY\b", "".join(top), re.I) is not None


def unique_columns(pairs):
    # PostgreSQL JSON permits duplicate object keys; Python would silently drop
    # one and could accept a candidate with an extra same-named output column.
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate result column names are unsupported.")
        result[key] = value
    return result
