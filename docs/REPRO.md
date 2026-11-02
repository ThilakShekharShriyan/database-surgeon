# Reproduce Database Surgeon (eval v2)

## One-liners

```bash
# Measured table
.venv/bin/python -m surgeon.eval report --split dev

# Compare against a named saved baseline using a preselected trial (default 0).
.venv/bin/python -m surgeon.eval report --split dev --baseline frontier-raw --comparison-trial 0

# Named systems
.venv/bin/python -m surgeon.eval systems

# Local demo API (cascade-local: rules → gpt-oss harness if registered)
.venv/bin/python -m surgeon.service   # :8765
# web: npm run dev → /demo  (“Local cascade”)

# Research site preview
bash scripts/site/sync.sh && cd site && python3 -m http.server 8766
```

## Paired comparisons and interpretation

The report writes `benchmarks/eval_v2/results/summary_<split>.json`. Each
non-baseline system has a `paired_comparison` with:

- Exact, two-sided McNemar tests for **accepted rewrite** and **incorrect return**.
  The table has A on rows, baseline on columns, and False/True in that order.
  Discordant counts show which system alone had the outcome. For incorrect
  returns, a larger count is worse. No discordance gives p=1; no pairs gives null.
- A template-level sensitivity test: all instances must be accepted for template
  acceptance; any incorrect instance marks a template incorrect. Only templates
  with every expected instance present in both systems enter this test.
- Matched means, differences, ratios and 95% template-cluster bootstrap intervals
  for API cost, optimizer latency, LLM time, verification time, model calls,
  output tokens and SQL speedup. Unknown measurements remain unknown and each
  metric records its denominator. Speedup omits wrong/invalid outputs and uses
  1x for unchanged queries; it is a secondary conditional metric, not total
  workload savings. Ratios are A/baseline; smaller is better except speedup.

The primary trial must be chosen before examining scores; default trial 0 prevents
pooling repeated case observations as independent pairs. Other trials remain in
the descriptive summary. The per-case McNemar p-value assumes independent pairs;
template variants are dependent, hence the sensitivity test and clustered CIs.
Intervals describe case/template variation within the selected trial, not
between-trial inference or database timing variation. These results do not replace
fresh timing confirmation. Method reference:
[statsmodels McNemar documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html).

Development comparisons and unadjusted p-values are exploratory. A large p-value
does **not** prove equivalent accuracy, noninferiority or zero error risk.
Predeclare the primary system comparison and outcome for held-out evaluation;
use a separate noninferiority design if making a quality-preservation claim.

Partial runs show observed-case rates and matched-subset comparisons, with missing
IDs in JSON. Pareto membership requires complete splits and the baseline's trial
count. Existing hashes do not fully pin code, database or workload-cache state;
the paired report discloses these limits rather than certifying reproducibility.

Keep the strongest relevant frontier baseline and compare the same harness and
budgets where possible. Additional older, cheaper or weaker closed models may be
included as explicitly labeled comparators, selected for a deployment use case
before seeing final scores. Do not relabel a weaker comparator as the strongest
frontier or hide unfavorable comparisons. A useful win can be lower cost or
latency at a predeclared acceptable quality level; higher accuracy is not required.
Report API cost separately from database/hardware costs. Current optimizer latency
excludes throttling and database lock queueing, so it is not end-to-end serving
latency. Measure total optimization overhead and execution frequency before
claiming amortized database savings.

## Overnight jobs (LaunchAgents)

| Label | Script | Purpose |
|-------|--------|---------|
| `com.databasesurgeon.gptoss` | `scripts/overnight/ollama_gptoss_only.sh` | Local gpt-oss:20b raw (+ harness) |
| `com.databasesurgeon.vast` | `scripts/overnight/vast_train_now.sh` | Ampere+ LoRA SFT, eval, destroy |
| `com.databasesurgeon.finish` | `scripts/overnight/finish_wave_a.sh` | Router/cascades/RESULTS/site when ready |

Unload: `launchctl bootout gui/$(id -u)/com.databasesurgeon.<name>`

## Vast safety

- Only touches label `database-surgeon-sft`
- Destroy uses `vastai destroy instance <id> -y`
- Offers require `compute_cap>=800` (no V100)

## Groq

Harness/ablations paused on rate limits. Resume later; not required for the first RESULTS draft.
