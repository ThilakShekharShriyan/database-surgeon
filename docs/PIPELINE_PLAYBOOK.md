# Database Surgeon: pipeline, ownership and delivery plan

Companion to [STUDY_GUIDE.md](STUDY_GUIDE.md). “Owner” below means the role that
should be accountable in a team, not a claim that the repository has that staff.
This document describes work; it does not launch model jobs, training or database
changes. Saved measurements are pinned in [STUDY_EVIDENCE.json](STUDY_EVIDENCE.json).

## 1. The three loops

| Loop | Purpose | Typical owner | Output |
| --- | --- | --- | --- |
| Optimization | Find a beneficial replacement for a particular request. | Database/platform engineer | Candidate or original, with evidence and resource usage. |
| Evaluation | Compare systems under a declared protocol. | Evaluation engineer / independent reviewer | Complete traces, matched comparisons, uncertainty and failures. |
| Learning | Improve a future policy using permitted historical examples. | ML engineer with data owner | Dataset, candidate checkpoint and release decision. |

Keep their data boundaries explicit. An evaluator fixture used to repair a
candidate is development feedback. An evaluation example added to SFT is training
data. A replayed response is historical evidence, not a new inference trial.

## 2. Where the pieces live

```text
SQL / workload
  → Python System + model Client
  → restricted PostgreSQL checks and measurements
  → one trace record per system / case / trial
  → offline paired comparison and evidence export
  → research dashboard / static report / recorded demo

Accepted examples + explicit provenance
  → curated SFT / preferences
  → optional training service or local trainer
  → candidate checkpoint
  → separate untouched evaluation before any serving promotion
```

Local layout:

| Surface | Location | Role |
| --- | --- | --- |
| PostgreSQL prototype | `127.0.0.1:55432` | Seeded fixture schemas and execution timing; use the restricted reader for candidate SQL. |
| Python workbench service | `127.0.0.1:8765` | Live lab/optimization/verification endpoints. |
| Next.js application | Usually `3100`; isolated production demo `3101` | Research, demo and lab routes. |
| Static companion | `127.0.0.1:8766` when served | Saved research report without the evaluator. |
| Canonical eval records | `benchmarks/eval_v2/runs/<system>/<split>_t<trial>.jsonl` | Per-case saved outcomes and resource records. |
| Legacy lab records | `results/<run-id>/` | Separate older pipeline; do not mix its denominator with eval_v2. |
| Mutable working state | `.local/` | Response/verdict/workload caches, training files and operational logs. |
| Research snapshot | `web/public/research/snapshot.json`, `site/data/research.json` | UI presentation data, refreshed deliberately. |

Cloud inference can involve Fireworks, Groq or the configured closed-model API;
local inference can use a compatible local endpoint. A local database does not
make remote model prompts private. Never publish `.env` files, credentials or
unreviewed customer traces as part of a study packet.

## 3. Stage-by-stage implementation map

| Stage | What it does and why | Implementation | Current limit / next gate |
| --- | --- | --- | --- |
| 1. Scope | Admit SELECT workloads with an explicit observable result contract. | `surgeon/database.py`, `surgeon/lab.py` | Unsupported ordering, functions or dialects need explicit rejection; no arbitrary SQL-equivalence claim. |
| 2. Provenance | Keep source, case, family, template and split identity. | `surgeon/eval/cases.py`, `synth.py`, manifest | Public inputs and related variants require cross-source lineage review. |
| 3. Fixtures | Generate deterministic performance and correctness instances. | `surgeon/workload.py`, `surgeon/eval/fixtures.py` | Current verifier consumes all eight; prepare fresh evaluator-only instances. |
| 4. Context | Explain schema constraints, indexes, statistics and original plan. | `catalog.py`, `systems.py` | Pin context and keep actual constraints separate from empirical statistics. |
| 5. Cheap candidates | Try cached candidates and rules before inference. | `workload_cache.py`, `rules.py` | Cache is shared and structure matching is weak; purity of new rules-only runs is not assured. |
| 6. Model proposals | Generate structured candidates with optional retrieval and feedback. | `llm.py`, `systems.py`, `registry.py` | Full harness permits up to nine calls per stage; reasoning/response parse behavior varies. |
| 7. Candidate gates | Guard SQL, compare outputs/types and measure benefit. | `database.py`, `Verifier` in `systems.py` | Finite fixtures; type/ordering support must be admitted. Consistent snapshots and output limits matter at scale. |
| 8. Repair or fallback | Repair when rounds remain; otherwise retain original. | `systems.py` | Negative cache can skip useful work. Stop conditions need expected-value calibration. |
| 9. Evaluate | Judge final returned SQL and record all outcome categories. | `judge.py`, `runner.py` | Current judge shares fixtures with verifier; persistent cache and resume identity need versioning. |
| 10. Compare | Summarize resources, disagreements, effect sizes and intervals. | `metrics.py`, `comparison.py`, `report.py` | Partial cohorts, repeated trials, dependent variants and multiple comparisons require disclosure. |
| 11. Learn | Export permitted examples; optionally train a candidate specialist. | `train_data.py`, `build_specialist_dataset.py`, `finetune/` | Dev examples enter final SFT; actual Muse validation overlaps 12 template groups. |
| 12. Present | Load saved evidence and inspect queries or recorded examples. | `export_research.py`, `web/`, `site/` | Snapshot time is separate from current run progress; replay must remain distinct from live inference. |

The actual current optimization order is **cache → rules → model rounds**, with
verification at candidate admissions. The larger proposed architecture in
[ARCHITECTURE.md](ARCHITECTURE.md) includes components not yet implemented.

## 4. Important method choices and their alternatives

### SQL text rewriting versus physical tuning

Rewriting changes the expression sent to the planner. Index tuning changes the
physical design; knob tuning changes execution conditions. A rewrite benchmark
should hold physical design fixed. If an index creates the win, call it an index
experiment and include storage/write/maintenance costs.

### Narrow rules versus model search

Rules are cheap, reproducible and understandable within proven preconditions.
Models cover less stereotyped combinations but introduce semantic risk and
inference cost. A hybrid pipeline can benefit from both. Demonstrating that
requires a cache-disabled rules baseline and matched ablations, not a name in a
registry.

### Planner precheck versus execution measurement

Planner estimates can cheaply discard unlikely candidates, but misestimation can
also discard a real improvement. Compare precheck on/off under the same search
budget. Do not replace runtime measurement with an estimated-cost score.

### Stronger verification versus an independent test

Adding former evaluator fixtures to the optimizer catches known failures. It
also consumes their independence. The next release should explicitly name a
development oracle and a new final oracle. Test generalization over both new
query groups and new database instances.

### Cache reuse versus a clean cold benchmark

A warm system may reasonably exploit historical workload knowledge. A cold
comparison must prevent earlier systems' answers or labels from changing later
systems' behavior. Evaluate both tracks, with separate cache identities and
clear warmup data. Negative-cache abstention must be counted as abstention.

## 5. Work still required, in dependency order

### Milestone A — make experiments identifiable

**Accountable roles:** evaluation engineer and platform engineer.

Required changes:

- Define an immutable experiment identity covering code, cases/splits, model
  versions/settings, retrieval data, workload cache, router, database contents,
  schema/indexes, session settings, threshold, repetitions and prices.
- Reject incompatible resume records. Version judge results with the relevant
  database/oracle/timing identity.
- Separate empty cold cache, frozen warm cache and training caches; disable shared
  cache for rules-only and component ablations.
- Serialize timing across processes or use isolated database workers. Record host
  load and whether measurements contend.
- Keep complete-denominator accounting for errors, timeouts, unsupported cases
  and incomplete runs. Retain legacy evidence under its actual identity.

**Acceptance evidence:** a deliberately changed fixture or policy cannot reuse
an old verdict/run; rerun order does not alter a cold baseline through shared
cache state. No new winner claim is made merely by adding hashes.

### Milestone B — regain independent correctness evidence

**Accountable roles:** database engineer and independent evaluator.

- Add adversarial tests for missing relationships, duplicate fan-out, NULLs,
  empty groups, precision and temporal boundaries to development validation.
- Prepare new final instances unavailable to retrieval, repair and reward design.
- Define admitted ordered/LIMIT contracts, volatility restrictions, output-volume
  limits and consistent snapshot behavior.
- Audit rule assumptions against declared constraints. Retain a reject/original
  outcome for unsupported cases.

**Acceptance evidence:** the known errors fail development validation, and a
separate locked oracle is used for final assessment. Zero observed mismatches is
reported with its scope; it is not a universal correctness SLA.

### Milestone C — complete fair model/harness comparisons

**Accountable role:** evaluation engineer.

Minimum useful matrix:

| Model class | Raw | Same full harness | Lean, matched-budget harness |
| --- | --- | --- | --- |
| Configured closed comparator | Required | Required to isolate harness advantage | Useful efficiency comparison |
| Open baseline | Required | Required | Useful efficiency comparison |
| Specialist | Required after deployment | Required after deployment | Required if claiming cheaper proposal/search |

Predeclare primary system, workload, trial policy, correctness/quality criterion,
acceptable quality margin if applicable, and resource objective. Freeze before
held-out evaluation. Include existing strong relevant baselines even when the
results are unfavorable. Complete all matched cases or label the comparison as
partial; do not extrapolate a high early completion rate.

**Acceptance evidence:** complete held-out cohorts with paired outcomes and
resources, matched context/budgets where the claim requires them, and transparent
uncertainty. A non-significant McNemar result is not a quality-preservation claim.

### Milestone D — prove the efficiency mechanism

**Accountable roles:** platform and database engineers.

- Benchmark exact/parameter-safe cache reuse on a separate warmup workload.
- Reverify cached evidence under declared validity epochs; invalidate on relevant
  schema, index, data/distribution, session or parameter changes.
- Measure cold misses, positive hits and negative hits separately; include cache
  lookup, verification, queuing, throttling and total wall time.
- Compare rules → one model call → repair/escalation against the full search
  harness. Do not assume the best proposed two-call policy is already implemented.
- Evaluate router predictions out of sample, plus a fixed cheap cascade.

**Acceptance evidence:** lower measured end-to-end cost or latency under the
prespecified quality criterion. Coverage-based estimates remain supplementary.

### Milestone E — establish useful workload value

**Accountable roles:** workload owner/DBA and product engineer.

- Obtain permission to inspect a representative workload. Use read-only export
  rather than the current demo script's extension creation/reset/replay flow.
- Preserve bind values or admitted parameter domains, frequency and concurrency.
- Evaluate larger scales, selectivity/skew changes and already-efficient queries.
- Report total workload execution time/resources saved and the cost of finding
  those savings. Do not substitute an average of successful speedups.
- Separate elapsed-time, capacity, latency and dollar benefits.

**Acceptance evidence:** a workload owner can reproduce positive net value under
the stated traffic and cost assumptions. The 38-statement fixture replay does
not satisfy customer-workload validation.

### Milestone F — evaluate the specialist, then deploy cautiously

**Accountable roles:** ML engineer, data owner and serving owner.

- Split by template/schema lineage before training, and audit overlap.
- Keep evaluation prompts/references and final fixtures out of the learning loop.
- Preserve useful abstention examples instead of teaching only “always change.”
- Deploy the candidate endpoint and benchmark base versus tuned with identical
  generation settings and verifier; report SQL outcomes, resources and errors.
- Admit a serving version only after its release gates pass; establish shadow
  evaluation, drift invalidation, fallback and rollback behavior.

**Acceptance evidence:** untouched SQL evaluation demonstrates the claimed
quality/efficiency change. Adapter promotion or SQL-string match is insufficient.

## 6. Metrics checklist for the next experiment

| Measurement | Denominator / unit | What it answers |
| --- | --- | --- |
| Source acceptance | Admitted / attempted source inputs | How much of the intended task is supported? |
| Useful rewrite coverage | Accepted / all eligible evaluation cases | How often do we deliver a measured improvement? |
| Incorrect returns | Count and rate over returned cases, with scope | How often did the oracle find semantic failure? |
| Abstention, invalidity, regression | Separate counts/rates | What happened when optimization did not help? |
| Workload execution benefit | Sum of traffic-weighted runtime/resources | Does it matter to the workload? |
| Optimizer p50/p95 | End-to-end wall time, plus components | What does finding the rewrite cost in time? |
| API and infrastructure cost | Total and per request/useful rewrite | Is the complete service economical? |
| Calls, tokens, cache behavior | Per request and route | Which mechanism consumes or saves resources? |
| Paired effect and CI | Same cases; template-aware analysis | How large and uncertain is the difference? |
| Repeated-trial variation | Trial-level records and fresh timings | How stable is the result? |

If no useful rewrites are delivered, cost per useful rewrite is undefined rather
than zero. Wrong/invalid SQL has no meaningful delivered speedup. Missing prices
stay unknown. A local API charge of zero excludes local compute and energy.

## 7. Commands: inspect first, spend deliberately

These are study examples, not actions performed while writing this packet.
Use the repository's local environment and installed dependencies.

### Offline artifact analysis: no inference or database evaluation

```sh
.venv/bin/python scripts/build_study_evidence.py
.venv/bin/python -m surgeon.eval report --split dev --baseline frontier-raw --comparison-trial 0
.venv/bin/python scripts/export_research.py
```

These commands write local reports/snapshots. They do not launch models or
seed databases. They analyze saved results, which may be stale or incomplete.

### Local presentation and checks

```sh
npm --prefix web run typecheck
npm --prefix web run build
SURGEON_WEB_PORT=3101 npm --prefix web start
python3 -m http.server 8766 --bind 127.0.0.1 --directory site
.venv/bin/python -m unittest discover -s tests -v
RESEARCH_BASE_URL=http://127.0.0.1:3101 node scripts/verify_research.mjs
```

The UI verification requires the servers and Chrome. It exercises recorded
replay without paid inference. Database integration tests require a seeded local
database and `SURGEON_TEST_DATABASE=1`; skipped tests do not establish readiness.

### Model experiments: potentially paid, not automatically fair

```sh
.venv/bin/python -m surgeon.eval run open-raw --split dev --trials 1 --max-usd 4
.venv/bin/python -m surgeon.eval run open-harness --split dev --trials 1 --max-usd 6
```

Different ceilings here are examples, not a matched-budget design. Existing run
files may cause resume; current cache state may change behavior. Establish the
experiment identity and budget reservations before using these as release tests.
Listing several systems applies the CLI ceiling per invocation/system, not one
global sum. Unknown prices and in-flight calls can prevent a strict billing cap.

Do not run broad overnight scripts simply to prepare a presentation. They can
launch inference and training or change working caches. The `pg_stat` collector
can create an extension and reset statistics; use it only in the owned demo
environment unless it has been redesigned for a production read-only export.

## 8. Release decision template

Fill in actual values before approving a version:

```text
Task / supported SQL contract:
Target workload and repetition distribution:
Candidate model + harness + data/cache versions:
Baseline and reason for selecting it:
Primary quality/safety criterion:
Primary cost or latency objective:
Independent final query groups and database instances:
Budget, trial, timing and cache protocols:
Complete outcomes and paired effect intervals:
All-in resource ledger and break-even assumptions:
Failures, unsupported coverage and limitations:
Deployment scope, invalidation, original fallback and rollback:
Decision: reject / inconclusive / advisory pilot / promote within scope
```

A good release decision can be “inconclusive.” A strong engineering result is an
experiment that distinguishes a useful mechanism from a persuasive but unsupported
story.
