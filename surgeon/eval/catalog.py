"""Catalog-aware context: the facts a correct rewrite depends on.

Declared nullability, keys, foreign keys and indexes decide whether NOT IN may
become NOT EXISTS, whether a join can be dropped, or whether DISTINCT is
redundant. Row counts and per-column distinct estimates come from the bench
schema's statistics. Constraints hold on every fixture; statistics describe only
the bench data, and the prompt says so.

Optional join-graph block lists FK edges as typed relations so the model can
follow multi-hop joins without inventing join keys (SchemaGraphSQL-style).
"""

import json

from ..database import Database

TABLES = ("customers", "orders", "part", "lineitem", "emp", "dept")
_cache = {}


def catalog_text(db=None, join_graph=True):
    cache_key = "text_jg" if join_graph else "text"
    if cache_key in _cache:
        return _cache[cache_key]
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
    if join_graph:
        text += "\n\n" + join_graph_text(db)
    _cache[cache_key] = text
    return text


def join_graph_text(db=None):
    """FK join graph: edges the rewriter may follow (no invented join keys)."""
    if "join_graph" in _cache:
        return _cache["join_graph"]
    db = db or Database()
    names = ",".join("'" + t + "'" for t in TABLES)
    edges = json.loads(db.execute(
        "SELECT coalesce(json_agg(json_build_object("
        "  'src', regexp_replace(c.conrelid::regclass::text, '^bench\\.', ''), "
        "  'dst', regexp_replace(c.confrelid::regclass::text, '^bench\\.', ''), "
        "  'src_cols', (SELECT json_agg(a.attname ORDER BY u.ord) FROM unnest(c.conkey) WITH ORDINALITY AS u(attnum, ord) "
        "               JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = u.attnum), "
        "  'dst_cols', (SELECT json_agg(a.attname ORDER BY u.ord) FROM unnest(c.confkey) WITH ORDINALITY AS u(attnum, ord) "
        "               JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = u.attnum)"
        ") ORDER BY c.conrelid::regclass::text), '[]'::json) "
        "FROM pg_constraint c "
        "JOIN pg_class rel ON rel.oid = c.conrelid "
        "JOIN pg_namespace n ON n.oid = rel.relnamespace "
        f"WHERE n.nspname = 'bench' AND c.contype = 'f' AND rel.relname IN ({names})"
    ) or "[]") or []
    # Also encode emp→dept if present as a soft relation via known column names.
    soft = []
    if any(t == "emp" for t in TABLES) and any(t == "dept" for t in TABLES):
        soft.append("emp.dept_id → dept.id (logical department membership)")
    lines = ["Join graph (use only these edges; do not invent join predicates):"]
    for e in edges:
        src_cols = ", ".join(e.get("src_cols") or [])
        dst_cols = ", ".join(e.get("dst_cols") or [])
        lines.append(f"  {e['src']}.({src_cols}) → {e['dst']}.({dst_cols})")
    for s in soft:
        lines.append(f"  {s}")
    if len(lines) == 1:
        lines.append("  (no foreign keys declared)")
    text = "\n".join(lines)
    _cache["join_graph"] = text
    return text

