"""Render the research paper figures from site/data/research.json into site/figures/."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "site" / "data" / "research.json"
OUT = ROOT / "site" / "figures"

OURS = "#1f4e79"
OURS_LIGHT = "#9db8d3"
BASE = "#8c8c8c"
BASE_DARK = "#4d4d4d"
WRONG = "#b2182b"
GRID = "#e6e6e6"

NAMES = {
    "rules-only": "Rules-only",
    "open-raw": "Open-raw",
    "open-harness": "Open-harness (ours)",
    "open-harness-nocache": "Harness, no cache",
    "frontier-raw": "Frontier-raw",
    "fw-fast-raw": "FW-fast raw",
    "fw-fast-harness": "FW-fast harness",
    "oss20b-raw": "OSS-20B raw",
    "oss20b-harness": "OSS-20B harness",
    "fw-nemotron-raw": "Nemotron raw",
    "fw-nemotron-harness": "Nemotron harness",
    "ollama-gpt-oss-20b-raw": "Ollama 20B raw",
    "ollama-gpt-oss-20b-harness": "Ollama 20B harness",
    "ollama-qwen3-8b-raw": "Qwen3-8B raw",
    "ollama-qwen25-coder-7b-raw": "Qwen2.5-Coder-7B raw",
    "cache-rules": "Cache + rules",
}

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "legend.frameon": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "svg.fonttype": "none",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.04,
})


def name(system: str) -> str:
    return NAMES.get(system, system)


def color(system: str) -> str:
    if system == "open-harness":
        return OURS
    if system.endswith("harness") or system == "open-harness-nocache":
        return OURS_LIGHT
    return BASE


def save(fig, stem: str) -> None:
    fig.savefig(OUT / f"{stem}.svg")
    plt.close(fig)


def fig_accept_ci(by):
    order = ["rules-only", "open-raw", "fw-fast-raw", "fw-fast-harness",
             "frontier-raw", "open-harness"]
    rows = [by[s] for s in order if s in by]
    fig, ax = plt.subplots(figsize=(5.2, 2.5))
    y = np.arange(len(rows))
    vals = [r["accepted_rate"] * 100 for r in rows]
    lo = [v - r["accepted_ci95"][0] * 100 for v, r in zip(vals, rows)]
    hi = [r["accepted_ci95"][1] * 100 - v for v, r in zip(vals, rows)]
    ax.barh(y, vals, color=[color(r["system"]) for r in rows], height=0.62)
    ax.errorbar(vals, y, xerr=[lo, hi], fmt="none", ecolor="black", elinewidth=0.8, capsize=2.5)
    for yi, v, r in zip(y, vals, rows):
        ax.text(r["accepted_ci95"][1] * 100 + 1.5, yi, f"{v:.1f}%", va="center", fontsize=8,
                fontweight="bold" if r["system"] == "open-harness" else "normal")
    ax.set_yticks(y, [name(r["system"]) for r in rows])
    ax.set_xlim(0, 88)
    ax.set_xlabel("Beneficial accept rate (%), 95% case-bootstrap CI")
    ax.grid(axis="y", visible=False)
    save(fig, "fig_accept_ci")


def fig_wrong_pairs(by):
    pairs = [
        ("gpt-oss-120b", "open-raw", "open-harness"),
        ("FW-fast", "fw-fast-raw", "fw-fast-harness"),
        ("Nemotron", "fw-nemotron-raw", "fw-nemotron-harness"),
        ("gpt-oss-20b", "oss20b-raw", "oss20b-harness"),
        ("Ollama 20B", "ollama-gpt-oss-20b-raw", "ollama-gpt-oss-20b-harness"),
    ]
    pairs = [p for p in pairs if p[1] in by and p[2] in by]
    fig, ax = plt.subplots(figsize=(5.2, 2.4))
    x = np.arange(len(pairs))
    w = 0.36
    raw = [by[p[1]]["incorrect_returned_count"] for p in pairs]
    har = [by[p[2]]["incorrect_returned_count"] for p in pairs]
    ax.bar(x - w / 2, raw, w, color=WRONG, label="Raw")
    ax.bar(x + w / 2, har, w, color=OURS, label="Harness")
    for xi, r, h in zip(x, raw, har):
        ax.text(xi - w / 2, r + 0.6, str(r), ha="center", fontsize=8)
        ax.text(xi + w / 2, h + 0.6, str(h), ha="center", fontsize=8, color=OURS)
    ax.set_xticks(x, [p[0] for p in pairs])
    ax.set_ylabel("Wrong answers returned (of 98)")
    ax.set_ylim(0, max(raw) * 1.18 + 1)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncols=2)
    save(fig, "fig_wrong_pairs")


SCATTER = [
    "rules-only", "cache-rules", "open-raw", "open-harness-nocache", "open-harness", "frontier-raw",
    "fw-fast-raw", "fw-fast-harness", "fw-nemotron-raw", "oss20b-raw",
    "ollama-gpt-oss-20b-raw", "ollama-gpt-oss-20b-harness", "ollama-qwen3-8b-raw", "ollama-qwen25-coder-7b-raw",
]


def scatter_points(ax, by, xfn, labels):
    """Plot accept rate against xfn; hollow red = returned wrong answers. Returns safe (x, y) points."""
    safe = []
    for sid in SCATTER:
        s = by.get(sid)
        if not s:
            continue
        x = xfn(s)
        if x is None:
            continue
        y = s["accepted_rate"] * 100
        wrong = s["incorrect_returned_count"]
        ours = sid == "open-harness"
        if wrong:
            ax.scatter(x, y, s=18 + wrong * 3, facecolors="white", edgecolors=WRONG, linewidths=1.1, zorder=3)
        else:
            ax.scatter(x, y, s=64 if ours else 26, color=OURS if ours else BASE_DARK, zorder=4)
            safe.append((x, y))
        if sid in labels:
            dx, dy, ha = labels[sid]
            ax.annotate(name(sid), (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7.5, ha=ha,
                        va="center", color=OURS if ours else "black", fontweight="bold" if ours else "normal")
    return safe


def scatter_legend(ax, extra=None):
    handles = [
        plt.Line2D([], [], marker="o", ls="", color=BASE_DARK, label="0 wrong"),
        plt.Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=WRONG,
                   label="Returned wrong answers (larger = more)"),
    ]
    ax.legend(handles=handles + (extra or []), loc="lower right")


def fig_accept_vs_cost(by):
    fig, ax = plt.subplots(figsize=(5.4, 3.1))
    labels = {
        "open-harness": (-8, 3, "right"),
        "open-harness-nocache": (7, 5, "left"),
        "frontier-raw": (-7, -6, "right"),
        "fw-fast-harness": (0, -10, "center"),
        "fw-fast-raw": (0, -10, "center"),
        "fw-nemotron-raw": (7, 2, "left"),
        "open-raw": (-7, 2, "right"),
        "oss20b-raw": (-9, -2, "right"),
        "rules-only": (8, 0, "left"),
        "cache-rules": (8, 0, "left"),
        "ollama-gpt-oss-20b-harness": (8, 0, "left"),
        "ollama-gpt-oss-20b-raw": (8, 0, "left"),
        "ollama-qwen3-8b-raw": (8, 0, "left"),
        "ollama-qwen25-coder-7b-raw": (8, 0, "left"),
    }
    safe = scatter_points(ax, by, lambda s: max(s["cost_per_case_usd"] * 1000, 0.01), labels)
    safe.sort()
    frontier, best = [], -1
    for c, a in safe:
        if a > best:
            frontier.append((c, a))
            best = a
    fx, fy = zip(*frontier)
    ax.step(fx, fy, where="post", color=OURS, lw=0.9, ls="--", alpha=0.6, zorder=2)
    ax.set_xscale("log")
    ax.set_xlim(0.006, 20)
    ax.set_xlabel(r"API cost per 1,000 cases (USD, log scale; local models at \$0 drawn at \$0.01)")
    ax.set_ylabel("Accept rate (%)")
    ax.set_ylim(0, 75)
    scatter_legend(ax, [plt.Line2D([], [], color=OURS, ls="--", lw=0.9, label="Best safe accept per budget")])
    save(fig, "fig_accept_vs_cost")


def ecdf(values):
    v = np.sort(np.asarray(values, dtype=float))
    return v, np.arange(1, len(v) + 1) / len(v)


def fig_latency_cdf(by):
    order = [("open-raw", BASE, "-"), ("frontier-raw", BASE_DARK, "--"),
             ("open-harness-nocache", OURS_LIGHT, "-"), ("open-harness", OURS, "-")]
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    for sys, col, ls in order:
        if sys not in by:
            continue
        lat = [max(r["latency_ms"] / 1000, 0.01) for r in by[sys]["records"] if r.get("latency_ms") is not None]
        x, y = ecdf(lat)
        ax.plot(x, y * 100, color=col, ls=ls, lw=1.6 if sys == "open-harness" else 1.2, label=name(sys))
    ax.axhline(50, color="black", lw=0.5, ls=":")
    ax.text(0.04, 52, "median", fontsize=7)
    ax.set_xscale("log")
    ax.set_xlabel("Optimizer wall time per case (s, log)")
    ax.set_ylabel("Cases finished (%)")
    ax.set_ylim(0, 101)
    ax.legend(loc="lower right")
    save(fig, "fig_latency_cdf")


def fig_speedup_cdf(by):
    order = [("open-raw", BASE, "-"), ("frontier-raw", BASE_DARK, "--"), ("open-harness", OURS, "-")]
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    for sys, col, ls in order:
        if sys not in by:
            continue
        sp = [r["speedup"] for r in by[sys]["records"]
              if r.get("outcome") == "accepted" and r.get("speedup")]
        x, y = ecdf(sp)
        ax.plot(x, (1 - y) * len(sp), color=col, ls=ls, lw=1.6 if sys == "open-harness" else 1.2,
                label=f"{name(sys)} (n={len(sp)})", drawstyle="steps-post")
    ax.axvline(1.25, color="black", lw=0.5, ls=":")
    ax.text(1.28, 2, "≥20% faster gate", fontsize=7, rotation=90, va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel("SQL speedup of accepted rewrite (×, log)")
    ax.set_ylabel("Accepted rewrites at least this fast")
    ax.legend(loc="upper right")
    save(fig, "fig_speedup_cdf")


def fig_outcomes(by):
    order = ["rules-only", "open-raw", "frontier-raw", "open-harness-nocache", "open-harness"]
    rows = [by[s] for s in order if s in by][::-1]
    cats = [
        ("accepted", "Accepted", OURS, None),
        ("no_change", "Kept original", "#d9d9d9", None),
        ("not_faster", "Not faster", "#bdbdbd", "///"),
        ("regression", "Regression", "#737373", None),
        ("incorrect", "Incorrect", WRONG, None),
        ("invalid", "Invalid", "#e08080", "xx"),
    ]
    fig, ax = plt.subplots(figsize=(5.2, 2.4))
    y = np.arange(len(rows))
    left = np.zeros(len(rows))
    for key, label, col, hatch in cats:
        vals = np.array([r["outcomes"].get(key, 0) * 100 for r in rows])
        ax.barh(y, vals, left=left, color=col, hatch=hatch, edgecolor="white", linewidth=0.4,
                height=0.62, label=label)
        for yi, l, v in zip(y, left, vals):
            if v >= 7:
                ax.text(l + v / 2, yi, f"{v:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if key in {"accepted", "incorrect", "regression"} else "black")
        left += vals
    ax.set_yticks(y, [name(r["system"]) for r in rows])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of cases (%)")
    ax.grid(visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.22), ncols=6, handlelength=1.2, columnspacing=0.8)
    save(fig, "fig_outcomes")


def fig_family_heatmap(by, cases):
    systems = ["rules-only", "open-raw", "frontier-raw", "open-harness"]
    counts = {}
    for c in cases:
        counts[c["family"]] = counts.get(c["family"], 0) + 1
    fams = sorted(counts, key=lambda f: (-counts[f], f))
    m = np.array([[by[s]["accepted_by_family"].get(f, np.nan) * 100 for s in systems] for f in fams])
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    im = ax.imshow(m, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    for i in range(len(fams)):
        for j in range(len(systems)):
            v = m[i, j]
            ax.text(j, i, "—" if math.isnan(v) else f"{v:.0f}", ha="center", va="center", fontsize=7.5,
                    color="white" if v > 60 else "black",
                    fontweight="bold" if j == len(systems) - 1 else "normal")
    ax.set_xticks(range(len(systems)), [name(s).replace(" (ours)", "\n(ours)") for s in systems])
    ax.set_yticks(range(len(fams)), [f"{f.replace('_', ' ')} (n={counts[f]})" for f in fams])
    ax.tick_params(length=0)
    ax.grid(visible=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Accept rate (%)")
    cb.outline.set_linewidth(0.4)
    save(fig, "fig_family_heatmap")


def fig_cache_ablation(by):
    steps = ["open-raw", "open-harness-nocache", "open-harness"]
    if not all(s in by for s in steps):
        return
    labels = ["Raw", "Harness,\nno cache", "Harness"]
    metrics = [
        ("Accept rate (%)", lambda r: r["accepted_rate"] * 100, "{:.1f}"),
        ("Wrong answers", lambda r: r["incorrect_returned_count"], "{:.0f}"),
        ("Median latency (s)", lambda r: r["latency_p50_ms"] / 1000, "{:.1f}"),
        ("Output tokens / case", lambda r: r["output_tokens_per_case"], "{:,.0f}"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(6.6, 2.0))
    x = np.arange(3)
    for ax, (title, fn, fmt) in zip(axes, metrics):
        vals = [fn(by[s]) for s in steps]
        ax.plot(x, vals, color=BASE, lw=1, zorder=1)
        ax.scatter(x, vals, color=[BASE, OURS_LIGHT, OURS], s=26, zorder=2)
        top = max(vals) if max(vals) else 1
        for xi, v in zip(x, vals):
            ax.text(xi, v + top * 0.08, fmt.format(v), ha="center", fontsize=7)
        ax.set_title(title)
        ax.set_xticks(x, labels, fontsize=6.5)
        ax.set_xlim(-0.4, 2.4)
        ax.set_ylim(0, top * 1.3)
        ax.grid(axis="x", visible=False)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig_cache_ablation")


def fig_mcnemar(comps):
    if not comps:
        return
    fig, ax = plt.subplots(figsize=(5.2, 2.3))
    y = np.arange(len(comps))[::-1]
    for yi, c in zip(y, comps):
        m = c["mcnemar_accepted"]
        ax.barh(yi, m["a_only"], color=OURS, height=0.55)
        ax.barh(yi, -m["baseline_only"], color=BASE, height=0.55)
        ax.text(m["a_only"] + 0.8, yi, f'{m["a_only"]}', va="center", fontsize=7.5, color=OURS)
        ax.text(-m["baseline_only"] - 0.8, yi, f'{m["baseline_only"]}', va="center", ha="right", fontsize=7.5)
        p = m["p_value"]
        ptxt = f"p={p:.1e}" if p < 1e-3 else f"p={p:.4f}" if p < 0.01 else f"p={p:.3f}"
        ax.text(52, yi, ptxt, va="center", fontsize=7.5, fontweight="bold" if p < 0.05 else "normal")
    ax.axvline(0, color="black", lw=0.7)
    labels = [f'{name(c["system"]).replace(" (ours)", "")}\nvs {name(c["baseline"])}' for c in comps]
    ax.set_yticks(y, labels, fontsize=7.5)
    ax.set_xlim(-14, 62)
    ax.set_xlabel("Discordant cases: baseline-only accepts (left) vs system-A-only accepts (right)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig_mcnemar")


def fig_bootstrap_forest(comps):
    if not comps:
        return
    fig, ax = plt.subplots(figsize=(5.2, 2.2))
    y = np.arange(len(comps))[::-1]
    for yi, c in zip(y, comps):
        g = c["bootstrap_accept_gap"]
        mean, (lo, hi) = g["mean"] * 100, [v * 100 for v in g["ci95"]]
        real = lo > 0
        col = OURS if real else BASE
        ax.plot([lo, hi], [yi, yi], color=col, lw=2.2, solid_capstyle="butt")
        ax.scatter([mean], [yi], color="white", edgecolors=col, s=36, zorder=3, linewidths=1.4)
        ax.text(hi + 1.5, yi, f"{mean:+.1f} [{lo:+.1f}, {hi:+.1f}]", va="center", fontsize=7.5)
    ax.axvline(0, color="black", lw=0.7, ls="--")
    labels = [f'{name(c["system"]).replace(" (ours)", "")}\nvs {name(c["baseline"])}' for c in comps]
    ax.set_yticks(y, labels, fontsize=7.5)
    ax.set_xlim(-10, 92)
    ax.set_xlabel("Accept-rate gap, percentage points (template-cluster bootstrap, 95% CI)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig_bootstrap_forest")


def fig_tokens_vs_accept(by):
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    labels = {
        "open-harness": (-8, 4, "right"),
        "open-harness-nocache": (7, 4, "left"),
        "frontier-raw": (7, 0, "left"),
        "fw-fast-harness": (0, -10, "center"),
        "fw-fast-raw": (0, -10, "center"),
        "fw-nemotron-raw": (0, 9, "center"),
        "open-raw": (-8, 3, "right"),
        "oss20b-raw": (-9, -3, "right"),
        "ollama-qwen3-8b-raw": (8, 0, "left"),
        "ollama-qwen25-coder-7b-raw": (8, 0, "left"),
    }
    scatter_points(ax, by, lambda s: s["output_tokens_per_case"] or None, labels)
    ax.set_xscale("log")
    ax.set_xlim(70, 30000)
    ax.set_xlabel("Output tokens per case (log scale)")
    ax.set_ylabel("Accept rate (%)")
    ax.set_ylim(0, 75)
    scatter_legend(ax)
    save(fig, "fig_tokens_vs_accept")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(DATA.read_text())
    dev = data["splits"]["dev"]
    by = {s["system"]: s for s in dev["systems"]}
    order = {"open-raw": 0, "frontier-raw": 1, "rules-only": 2}
    comps = [c for c in data.get("paired_stats", {}).get("comparisons", []) if c.get("split") == "dev"]
    comps.sort(key=lambda c: (c["system"] != "open-harness", order.get(c["baseline"], 9)))

    fig_accept_ci(by)
    fig_wrong_pairs(by)
    fig_accept_vs_cost(by)
    fig_latency_cdf(by)
    fig_speedup_cdf(by)
    fig_outcomes(by)
    fig_family_heatmap(by, dev["cases"])
    fig_cache_ablation(by)
    fig_mcnemar(comps)
    fig_bootstrap_forest(comps)
    fig_tokens_vs_accept(by)
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


if __name__ == "__main__":
    main()
