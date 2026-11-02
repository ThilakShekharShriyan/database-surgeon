"""Paired, offline comparisons on a preselected trial (never the best trial).

Exact McNemar uses the two-sided Binomial(n_discordant, 0.5) test:
https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html
Non-significance is neither equivalence nor noninferiority.
"""

import math
import random
import statistics
from collections import defaultdict


def mcnemar(a, b):
    """Paired Boolean outcomes; table rows=A, columns=B, False then True."""
    if len(a) != len(b):
        raise ValueError("McNemar requires equally sized paired outcomes.")
    table = [[0, 0], [0, 0]]
    for x, y in zip(a, b):
        if not isinstance(x, bool) or not isinstance(y, bool):
            raise ValueError("McNemar requires Boolean outcomes, not trial averages.")
        table[int(x)][int(y)] += 1
    a_only, b_only = table[1][0], table[0][1]
    n = a_only + b_only
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a_only, b_only) + 1)) / (1 << n))
    return {"method": "exact_two_sided_binomial", "pairs": len(a), "table": table,
            "a_only": a_only, "baseline_only": b_only, "discordant": n,
            "p_value": p if a else None,
            "interpretation": "Tests equal marginal outcome rates; does not establish equivalence."}


def _trial(trials, trial):
    rows = {}
    for batch in trials:
        for row in batch:
            if row["trial"] != trial:
                continue
            if row["case"] in rows:
                raise ValueError(f"Duplicate case/trial: {row['case']}/{trial}")
            rows[row["case"]] = row
    return rows


def _cluster_interval(differences, templates, iterations=2000):
    """Resample whole templates, preserving within-template case dependence."""
    if not differences:
        return None
    groups = defaultdict(list)
    for case, value in differences.items():
        groups[templates[case]].append(value)
    clusters = [(sum(values), len(values)) for values in groups.values()]
    # A single template cannot support an across-template uncertainty estimate.
    if len(clusters) < 2:
        return None
    rng = random.Random(11)
    means = []
    for _ in range(iterations):
        sample = [rng.choice(clusters) for _ in clusters]
        means.append(sum(total for total, _ in sample) / sum(count for _, count in sample))
    means.sort()
    return [means[int(0.025 * iterations)], means[int(0.975 * iterations) - 1]]


def compare(trials_a, trials_b, cases, trial=0):
    """A minus baseline; compare identical cases in one declared trial.

    Missing cases are disclosed, never silently interpreted as successes or
    failures. Continuous estimates use the same matched cases, with unknown
    measurements omitted and their denominator recorded.
    """
    a, b = _trial(trials_a, trial), _trial(trials_b, trial)
    expected = {c["id"]: c for c in cases}
    shared = sorted(set(a) & set(b) & set(expected))
    templates = {i: expected[i]["template"] for i in shared}
    reasons = []
    complete = set(a) == set(b) == set(expected)
    if not complete:
        reasons.append("Incomplete or unmatched trial: comparisons describe the shared subset only.")
    for label, rows in (("a", a), ("baseline", b)):
        selected = list(rows.values())
        if len({r.get("config_hash") for r in selected}) > 1:
            reasons.append(f"{label} contains multiple config hashes (possibly simulated stage records).")
        if any(r.get("simulated") for r in selected):
            reasons.append(f"{label} includes simulated cascade records; latency is reconstructed.")
    if any(a[i].get("cases_sha256") != b[i].get("cases_sha256") for i in shared):
        reasons.append("Case manifest hashes differ between systems.")
    if any(expected[i].get("split") == "dev" for i in shared):
        reasons.append("Development results are exploratory, including all p-values.")
    reasons.extend([
        "Per-case McNemar assumes independent pairs; parameter variants share templates. "
        "Use the template test as a sensitivity analysis.",
        "P-values are unadjusted across metrics and systems; predeclare a primary held-out comparison.",
        "Recorded config hashes do not fully pin evaluator code, workload caches or database state.",
    ])
    result = {"trial": trial, "pairs": len(shared), "expected_cases": len(expected),
              "complete": complete, "missing_a": sorted(set(expected) - set(a)),
              "missing_baseline": sorted(set(expected) - set(b)),
              "warnings": reasons, "mcnemar": {}, "paired_metrics": {}}
    groups = defaultdict(list)
    for i in shared:
        groups[templates[i]].append(i)
    expected_groups = defaultdict(set)
    for i, c in expected.items():
        expected_groups[c["template"]].add(i)
    full_groups = [ids for name, ids in groups.items() if set(ids) == expected_groups[name]]
    for metric, outcome in (("accepted", "accepted"), ("incorrect_returned", "incorrect")):
        yes_a = {i: a[i]["outcome"] == outcome for i in shared}
        yes_b = {i: b[i]["outcome"] == outcome for i in shared}
        test = mcnemar([yes_a[i] for i in shared], [yes_b[i] for i in shared])
        test["rate_difference_a_minus_baseline"] = (
            statistics.mean(int(yes_a[i]) - int(yes_b[i]) for i in shared) if shared else None)
        test["difference_ci95_template_bootstrap"] = _cluster_interval(
            {i: int(yes_a[i]) - int(yes_b[i]) for i in shared}, templates)
        # A template succeeds only if every instance is accepted. For safety,
        # a template fails if ANY instance returns an incorrect query.
        aggregate = all if metric == "accepted" else any
        test["template_sensitivity"] = mcnemar(
            [aggregate(yes_a[i] for i in ids) for ids in full_groups],
            [aggregate(yes_b[i] for i in ids) for ids in full_groups])
        test["template_sensitivity"]["definition"] = (
            "all instances accepted" if metric == "accepted" else "any instance incorrect")
        result["mcnemar"][metric] = test
    measures = ("cost_usd", "latency_ms", "llm_ms", "verify_ms", "calls", "output_tokens", "speedup")
    for metric in measures:
        def value(row):
            # No-op retains the original runtime. Wrong/invalid SQL has no
            # meaningful delivered speedup; never impute a successful fallback.
            if metric == "speedup" and row["outcome"] == "no_change":
                return 1.0
            if metric == "speedup" and row["outcome"] in ("incorrect", "invalid"):
                return None
            return row.get(metric)
        pairs = {i: (value(a[i]), value(b[i])) for i in shared}
        pairs = {i: v for i, v in pairs.items() if all(
            isinstance(x, (int, float)) and math.isfinite(x) for x in v)}
        mean_a = statistics.mean(v[0] for v in pairs.values()) if pairs else None
        mean_b = statistics.mean(v[1] for v in pairs.values()) if pairs else None
        differences = {i: x - y for i, (x, y) in pairs.items()}
        result["paired_metrics"][metric] = {
            "pairs": len(pairs), "excluded_pairs": len(shared) - len(pairs),
            "mean_a": mean_a, "mean_baseline": mean_b,
            "mean_difference": statistics.mean(differences.values()) if differences else None,
            "difference_ci95_template_bootstrap": _cluster_interval(differences, templates),
            "ratio_of_means_a_over_baseline": mean_a / mean_b if mean_b else None,
            "lower_is_better": metric != "speedup",
        }
    return result
