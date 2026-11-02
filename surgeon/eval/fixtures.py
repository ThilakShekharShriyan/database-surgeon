"""Null/skew evaluator fixtures (part of the full EVAL_SCHEMAS contract).

Harness verify and the judge both check these schemas together with the five
development fixtures, so a null-edge semantic bug cannot be returned as an
accept. Values are derived from md5 of the row number (deterministic seed).
"""

HIDDEN_SCHEMAS = ("check_nulls", "check_rand1", "check_rand2")

# Per-schema shape: (customers, orders, null customer 1-in-k, null amount 1-in-k,
# customer key range, lineitem rows, emp rows, dept modulus, midnight 1-in-k, salt)
SHAPES = {
    "check_nulls": (300, 2000, 3, 4, 300, 600, 400, 12, 5, "n"),
    "check_rand1": (500, 3000, 11, 13, 500, 900, 600, 12, 7, "r1"),
    "check_rand2": (200, 1500, 29, 31, 50, 500, 300, 6, 3, "r2"),
}


def hidden_seed_sql():
    sql = ""
    for schema, (customers, orders, null_c, null_a, key_range, lines, emps, dept_mod, midnight, salt) in SHAPES.items():
        h = lambda expr, tag: f"(('x' || substr(md5(({expr})::text || ':{salt}:{tag}'), 1, 7))::bit(28)::int)"
        sql += f"""
CREATE SCHEMA IF NOT EXISTS {schema};
CREATE TABLE IF NOT EXISTS {schema}.customers(id integer PRIMARY KEY, name text);
CREATE TABLE IF NOT EXISTS {schema}.orders(
 id integer PRIMARY KEY, customer_id integer REFERENCES {schema}.customers(id),
 amount numeric(12,2), created_at timestamp NOT NULL);
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
INSERT INTO {schema}.customers
 SELECT i, 'Customer ' || ({h('i', 'name')} % 40) FROM generate_series(1,{customers}) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.orders
 SELECT i,
  CASE WHEN {h('i', 'cn')} % {null_c} = 0 THEN NULL ELSE {h('i', 'c')} % {key_range} + 1 END,
  CASE WHEN {h('i', 'an')} % {null_a} = 0 THEN NULL ELSE ({h('i', 'a')} % 12000)::numeric / 100 END,
  TIMESTAMP '2025-12-20' + ({h('i', 'd')} % 400) * INTERVAL '1 day'
   + CASE WHEN {h('i', 'm')} % {midnight} = 0 THEN INTERVAL '0' ELSE ({h('i', 's')} % 86400) * INTERVAL '1 second' END
 FROM generate_series(1,{orders}) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.orders
 SELECT {orders} + i, o.customer_id, o.amount, o.created_at
 FROM generate_series(1,{orders // 10}) i JOIN {schema}.orders o ON o.id = i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.part
 SELECT i, (ARRAY['Brand#23','Brand#25','Brand#12','Brand#31','Brand#44'])[{h('i', 'b')} % 5 + 1],
  (ARRAY['WRAP BAG','WRAP PACK','SM CASE','LG BOX'])[{h('i', 'k')} % 4 + 1]
 FROM generate_series(1,100) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.lineitem
 SELECT i, {h('i', 'p')} % 100 + 1, 1 + {h('i', 'q')} % 50, ({h('i', 'e')} % 100000)::numeric / 10
 FROM generate_series(1,{lines}) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.dept
 SELECT i, (ARRAY['ENGINEER','ANALYST','SALES','MANAGER'])[i % 4 + 1] FROM generate_series(0,{dept_mod - 1}) i ON CONFLICT DO NOTHING;
INSERT INTO {schema}.emp
 SELECT i, 'Employee ' || ({h('i', 'en')} % 90),
  (ARRAY['ENGINEER','ANALYST','SALES','MANAGER'])[{h('i', 'j')} % 4 + 1],
  CASE WHEN {h('i', 'mg')} % 5 = 0 THEN NULL ELSE {h('i', 'mv')} % 20 + 1 END,
  DATE '2020-01-01' + {h('i', 'hd')} % 1500, ({h('i', 'sl')} % 40) * 25, ({h('i', 'cm')} % 6) * 10,
  {h('i', 'dp')} % {dept_mod + 2}, {h('i', 'sk')} % 2 = 0
 FROM generate_series(1,{emps}) i ON CONFLICT DO NOTHING;
CREATE INDEX IF NOT EXISTS orders_created ON {schema}.orders(created_at);
CREATE INDEX IF NOT EXISTS orders_customer ON {schema}.orders(customer_id);
CREATE INDEX IF NOT EXISTS lineitem_part ON {schema}.lineitem(l_partkey);
CREATE INDEX IF NOT EXISTS emp_dept ON {schema}.emp(deptno);
CREATE INDEX IF NOT EXISTS emp_job ON {schema}.emp(job);
GRANT USAGE ON SCHEMA {schema} TO surgeon_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO surgeon_reader;
ANALYZE {schema}.customers; ANALYZE {schema}.orders; ANALYZE {schema}.part;
ANALYZE {schema}.lineitem; ANALYZE {schema}.dept; ANALYZE {schema}.emp;
"""
    return sql
