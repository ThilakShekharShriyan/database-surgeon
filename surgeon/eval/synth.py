"""Seeded SQL rewrite templates over the development tables.

Each template is a slow-but-correct query shape that appears in real workloads,
a correctness trap (the obvious rewrite changes results), or a decoy (already
optimal; the right answer is to return it unchanged). A template may carry a
reference rewrite written by hand. References are only used to measure headroom
when the case set is built; no system ever sees them.

Families mirror the rewrite classes in R-Bot (VLDB 2025) and LLM-R2 (VLDB 2024):
predicate sargability, subquery decorrelation, NULL-aware anti-joins, semijoins,
disjunctions, redundant operators and aggregate pushdown.
"""

import random

DAY = "TIMESTAMP '{d}'"
NEXT_DAY = "TIMESTAMP '{d}' + INTERVAL '1 day'"


def _day(rng):
    return f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def _month(rng):
    return rng.randint(1, 11)


def _params(rng):
    month = _month(rng)
    return {
        "d": _day(rng),
        "m": month,
        "m_start": f"2026-{month:02d}-01",
        "m_next": f"2026-{month + 1:02d}-01",
        "c": rng.randint(1, 200),
        "c2": rng.randint(1, 200),
        "c3": rng.randint(1, 200),
        "k": rng.randint(2, 9),
        "x": rng.choice([25, 50, 75, 90, 95, 99]),
        "lo": rng.choice([1, 2, 5]),
        "hi": rng.choice([90, 95, 98]),
        "n": rng.choice([20, 50, 100, 200]),
        "job": rng.choice(["ENGINEER", "ANALYST", "SALES", "MANAGER"]),
        "s": rng.choice([100, 250, 500, 800]),
        "brand": rng.choice(["Brand#23", "Brand#25"]),
        "days": rng.choice([2, 3, 7]),
    }


# (id, family, kind, sql, reference or None, ordered)
# kind: "rewrite" (a faster equivalent probably exists), "trap" (the obvious
# rewrite is wrong; a careful one may exist), "decoy" (already optimal).
TEMPLATES = [
    # --- sargability: functions on indexed columns hide the index.
    ("sarg_to_char_day", "sargability", "rewrite",
     "SELECT id, amount FROM orders WHERE to_char(created_at, 'YYYY-MM-DD') = '{d}'",
     f"SELECT id, amount FROM orders WHERE created_at >= {DAY} AND created_at < {NEXT_DAY}", False),
    ("sarg_cast_date", "sargability", "rewrite",
     "SELECT id, customer_id FROM orders WHERE created_at::date = DATE '{d}'",
     f"SELECT id, customer_id FROM orders WHERE created_at >= {DAY} AND created_at < {NEXT_DAY}", False),
    ("sarg_trunc_month", "sargability", "rewrite",
     "SELECT id, amount FROM orders WHERE date_trunc('month', created_at) = TIMESTAMP '{m_start}'",
     "SELECT id, amount FROM orders WHERE created_at >= TIMESTAMP '{m_start}' AND created_at < TIMESTAMP '{m_next}'", False),
    ("sarg_extract_month", "sargability", "rewrite",
     "SELECT count(*) AS n FROM orders WHERE EXTRACT(YEAR FROM created_at) = 2026 AND EXTRACT(MONTH FROM created_at) = {m}",
     "SELECT count(*) AS n FROM orders WHERE created_at >= TIMESTAMP '{m_start}' AND created_at < TIMESTAMP '{m_next}'", False),
    ("sarg_arith_key", "sargability", "rewrite",
     "SELECT id, amount FROM orders WHERE customer_id - {k} = {c} - {k}",
     "SELECT id, amount FROM orders WHERE customer_id = {c}", False),
    ("sarg_coalesce_key", "sargability", "rewrite",
     "SELECT id, created_at FROM orders WHERE coalesce(customer_id, -1) = {c}",
     "SELECT id, created_at FROM orders WHERE customer_id = {c}", False),
    ("sarg_to_char_range", "sargability", "rewrite",
     "SELECT id FROM orders WHERE to_char(created_at, 'YYYY-MM-DD') BETWEEN '{d}' AND to_char(DATE '{d}' + {days}, 'YYYY-MM-DD')",
     f"SELECT id FROM orders WHERE created_at >= {DAY} AND created_at < TIMESTAMP '{{d}}' + INTERVAL '{{days}} days' + INTERVAL '1 day'", False),

    # --- correlated subqueries.
    ("corr_count_per_customer", "correlation", "rewrite",
     "SELECT c.id, (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) AS n FROM customers c WHERE c.id <= {n}",
     None, False),
    ("corr_avg_salary_dept", "correlation", "rewrite",
     "SELECT e.empno, e.ename FROM emp e WHERE e.job = '{job}' AND e.sal > (SELECT avg(e2.sal) FROM emp e2 WHERE e2.deptno = e.deptno)",
     "SELECT e.empno, e.ename FROM emp e JOIN (SELECT deptno, avg(sal) AS a FROM emp GROUP BY deptno) d ON d.deptno = e.deptno WHERE e.job = '{job}' AND e.sal > d.a", False),
    ("corr_max_threshold", "correlation", "rewrite",
     "SELECT c.id, c.name FROM customers c WHERE (SELECT max(o.amount) FROM orders o WHERE o.customer_id = c.id) > {x}",
     "SELECT c.id, c.name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > {x})", False),
    ("corr_repeated_scalar", "correlation", "rewrite",
     "SELECT c.id, (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) AS n, (SELECT sum(o.amount) FROM orders o WHERE o.customer_id = c.id) AS total FROM customers c WHERE c.id <= {n}",
     "SELECT c.id, count(o.id) AS n, sum(o.amount) AS total FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE c.id <= {n} GROUP BY c.id", False),
    ("corr_q17_small_quantity", "correlation", "rewrite",
     "SELECT sum(l.l_extendedprice) / 7.0 AS avg_yearly FROM lineitem l JOIN part p ON p.p_partkey = l.l_partkey WHERE p.p_brand = '{brand}' AND l.l_quantity < (SELECT 0.2 * avg(l2.l_quantity) FROM lineitem l2 WHERE l2.l_partkey = p.p_partkey)",
     "SELECT sum(l.l_extendedprice) / 7.0 AS avg_yearly FROM lineitem l JOIN part p ON p.p_partkey = l.l_partkey JOIN (SELECT l_partkey, 0.2 * avg(l_quantity) AS lim FROM lineitem GROUP BY l_partkey) a ON a.l_partkey = l.l_partkey WHERE p.p_brand = '{brand}' AND l.l_quantity < a.lim", False),

    # --- NULL semantics: NOT IN over a nullable column is not an anti-join.
    ("null_notin_nullable", "null_semantics", "trap",
     "SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM orders WHERE amount > {x})",
     "SELECT c.id FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.amount > {x} AND (o.customer_id = c.id OR o.customer_id IS NULL))", False),
    ("null_notin_filtered", "null_semantics", "rewrite",
     "SELECT id, name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders WHERE customer_id IS NOT NULL AND created_at >= TIMESTAMP '{d}')",
     "SELECT c.id, c.name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.created_at >= TIMESTAMP '{d}')", False),
    ("null_notin_notnull_col", "null_semantics", "rewrite",
     "SELECT d.deptno, d.name FROM dept d WHERE d.deptno NOT IN (SELECT e.deptno FROM emp e WHERE e.sal > {s})",
     "SELECT d.deptno, d.name FROM dept d WHERE NOT EXISTS (SELECT 1 FROM emp e WHERE e.deptno = d.deptno AND e.sal > {s})", False),
    ("null_notin_mgr", "null_semantics", "trap",
     "SELECT e.empno FROM emp e WHERE e.job = '{job}' AND e.empno NOT IN (SELECT m.mgr FROM emp m)",
     None, False),

    # --- semijoins: DISTINCT over a join is usually an EXISTS.
    ("semi_distinct_join", "semijoin", "rewrite",
     "SELECT DISTINCT c.id, c.name FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.amount > {x}",
     "SELECT c.id, c.name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > {x})", False),
    ("semi_count_distinct", "semijoin", "rewrite",
     "SELECT count(DISTINCT c.id) AS n FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.created_at >= TIMESTAMP '{d}'",
     "SELECT count(*) AS n FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.created_at >= TIMESTAMP '{d}')", False),
    ("semi_distinct_nullable", "semijoin", "trap",
     "SELECT DISTINCT customer_id FROM orders WHERE amount > {x}",
     None, False),
    ("semi_in_distinct", "semijoin", "decoy",
     "SELECT id, name FROM customers WHERE id IN (SELECT DISTINCT customer_id FROM orders WHERE amount > {x})",
     None, False),

    # --- disjunctions.
    ("or_same_column", "disjunction", "decoy",
     "SELECT id FROM orders WHERE customer_id = {c} OR customer_id = {c2} OR customer_id = {c3}",
     None, False),
    ("or_two_indexes", "disjunction", "rewrite",
     f"SELECT id, amount FROM orders WHERE customer_id = {{c}} OR (created_at >= {DAY} AND created_at < {NEXT_DAY})",
     None, False),

    # --- redundant operators.
    ("red_self_join_pk", "redundancy", "rewrite",
     "SELECT o.id, o.amount FROM orders o JOIN orders o2 ON o2.id = o.id WHERE o.customer_id = {c}",
     "SELECT o.id, o.amount FROM orders o WHERE o.customer_id = {c}", False),
    ("red_sorted_subquery", "redundancy", "rewrite",
     "SELECT count(*) AS n FROM (SELECT * FROM orders ORDER BY created_at DESC) t WHERE t.amount > {x}",
     "SELECT count(*) AS n FROM orders WHERE amount > {x}", False),
    ("red_distinct_pk", "redundancy", "rewrite",
     "SELECT DISTINCT id, amount FROM orders WHERE created_at >= TIMESTAMP '{d}' - INTERVAL '30 days'",
     "SELECT id, amount FROM orders WHERE created_at >= TIMESTAMP '{d}' - INTERVAL '30 days'", False),
    ("red_union_disjoint", "redundancy", "rewrite",
     "SELECT id FROM orders WHERE amount > {hi} UNION SELECT id FROM orders WHERE amount < {lo}",
     "SELECT id FROM orders WHERE amount > {hi} UNION ALL SELECT id FROM orders WHERE amount < {lo}", False),
    ("red_having_key", "redundancy", "decoy",
     "SELECT customer_id, count(*) AS n FROM orders GROUP BY customer_id HAVING customer_id <= {n}",
     None, False),

    # --- aggregation.
    ("agg_fk_join_count", "aggregation", "trap",
     "SELECT count(*) AS n FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.amount > {x}",
     "SELECT count(*) AS n FROM orders o WHERE o.customer_id IS NOT NULL AND o.amount > {x}", False),
    ("agg_count_column", "aggregation", "decoy",
     "SELECT count(amount) AS n FROM orders WHERE customer_id = {c}",
     None, False),
    ("agg_group_then_filter", "aggregation", "rewrite",
     "SELECT t.customer_id, t.total FROM (SELECT customer_id, sum(amount) AS total FROM orders GROUP BY customer_id) t WHERE t.customer_id = {c}",
     "SELECT customer_id, sum(amount) AS total FROM orders WHERE customer_id = {c} GROUP BY customer_id", False),
    ("agg_left_join_condition", "aggregation", "trap",
     "SELECT c.id, count(o.id) AS n FROM customers c LEFT JOIN orders o ON o.customer_id = c.id AND o.amount > {x} WHERE c.id <= {n} GROUP BY c.id",
     None, False),

    # --- abstention: already index-friendly; the right answer is no change.
    ("dec_pk_lookup", "abstention", "decoy",
     "SELECT name FROM customers WHERE id = {c}", None, False),
    ("dec_day_range", "abstention", "decoy",
     f"SELECT id, amount FROM orders WHERE created_at >= {DAY} AND created_at < {NEXT_DAY}", None, False),
    ("dec_fk_lookup", "abstention", "decoy",
     "SELECT id, amount FROM orders WHERE customer_id = {c}", None, False),
    ("dec_top_n", "abstention", "decoy",
     "SELECT id, amount FROM orders WHERE customer_id = {c} ORDER BY amount DESC NULLS LAST, id LIMIT 5", None, True),
    ("dec_exists", "abstention", "decoy",
     "SELECT c.id FROM customers c WHERE c.id <= {n} AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)", None, False),
]


def instantiate(template, seed):
    template_id, family, kind, sql, reference, ordered = template
    params = _params(random.Random(f"{template_id}:{seed}"))
    return {
        "id": f"{template_id}__{seed}",
        "template": template_id,
        "family": family,
        "kind": kind,
        "source": "synthetic",
        "sql": sql.format(**params),
        "reference_sql": reference.format(**params) if reference else None,
        "ordered": ordered,
    }
