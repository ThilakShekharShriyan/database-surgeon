"""Development fixtures, not an untouched final evaluation set."""

from .eval.fixtures import HIDDEN_SCHEMAS, hidden_seed_sql

FIXTURE_SCHEMAS = ("bench", "check_a", "check_b", "check_nonnull", "check_empty")
# Full equivalence contract: development + null/skew schemas. Harness verify and
# the judge share EVAL_SCHEMAS so accepted returns cannot become incorrect.
EVAL_SCHEMAS = FIXTURE_SCHEMAS + HIDDEN_SCHEMAS

SCHEMA = """customers(id integer primary key, name text);
orders(id integer primary key, customer_id integer nullable references customers(id),
       amount numeric(12,2) nullable, created_at timestamp not null);
Indexes: orders(created_at), orders(customer_id)."""

CASES = [
    {
        "id": "date_filter",
        "family": "sargability",
        "sql": "SELECT id, amount FROM orders WHERE to_char(created_at, 'YYYY-MM-DD') = '2026-03-15'",
        "mock_sql": "SELECT id, amount FROM orders WHERE created_at >= TIMESTAMP '2026-03-15' AND created_at < TIMESTAMP '2026-03-16'",
    },
    {
        "id": "correlated_count",
        "family": "aggregation",
        "sql": "SELECT c.id, (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) AS n FROM customers c WHERE c.id <= 100",
        "mock_sql": "SELECT c.id, count(o.id) AS n FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE c.id <= 100 GROUP BY c.id",
    },
    {
        "id": "nullable_antijoin",
        "family": "null_semantics",
        "sql": "SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)",
        # Deliberately unsafe when the subquery contains NULL. The mock tests rejection.
        "mock_sql": "SELECT c.id FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)",
    },
]

SEED_SQL = """
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'surgeon_reader') THEN
  CREATE ROLE surgeon_reader LOGIN PASSWORD 'local-benchmark-only'
   NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE surgeon FROM PUBLIC;
ALTER ROLE surgeon_reader SET default_transaction_read_only = on;
"""


def seed_sql():
    sql = SEED_SQL
    for schema, size in (("bench", 50000), ("check_a", 200), ("check_b", 350),
                         ("check_nonnull", 350), ("check_empty", 0)):
        customer_id = "(i % 200) + 1" if schema == "check_nonnull" else "CASE WHEN i % 17 = 0 THEN NULL ELSE (i % 200) + 1 END"
        sql += f"""
CREATE SCHEMA IF NOT EXISTS {schema};
CREATE TABLE IF NOT EXISTS {schema}.customers(id integer PRIMARY KEY, name text);
CREATE TABLE IF NOT EXISTS {schema}.orders(
 id integer PRIMARY KEY, customer_id integer REFERENCES {schema}.customers(id),
 amount numeric(12,2), created_at timestamp NOT NULL);
INSERT INTO {schema}.customers SELECT i, 'Customer ' || i FROM generate_series(1,1000) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.orders
 SELECT i, {customer_id},
 CASE WHEN i % 19 = 0 THEN NULL ELSE (i % 10000)::numeric / 100 END,
 TIMESTAMP '2026-01-01' + (i % 365) * INTERVAL '1 day' + (i % 86400) * INTERVAL '1 second'
 FROM generate_series(1,{size}) i ON CONFLICT DO NOTHING;
CREATE INDEX IF NOT EXISTS orders_created ON {schema}.orders(created_at);
CREATE INDEX IF NOT EXISTS orders_customer ON {schema}.orders(customer_id);
GRANT USAGE ON SCHEMA {schema} TO surgeon_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO surgeon_reader;
ANALYZE {schema}.customers;
ANALYZE {schema}.orders;
"""
    # Unmatched customers, duplicate join keys, NULLs, and exact day boundaries.
    for schema in ("check_a", "check_b"):
        sql += f"""
INSERT INTO {schema}.orders VALUES
 (-1, NULL, NULL, '2026-03-15 00:00:00'),
 (-2, 1, 10, '2026-03-15 23:59:59.999999'),
 (-3, 1, 10, '2026-03-16 00:00:00'),
 (-4, 2, 0, '2026-03-14 23:59:59.999999') ON CONFLICT DO NOTHING;
"""
    from .lab import seed_lab_sql
    return sql + seed_lab_sql(FIXTURE_SCHEMAS) + hidden_seed_sql()
