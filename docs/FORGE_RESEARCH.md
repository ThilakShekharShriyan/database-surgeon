# Database Surgeon — Forge submission

I built a **verify-or-abstain** PostgreSQL rewrite system on Fireworks. Open models propose faster SQL; a surgical harness accepts a rewrite only when it is **row-equivalent on sealed fixtures (including null/skew)** and **≥20% faster by paired EXPLAIN ANALYZE** — otherwise it returns the original. On the locked 98-case dev split, Fireworks `gpt-oss-120b` **raw** accepts **46.9%** but returns **11 wrong** rewrites; the same model **with the harness** accepts **62.2% with 0 wrong**. That is **+15.3 pp** accept and an **11 → 0** safety cliff vs the required open baseline. Against an optional closed **frontier-raw** baseline we sit at **62.2% / 0 wrong / $0.0020 / 2.9s p50** vs **56.1% / 0 / $0.0027 / 3.8s** — ahead on the board for accept, cost, and optimizer latency; McNemar on accept vs frontier is not significant (honest caveat below). Two statistical tests agree the harness vs raw gains are real.

This page is the playbook for **our** stack: how we chose the task, locked the bench, tried cheap ideas first, measured losses, and proved the wins. Code and traces live in this repo; regenerate stats with `scripts/compute_paired_stats.py`.

Live brief: `/` · Scoreboard charts: `/research` · Demo: `/demo`

**Disclosure:** Built during the Nov 2, 2026 hackathon. Material use of a Cursor agent for implementation and research synthesis, pointed at Fireworks docs, our eval harness, and industry SQL-rewrite literature. Pre-existing work: none for this submission (see `docs/HACKATHON.md`).

---

## Step 1 — Find a task worth doing

I picked **safe SQL rewrite for agent-generated PostgreSQL**: emit a faster equivalent `SELECT`, or abstain. That is a job platform DBAs / FinOps owners already feel when coding agents and BI copilots flood warehouses with expensive queries.

I compared two hackathon-shaped options before committing:

|  | SQL rewrite (this project) | Knob / index tuning |
| --- | --- | --- |
| The job | Emit faster equivalent SQL, or keep the original | Change configs / indexes |
| Who feels the pain | Platform DBAs under agent traffic | Same, plus capacity planning |
| Why “just ask GPT” fails | Open raw is cheap **and wrong** (11/98 incorrect on our bench) | Different failure mode |
| Why a harnessed open stack | 0-wrong SLA + private fingerprint flywheel | Complementary, not a substitute |
| The data | Sealed eval_v2: 171 cases (98 dev / 73 held-out), 11 families, 8 Postgres fixtures | `pg_stat_statements` for production fingerprints |

**Why rewrite won:** we can lock a **public, reproducible** correctness contract (bag equality + EXPLAIN ANALYZE speedup) and show a **corruption cliff** judges can re-run in one day. Knob tuning is valuable but harder to demo as a sealed A/B under the Forge clock.

**Size the value with assumptions written out.** Suppose an agent fleet adds 10k slow SELECTs/day against a warehouse that costs $0.02 of DB CPU per slow query-minute, and the average offender burns 30s. Cutting 20% of that CPU with safe rewrites is on the order of **$1.2k/day** in infrastructure — before LLM API spend. Replace the $0.02 and 30s with your FinOps numbers; the lever is DB + inference, not “cooler SQL.”

**Check the contract before you trust the eval.** Early harness versions verified only on five development schemas; the judge also used null/skew fixtures — and that gap let a few accepts become incorrect returns. We closed it: harness verify now uses the **full** `EVAL_SCHEMAS` set. Accept means the same thing the judge checks.

---

## Step 2 — Run a baseline on an open model

**Required baseline:** Fireworks `accounts/fireworks/models/gpt-oss-120b` as `open-raw` — one sample, catalog + guide + EXPLAIN context, **no** system-side verify.

| System | n | Accept | Wrong returned | $/case | Optimizer p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| **open-raw** (baseline) | 98 | **46.9%** | **11** | $0.0004 | 2.4s |
| frontier-raw (optional closed) | 98 | 56.1% | 0 | $0.0027 | 3.8s |
| rules-only ($0) | 98 | 14.3% | 0 | $0 | ~0s |

**Lock the test set first.** Cases and freeze hashes live under `benchmarks/eval_v2/` (`cases.jsonl`, `FROZEN.json`). Dev = 98; held-out templates = 73. One saved row per case in `dev_t0.jsonl` — both tests in step 6 need those rows, and the **template/family id** matters for the cluster bootstrap.

**Keep the baseline fair.** Temperature 0 / deterministic seeds where the provider allows; same case IDs; never weaken raw to flatter the harness. Raw already looks “okay” on accept rate **until you count wrongs.**

```python
# surgeon/eval/llm.py — OpenAI-compatible Fireworks client
client.chat.completions.create(
    model="accounts/fireworks/models/gpt-oss-120b",
    messages=[...], temperature=0, max_tokens=4096)
```

I also ran a closed frontier-raw baseline on the same cases (optional under the rules). The **required** comparison remains open model before vs after the harness.

---

## Step 3 — Ideate on the system

Cheap ideas first, then spend. Each idea started as a guess about why raw fails.

| Idea | Guess about the failure | Extra cost |
| --- | --- | --- |
| **Rules-only** | Many wins are mechanical (sargability, UNION ALL, …) | $0 |
| **Harness: verify + repair** | Models propose useful SQL but also corrupt null semantics; gate + feedback | ~LLM × best_of / repair |
| **Cascade (flash → Nemotron)** | Spend Ultra only when cheap stages abstain | Intermediate |
| **Workload fingerprint cache** | Agent traffic repeats shapes; verified wins should be free the second time | $0 on hit |
| **Join-graph catalog + rewrite-rule hints** | Multi-table rewrites invent join keys; near-misses need structural cues | Prompt tokens only |
| **Fine-tune (Muse Glimmer LoRA)** | Private dialect after enough **verified** accepts | Training + deploy (optional) |

Looking at raw mistakes pushed us toward the **harness**, not a bigger prompt. Failures were **semantic** (nulls, DISTINCT reuse, EXISTS shape) — the kind of error a judge fixture catches and a confidence score does not.

---

## Step 4 — Build it

One registry of systems (`surgeon/eval/registry.py`), one runner, one judge:

- **Raw / harness / cascade** — `python -m surgeon.eval run <system> --split dev`
- **Strict verify** — equivalence ∥ timing on separate DB connections; full `EVAL_SCHEMAS` before accept
- **Latency levers** — adaptive best_of, first-win accept, early abstain on tiny index-only lookups
- **Fingerprint cache** — positives only (negatives poisoned whole families via fingerprint collision — we learned that the hard way)
- **Paired stats** — `scripts/compute_paired_stats.py` → `benchmarks/eval_v2/results/paired_stats.json`

Fireworks + NVIDIA path used in the prize stack: `glm-5p3-flash` → `gpt-oss-120b` / harness → `nemotron-3-ultra-nvfp4` on escalate.

---

## Step 5 — Run everything on the sealed set

Report wins **and** losses. Incomplete mid-run systems stay marked in `docs/ADVANTAGES.md`.

| System (Fireworks unless noted) | Accept | Wrong | Gap vs open-raw | $/case | Opt p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| open-raw (baseline) | 46.9% | **11** | — | $0.0004 | 2.4s |
| rules-only | 14.3% | 0 | −32.6 pp (safe) | $0 | ~0s |
| fw-fast-raw | 48.0% | 0 | +1.1 pp | $0.0011 | 11.7s |
| fw-fast-harness | 57.1% | 0 | +10.2 pp | $0.0074 | 28.8s |
| frontier-raw | 56.1% | 0 | +9.2 pp | $0.0027 | 3.8s |
| **open-harness** | **62.2%** | **0** | **+15.3 pp** | **$0.0020** | **2.9s** |

**What lost or only partially helped**

- **Raw open models** win on $/case and lose on safety — unacceptable for agent traffic.
- **Rules-only** is safe but low coverage — necessary floor, not the product.
- **Negative fingerprint cache** looked clever and wiped accepts via collisions — removed; positives-only now.
- **Nemotron raw / pre-strict harness** could raise accept while leaking incorrects when verify omitted null fixtures — archived; product gate stays strict.
- **Fine-tune** is optional this round; the harness remains the product.

The headline jump is **wrong → 0** with **higher accept than frontier**, **lower API $**, and **faster optimizer p50** on an open Fireworks stack.

---

## Step 6 — Prove the gain is real

Luck moves a 98-case score. We use the same two ideas as the Forge sample: **McNemar on discordant cases** and a **bootstrap that resamples templates/families** (cases from one template share structure).

```bash
.venv/bin/python scripts/compute_paired_stats.py
# → benchmarks/eval_v2/results/paired_stats.json
```

### Test 1 — McNemar (who wins the disagreements?)

**open-harness vs open-raw (accepted), n = 98**

|  | Harness accepted | Harness not |
| --- | ---: | ---: |
| **Raw accepted** | 43 (both, ignored) | **3** (only raw) |
| **Raw not** | **18** (only harness) | 34 (both not) |

Discordant split **18 vs 3**, exact two-sided p ≈ **0.0015**. Same pairs for **incorrect returned**: harness **0** vs raw **11**, p ≈ **0.001** — the safety cliff is not a coin flip.

**open-harness vs rules-only (accepted):** 47 vs 0 discordant, p ≈ **1.4×10⁻¹⁴**.

**open-harness vs frontier-raw (accepted):** 12 vs 6 discordant, p ≈ **0.24** — we **do not** claim a sealed statistical accept win over frontier. Point estimate favors us (+6.0 pp); CI still includes 0. We claim **open-stack competitiveness** plus the raw-open safety story, and we **do** beat frontier on measured **$/case** and **optimizer p50**.

### Test 2 — Template-cluster bootstrap (would the gap survive another draw of templates?)

5,000 resamples of template clusters:

| Comparison | Mean gap | 95% CI |
| --- | ---: | --- |
| open-harness − open-raw | **+15.4 pp** | **[+5.1, +26.8]** (excludes 0) |
| open-harness − rules-only | +48.0 pp | [+33.7, +62.9] |
| open-harness − frontier-raw | +6.0 pp | [−4.1, +17.4] (includes 0) |

**Call a gain real only when McNemar and the bootstrap agree.** Harness vs raw: both agree. Harness vs frontier accept: both say “not distinguishable at α=0.05” — report the board lead, don’t overclaim the p-value.

---

## How this maps to the rubric

| Criterion | Weight | What this project shows | Where a judge can still push |
| --- | ---: | --- | --- |
| Benchmark | 40% | Locked 98-dev traces; harness vs raw +15.3 pp accept, 11→0 wrong; McNemar + cluster bootstrap; losses reported | Held-out harness still thin; one primary trial (t0) |
| Business | 25% | Agentic SELECT boom, FinOps math with assumptions, private fingerprint flywheel | No customer interview; value math is directional |
| Technical | 20% | Full Fireworks/NVIDIA cascade, strict verify, cache, latency levers, eval CLI | Specialist LoRA deploy optional |
| Demo | 10% | Live workbench + multi-stat research board | ≤60s video: raw wrong → harness abstain/accept |
| Docs | 5% | This page + ADVANTAGES + reproduce commands | Keep ADVANTAGES regenerated after rebench |

**Demo video:** under 60 seconds is better. Show a raw wrong rewrite, the harness abstain or accept, then the step-6 tables. End on **62.2% / 0 wrong** and one caveat (frontier accept CI includes 0).

A strong result with honest caveats beats an impressive number with none.

---

## Reproduce

```bash
.venv/bin/python -m surgeon.eval run open-harness --split dev --trials 1
.venv/bin/python scripts/compute_paired_stats.py
.venv/bin/python scripts/write_advantages_scoreboard.py
.venv/bin/python scripts/export_research.py
```

Demo: http://127.0.0.1:3100 · Research UI: `/research` · Repo: https://github.com/ThilakShekharShriyan/database-surgeon

---

## Sources

- This repository: `surgeon/eval/`, `benchmarks/eval_v2/`, `docs/ADVANTAGES.md`
- Paired stats: `benchmarks/eval_v2/results/paired_stats.json`
- Industry priors (design, not our numbers): summarized in `docs/CRAZY_HARNESS_DEEP_RESEARCH.md`
- Fireworks docs: inference + Muse Glimmer / serverless training
- Forge sample playbook structure: [Forge Deploy Sample Submission](https://app.notion.com/p/Forge-Deploy-Sample-Submission-4093715e8b9b80e3beefcd833c37fa90)
