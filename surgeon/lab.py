"""Source-pinned public SQL on synthetic microfixtures; no benchmark-scale claim."""
import hashlib
import json
from .config import ROOT

LAB_CONTEXT = """Additional synthetic microfixture tables:
part(p_partkey integer primary key, p_brand char(10) not null, p_container char(10) not null);
lineitem(l_orderkey integer primary key, l_partkey integer not null references part(p_partkey),
 l_quantity numeric(15,2) not null, l_extendedprice numeric(15,2) not null);
Indexes: lineitem(l_partkey).
emp(empno integer primary key, ename varchar not null, job varchar not null, mgr integer nullable,
 hiredate date not null, sal integer not null, comm integer not null, deptno integer not null, slacker boolean not null);
dept(deptno integer primary key, name varchar not null).
Indexes: emp(deptno), emp(job).
This is synthetic microfixture data, not official TPC-H/Calcite scale data."""
EXTRA_TABLES = ("part", "lineitem", "emp", "dept")


def lab_cases():
    directory = ROOT / "benchmarks" / "sources" / "rbot"
    provenance = json.loads((directory / "provenance.json").read_text())
    for item in provenance["files"]:
        path = ROOT / item["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Pinned source hash mismatch: " + item["local_path"])
    own = [
        {"id": "month_range", "family": "sargability",
         "sql": "SELECT id, amount FROM orders WHERE date_trunc('month', created_at) = TIMESTAMP '2026-03-01'",
         "mock_sql": "SELECT id, amount FROM orders WHERE created_at >= TIMESTAMP '2026-03-01' AND created_at < TIMESTAMP '2026-04-01'"},
        {"id": "distinct_customer", "family": "semijoin",
         "sql": "SELECT DISTINCT c.id FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.amount > 50",
         "mock_sql": "SELECT c.id FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > 50)"},
        {"id": "count_nonnull", "family": "null_semantics",
         "sql": "SELECT c.id, (SELECT count(amount) FROM orders o WHERE o.customer_id = c.id) AS n FROM customers c WHERE c.id <= 50",
         "mock_sql": "SELECT c.id, count(o.amount) AS n FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE c.id <= 50 GROUP BY c.id"},
        {"id": "repeated_sum", "family": "aggregation",
         "sql": "SELECT c.id, (SELECT sum(o.amount) FROM orders o WHERE o.customer_id = c.id) AS total, (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) AS n FROM customers c WHERE c.id <= 100",
         "mock_sql": "SELECT c.id, sum(o.amount) AS total, count(o.id) AS n FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE c.id <= 100 GROUP BY c.id"},
        {"id": "already_indexed", "family": "abstention",
         "sql": "SELECT id, amount FROM orders WHERE customer_id = 42",
         "mock_sql": "SELECT id, amount FROM orders WHERE customer_id = 42"},
    ]
    for case in own:
        case.update(source="own_synthetic", template_id=case["id"])
    public = []
    for variant in (0, 1):
        sql = "\n".join(line for line in (directory / ("tpch_q17_" + str(variant) + ".sql")).read_text().splitlines()
                        if not line.lstrip().startswith("--"))
        public.append({"id": "tpch_q17_" + str(variant), "family": "correlated_aggregate",
                       "sql": sql, "mock_sql": sql, "template_id": "tpch_q17",
                       "source": "R-Bot / TPC-H query input; synthetic microfixtures",
                       "source_commit": provenance["files"][variant]["commit"]})
    selected = {
        "testEmptyFilterProjectUnion": ("calcite_union", "set_semantics"),
        "testEmptyMinus": ("calcite_empty_minus", "set_semantics"),
        "testWhereNotInCorrelated": ("calcite_not_in", "null_semantics"),
        "testDecorrelateTwoExists": ("calcite_exists", "correlation"),
    }
    for line in (directory / "calcite.jsonl").read_text().splitlines():
        record = json.loads(line)
        names = {rewrite["name"] for rewrite in record["rewrites"]}
        for name in names.intersection(selected):
            case_id, family = selected[name]
            public.append({"id": case_id, "family": family, "sql": record["input_sql"],
                           "mock_sql": record["input_sql"], "template_id": name,
                           "source": "R-Bot / Calcite input; synthetic microfixtures",
                           "source_commit": provenance["files"][2]["commit"]})
    if len(public) != 6:
        raise ValueError("Expected six source-pinned public SQL inputs.")
    for case in own + public:
        case["schema_context"] = LAB_CONTEXT
        case["result_contract"] = "unordered_row_bag_with_type_check"
    return own + public


def suite_cases(name):
    from .workload import CASES
    if name == "pilot":
        return CASES
    if name == "lab":
        return lab_cases()
    if name == "all":
        return CASES + lab_cases()
    raise ValueError("Unknown suite.")


def seed_lab_sql(schemas):
    sql = ""
    for schema in schemas:
        size = 50000 if schema == "bench" else 0 if schema == "check_empty" else 350
        employees = 10000 if schema == "bench" else 0 if schema == "check_empty" else 150
        sql += f"""
CREATE TABLE IF NOT EXISTS {schema}.part(
 p_partkey integer PRIMARY KEY, p_brand char(10) NOT NULL, p_container char(10) NOT NULL);
CREATE TABLE IF NOT EXISTS {schema}.lineitem(
 l_orderkey integer PRIMARY KEY, l_partkey integer NOT NULL REFERENCES {schema}.part(p_partkey),
 l_quantity numeric(15,2) NOT NULL, l_extendedprice numeric(15,2) NOT NULL);
CREATE TABLE IF NOT EXISTS {schema}.dept(deptno integer PRIMARY KEY, name varchar NOT NULL);
CREATE TABLE IF NOT EXISTS {schema}.emp(
 empno integer PRIMARY KEY, ename varchar NOT NULL, job varchar NOT NULL, mgr integer,
 hiredate date NOT NULL, sal integer NOT NULL, comm integer NOT NULL, deptno integer NOT NULL,
 slacker boolean NOT NULL);
INSERT INTO {schema}.part
 SELECT i, CASE WHEN i % 2 = 0 THEN 'Brand#23' ELSE 'Brand#25' END,
 CASE WHEN i % 2 = 0 THEN 'WRAP BAG' ELSE 'WRAP PACK' END
 FROM generate_series(1,200) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.lineitem SELECT i, (i % 200) + 1,
 1 + (i % 47), ((i * 37) % 10000)::numeric / 10
 FROM generate_series(1,{size}) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.dept SELECT i, CASE i % 4 WHEN 0 THEN 'ENGINEER' WHEN 1 THEN 'ANALYST' WHEN 2 THEN 'SALES' ELSE 'MANAGER' END
 FROM generate_series(0,11) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.emp SELECT i, 'Employee ' || i,
 CASE i % 4 WHEN 0 THEN 'ENGINEER' WHEN 1 THEN 'ANALYST' WHEN 2 THEN 'SALES' ELSE 'MANAGER' END,
 CASE WHEN i % 7 = 0 THEN NULL ELSE 1 END, DATE '2020-01-01' + (i % 1000),
 CASE WHEN i % 9 = 0 THEN 34 ELSE (i * 13) % 1000 END, (i % 11) * 10, i % 12, i % 2 = 0
 FROM generate_series(1,{employees}) i ON CONFLICT DO NOTHING;
CREATE INDEX IF NOT EXISTS lineitem_part ON {schema}.lineitem(l_partkey);
CREATE INDEX IF NOT EXISTS emp_dept ON {schema}.emp(deptno);
CREATE INDEX IF NOT EXISTS emp_job ON {schema}.emp(job);
GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO surgeon_reader;
ANALYZE {schema}.part;
ANALYZE {schema}.lineitem;
ANALYZE {schema}.emp;
ANALYZE {schema}.dept;
"""
    return sql
