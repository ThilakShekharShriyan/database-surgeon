"""Catalog-aware context: the facts a correct rewrite depends on.

Declared nullability, keys, foreign keys and indexes decide whether NOT IN may
become NOT EXISTS, whether a join can be dropped, or whether DISTINCT is
redundant. Row counts and per-column distinct estimates come from the bench
schema's statistics. Constraints hold on every fixture; statistics describe only
the bench data, and the prompt says so.
"""

import json

from ..database import Database

TABLES = ("customers", "orders", "part", "lineitem", "emp", "dept")
_cache = {}


def catalog_text(db=None):
    if "text" in _cache:
        return _cache["text"]
    db = db or Database()
    names = ",".join("'" + t + "'" for t in TABLES)
    columns = json.loads(db.execute(
        "SELECT json_agg(json_build_object('t', table_name, 'c', column_name, 'type', data_type, "
        "'null', is_nullable = 'YES') ORDER BY table_name, ordinal_position) "
        f"FROM information_schema.columns WHERE table_schema = 'bench' AND table_name IN ({names})"))
    constraints = json.loads(db.execute(
        "SELECT json_agg(json_build_object('t', rel.relname, 'def', pg_get_constraintdef(con.oid)) "
        "ORDER BY rel.relname, con.conname) FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid "
        f"JOIN pg_namespace n ON n.oid = rel.relnamespace WHERE n.nspname = 'bench' AND rel.relname IN ({names})"))
    indexes = json.loads(db.execute(
        "SELECT json_agg(json_build_object('t', tablename, 'def', regexp_replace(indexdef, '^.* USING ', ''))) "
        f"FROM pg_indexes WHERE schemaname = 'bench' AND tablename IN ({names})"))
    stats = json.loads(db.execute(
        "SELECT json_agg(json_build_object('t', c.relname, 'rows', c.reltuples::bigint)) FROM pg_class c "
        f"JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'bench' AND c.relname IN ({names})"))
    distinct = json.loads(db.execute(
        "SELECT json_agg(json_build_object('t', tablename, 'c', attname, 'nd', n_distinct, 'nf', null_frac)) "
        f"FROM pg_stats WHERE schemaname = 'bench' AND tablename IN ({names})") or "[]") or []
    rows = {s["t"]: s["rows"] for s in stats}
    lines = []
    for table in TABLES:
        cols = [f"{c['c']} {c['type']}{'' if c['null'] else ' NOT NULL'}" for c in columns if c["t"] == table]
        lines.append(f"{table} (~{rows.get(table, '?')} rows on the timing fixture): " + ", ".join(cols))
        for con in constraints:
            if con["t"] == table:
                lines.append("  constraint " + con["def"])
        for index in indexes:
            if index["t"] == table:
                lines.append("  index " + index["def"])
        for d in distinct:
            if d["t"] == table and (d["nf"] or 0) > 0:
                lines.append(f"  {d['c']}: about {round(d['nf'] * 100)}% NULL on the timing fixture")
    text = ("Catalog (constraints hold on every evaluation database; row counts and NULL rates describe "
            "only the timing fixture, other databases differ):\n" + "\n".join(lines) +
            "\nA nullable column may contain NULL on any database. NOT IN over a nullable column is not an anti-join.")
    _cache["text"] = text
    return text
