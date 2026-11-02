"""Deterministic rewrite rules on the SQLGlot AST (no model, no cost).

Each rule is equivalence-preserving by construction for the stated pattern and
fires only on that exact pattern. Output still goes through verification like
any model candidate. Requires sqlglot (installed in .venv).

Calcite counterparts: sargable_* and extract_year_month ~ DateRangeRules,
constant_shift / coalesce_key ~ ReduceExpressionsRule, drop_subquery_order ~
SortRemoveRule, drop_distinct_on_key ~ AggregateRemoveRule. The same author
wrote the case templates, so rule-only scores are not a blind test.
"""

import datetime

import sqlglot
from sqlglot import exp

PRIMARY_KEYS = {"orders": "id", "customers": "id", "emp": "empno", "dept": "deptno",
                "part": "p_partkey", "lineitem": "l_orderkey"}


def _ts(value):
    return exp.Cast(this=exp.Literal.string(value), to=exp.DataType.build("TIMESTAMP"))


def _range(column, start, end):
    return exp.and_(exp.GTE(this=column.copy(), expression=_ts(start)),
                    exp.LT(this=column.copy(), expression=_ts(end)))


def _date(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _literal_text(node):
    if isinstance(node, exp.Literal) and node.is_string:
        return node.this
    if isinstance(node, exp.Cast) and isinstance(node.this, exp.Literal) and node.this.is_string:
        return node.this.this
    return None


def _int(node):
    if isinstance(node, exp.Literal) and not node.is_string and node.this.lstrip("-").isdigit():
        return int(node.this)
    if isinstance(node, exp.Neg):
        inner = _int(node.this)
        return None if inner is None else -inner
    if isinstance(node, (exp.Add, exp.Sub)):
        a, b = _int(node.this), _int(node.expression)
        if a is not None and b is not None:
            return a + b if isinstance(node, exp.Add) else a - b
    return None


def sargable_day(node):
    """to_char(col, 'YYYY-MM-DD') = 'd' and col::date = DATE 'd' become a half-open range."""
    if not isinstance(node, exp.EQ):
        return None
    left, right = node.this, node.expression
    day = _date(_literal_text(right))
    if day is None:
        return None
    column = None
    if isinstance(left, exp.ToChar) and _literal_text(left.args.get("format")) == "YYYY-MM-DD":
        column = left.this
    elif isinstance(left, exp.Anonymous) and left.name.lower() == "to_char" and len(left.expressions) == 2 \
            and _literal_text(left.expressions[1]) == "YYYY-MM-DD":
        column = left.expressions[0]
    elif isinstance(left, exp.TimeToStr) and _literal_text(left.args.get("format")) in ("%Y-%m-%d", "YYYY-MM-DD"):
        column = left.this
    elif isinstance(left, (exp.Cast, exp.TsOrDsToDate)) and getattr(left, "to", None) is not None \
            and left.to.this == exp.DataType.Type.DATE:
        column = left.this
    if not isinstance(column, exp.Column):
        return None
    return _range(column, day.isoformat(), (day + datetime.timedelta(days=1)).isoformat())


def sargable_month(node):
    """date_trunc('month', col) = TIMESTAMP 'YYYY-MM-01' becomes a month range."""
    if not isinstance(node, exp.EQ) or not isinstance(node.this, (exp.TimestampTrunc, exp.DateTrunc)):
        return None
    unit = node.this.args.get("unit")
    unit = (unit.name if unit is not None else "").lower()
    column, start = node.this.this, _date((_literal_text(node.expression) or "")[:10])
    if unit != "month" or not isinstance(column, exp.Column) or start is None or start.day != 1:
        return None
    if len((_literal_text(node.expression) or "").strip()) not in (10, 19) or \
            (_literal_text(node.expression) or "").strip()[10:] not in ("", " 00:00:00"):
        return None
    end = datetime.date(start.year + start.month // 12, start.month % 12 + 1, 1)
    return _range(column, start.isoformat(), end.isoformat())


def constant_shift(node):
    """col - k = a - k (or col + k = c) becomes col = constant."""
    if not isinstance(node, exp.EQ) or not isinstance(node.this, (exp.Add, exp.Sub)):
        return None
    column, shift, rhs = node.this.this, _int(node.this.expression), _int(node.expression)
    if not isinstance(column, exp.Column) or shift is None or rhs is None:
        return None
    value = rhs + shift if isinstance(node.this, exp.Sub) else rhs - shift
    return exp.EQ(this=column.copy(), expression=exp.Literal.number(value))


def coalesce_key(node):
    """coalesce(col, d) = v with literal v != d becomes col = v."""
    if not isinstance(node, exp.EQ) or not isinstance(node.this, exp.Coalesce):
        return None
    column, defaults = node.this.this, node.this.expressions
    value = _int(node.expression)
    if not isinstance(column, exp.Column) or len(defaults) != 1 or value is None:
        return None
    default = _int(defaults[0])
    if default is None or default == value:
        return None
    return exp.EQ(this=column.copy(), expression=exp.Literal.number(value))


def _extract_part(node):
    if isinstance(node, exp.EQ) and isinstance(node.this, exp.Extract) and _int(node.expression) is not None:
        part = node.this.this.name.upper()
        if isinstance(node.this.expression, exp.Column):
            return part, node.this.expression, _int(node.expression)
    return None


def extract_year_month(tree):
    """EXTRACT(YEAR ...) = y AND EXTRACT(MONTH ...) = m on one column becomes a range."""
    changed = False
    for conj in list(tree.find_all(exp.And)):
        parts = [p for p in (_extract_part(conj.this), _extract_part(conj.expression)) if p]
        if len(parts) != 2:
            continue
        by = {p[0]: p for p in parts}
        if set(by) != {"YEAR", "MONTH"} or by["YEAR"][1].sql() != by["MONTH"][1].sql():
            continue
        year, month = by["YEAR"][2], by["MONTH"][2]
        if not 1 <= month <= 12:
            continue
        start = datetime.date(year, month, 1)
        end = datetime.date(year + month // 12, month % 12 + 1, 1)
        conj.replace(_range(by["YEAR"][1], start.isoformat(), end.isoformat()))
        changed = True
    return changed


def drop_subquery_order(tree):
    """ORDER BY in a derived table without LIMIT/OFFSET does not define any result order."""
    changed = False
    for sub in tree.find_all(exp.Subquery):
        select = sub.this
        if isinstance(select, exp.Select) and select.args.get("order") and not select.args.get("limit") \
                and not select.args.get("offset"):
            select.set("order", None)
            changed = True
    return changed


def drop_distinct_on_key(tree):
    """SELECT DISTINCT over one table that projects its primary key is already distinct."""
    if not isinstance(tree, exp.Select) or not isinstance(tree.args.get("distinct"), exp.Distinct) \
            or tree.args["distinct"].args.get("on") or tree.args.get("joins") or tree.args.get("group"):
        return False
    source = tree.args.get("from_") or tree.args.get("from")
    table = source.this if source else None
    if not isinstance(table, exp.Table):
        return False
    key = PRIMARY_KEYS.get(table.name)
    if key and any(isinstance(e, exp.Column) and e.name == key for e in tree.expressions):
        tree.set("distinct", None)
        return True
    return False


def _cmp_bound(node):
    """Return (column_sql, op, numeric_literal) for col >/</>=/<= literal."""
    if not isinstance(node, (exp.GT, exp.GTE, exp.LT, exp.LTE)):
        return None
    col, lit = node.this, _int(node.expression)
    if not isinstance(col, exp.Column) or lit is None:
        return None
    op = {exp.GT: ">", exp.GTE: ">=", exp.LT: "<", exp.LTE: "<="}[type(node)]
    return col.sql(dialect="postgres"), op, lit


def union_to_union_all_disjoint(tree):
    """UNION → UNION ALL when both arms filter the same column with disjoint ranges.

    Example: ``amount > hi UNION … amount < lo`` with ``hi >= lo`` cannot share rows.
    """
    if not isinstance(tree, exp.Union) or tree.args.get("distinct") is False:
        return False
    # sqlglot: distinct UNION has distinct=True or unset; UNION ALL has distinct=False
    if tree.args.get("distinct") is False:
        return False
    left, right = tree.this, tree.expression
    if not isinstance(left, exp.Select) or not isinstance(right, exp.Select):
        return False
    if left.args.get("joins") or right.args.get("joins"):
        return False
    lw, rw = left.args.get("where"), right.args.get("where")
    if not isinstance(lw, exp.Where) or not isinstance(rw, exp.Where):
        return False
    a, b = _cmp_bound(lw.this), _cmp_bound(rw.this)
    if a is None or b is None or a[0] != b[0]:
        return False
    (_, op1, v1), (_, op2, v2) = a, b
    hi = v1 if op1 in (">", ">=") else v2 if op2 in (">", ">=") else None
    lo = v1 if op1 in ("<", "<=") else v2 if op2 in ("<", "<=") else None
    if hi is None or lo is None or hi < lo:
        return False
    # Exact complementary ops: one high-side, one low-side
    ops = {op1, op2}
    if not (ops & {">", ">="} and ops & {"<", "<="}):
        return False
    tree.set("distinct", False)
    return True


NODE_RULES = (sargable_day, sargable_month, constant_shift, coalesce_key)
TREE_RULES = (extract_year_month, drop_subquery_order, drop_distinct_on_key, union_to_union_all_disjoint)


def apply_rules(sql):
    """Return (rewritten_sql, [rule names]) or (None, []) when no rule fires."""
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001 - unparseable input simply gets no rule
        return None, []
    fired = []
    for rule in TREE_RULES:
        if rule(tree):
            fired.append(rule.__name__)
    for rule in NODE_RULES:
        for node in list(tree.find_all(exp.EQ)):
            replacement = rule(node)
            if replacement is not None:
                node.replace(replacement)
                fired.append(rule.__name__)
    if not fired:
        return None, []
    return tree.sql(dialect="postgres"), sorted(set(fired))
