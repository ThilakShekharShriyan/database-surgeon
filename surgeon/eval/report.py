"""Summaries for every system that has runs, plus the quality/cost/latency frontier."""

import json

from ..config import ROOT
from .cases import load_cases
from .comparison import compare
from .metrics import paired_difference, summarize
from .runner import RUNS, load_trials

OUT = ROOT / "benchmarks" / "eval_v2" / "results"


def pareto(rows, quality="accepted_rate", cost="cost_per_case_usd"):
    """Systems not dominated on (higher quality, lower cost, lower p50 latency), among safe ones."""
    front = []
    for row in rows:
        if row.get(cost) is None:
            continue
        dominated = any(
            other is not row and other.get(cost) is not None
            and other[quality] >= row[quality] and other[cost] <= row[cost]
            and other["latency_p50_ms"] <= row["latency_p50_ms"]
            and (other[quality] > row[quality] or other[cost] < row[cost]
                 or other["latency_p50_ms"] < row["latency_p50_ms"])
            for other in rows)
        if not dominated:
            front.append(row["system"])
    return front


def write_report(split="dev", baseline="frontier-raw", comparison_trial=0):
    if comparison_trial < 0:
        raise ValueError("Comparison trial must be nonnegative.")
    cases, digest = load_cases(split)
    expected = {c["id"] for c in cases}
    rows, trials_by = [], {}
    if RUNS.exists():
        for directory in sorted(p for p in RUNS.iterdir() if p.is_dir()):
            trials = load_trials(directory.name, split)
            if not trials or not any(trials):
                continue
            trials_by[directory.name] = trials
            summary = summarize(trials)
            summary["system"] = directory.name
            summary["expected_cases"] = len(expected)
            summary["complete_trials"] = sum({r["case"] for r in t} == expected for t in trials)
            summary["complete"] = all(
                len(t) == len(expected) and {r["case"] for r in t} == expected for t in trials)
            rows.append(summary)
    for row in rows:
        if baseline in trials_by and row["system"] != baseline:
            row["vs_" + baseline] = paired_difference(trials_by[row["system"]], trials_by[baseline])
            row["paired_comparison"] = compare(
                trials_by[row["system"]], trials_by[baseline], cases, comparison_trial)
    # Compare systems on the same complete split and repetition count. Partial
    # or differently repeated results remain visible, but cannot win this list.
    baseline_trials = len(trials_by.get(baseline, []))
    safe = [r for r in rows if r["incorrect_returned_count"] == 0 and r["complete"]
            and r["trials"] == baseline_trials]
    report = {"split": split, "baseline": baseline, "comparison_trial": comparison_trial,
              "cases_sha256": digest, "systems": rows,
              "pareto_safe": pareto(safe),
              "comparison_note": "Paired tests and estimates use one preselected trial. "
              "McNemar p-values are exact, two-sided, unadjusted and exploratory on dev. "
              "Non-significance does not establish equivalence or noninferiority. "
              "Cost is API cost only. Latency excludes queueing and throttle waits; "
              "speedup excludes wrong/invalid outputs and is not workload-weighted. "
              "Pareto requires complete splits and the baseline's trial count. "
              "A missing baseline produces no paired comparisons.",
              "note": "Synthetic microfixtures on PostgreSQL 16 (development data). "
                      "Accepted = same rows on 8 databases (3 hidden) and >=20% faster by median paired EXPLAIN ANALYZE."}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"summary_{split}.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    lines = [f"{'system':34} {'n/full':>9} {'accept':>7} {'95% CI':>13} {'wrong':>5} {'geo×':>6} "
             f"{'p50 s':>6} {'p95 s':>6} {'llm p50':>7} {'ver p50':>7} {'$/case':>9} {'calls':>5}"]
    for r in sorted(rows, key=lambda r: -r["accepted_rate"]):
        ci = r["accepted_ci95"]
        cost = "unknown" if r["cost_per_case_usd"] is None else f"{r['cost_per_case_usd']:.5f}"
        coverage = f"{r['cases']}/{len(expected)}" + ("*" if not r["complete"] else "")
        llm_p50 = (r.get("optimizer_llm_p50_ms") or 0) / 1000
        ver_p50 = (r.get("optimizer_verify_p50_ms") or 0) / 1000
        lines.append(f"{r['system']:34} {coverage:>9} {r['accepted_rate']:7.3f} {ci[0]:6.3f}-{ci[1]:5.3f} "
                     f"{r['incorrect_returned_count']:5d} {r['geomean_speedup']:6.2f} "
                     f"{r['latency_p50_ms'] / 1000:6.1f} {r['latency_p95_ms'] / 1000:6.1f} "
                     f"{llm_p50:7.1f} {ver_p50:7.1f} {cost:>9} {r['calls_per_case']:5.1f}")
    lines.append("Pareto (zero incorrect returned): " + ", ".join(report["pareto_safe"]))
    lines.append("* Incomplete trial(s); rates describe observed cases. See JSON for missing IDs.")
    lines.append(f"Paired comparison vs {baseline}, preselected trial {comparison_trial} (A = listed system):")
    for r in rows:
        comparison = r.get("paired_comparison")
        if not comparison or not comparison["pairs"]:
            continue
        test = comparison["mcnemar"]["accepted"]
        safety = comparison["mcnemar"]["incorrect_returned"]
        def ratio(metric):
            value = comparison["paired_metrics"][metric]["ratio_of_means_a_over_baseline"]
            return "unknown" if value is None else f"{value:.2f}x"
        lines.append(f"  {r['system']}: n={comparison['pairs']}/{len(expected)}, "
                     f"McNemar accepted p={test['p_value']:.4g} "
                     f"(A-only={test['a_only']}, baseline-only={test['baseline_only']}), "
                     f"incorrect p={safety['p_value']:.4g}; "
                     f"mean cost ratio={ratio('cost_usd')}, mean latency ratio={ratio('latency_ms')}")
    lines.append(report["comparison_note"])
    return "\n".join(lines)
