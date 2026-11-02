# Crazy harness — efficiency playbook

What industry systems actually ship, what we should steal, whether fine-tuning
helps, and how workload patterns make the stack cheaper *without* trading away
the 0-wrong gate.

Companion: [RESEARCH.md](RESEARCH.md) · private loop: `scripts/private_retrain_loop.py` ·
cache: `surgeon/eval/workload_cache.py`.

Deep research (full synthesis): [CRAZY_HARNESS_DEEP_RESEARCH.md](CRAZY_HARNESS_DEEP_RESEARCH.md) ·
share: https://agent.tinyfish.ai/playground/research/share/01a19dd5-bba8-7471-8c77-8657d273bae7

---

## Verdict (one screen)

| Lever | Effect | Cost of wrongs | Do it? |
| --- | --- | --- | --- |
| **Rules + EXPLAIN precheck** | Free / cheap accept on known shapes | Near-zero if sound | **Yes — already in** |
| **Workload fingerprint cache** | $0 LLM on repeat shapes; negative → abstain | Only store *verified* accepts | **Yes — wired** |
| **Cascade (flash → Nemotron)** | Spend big model only on hard / failed cases | Harness still gates | **Yes** |
| **Verified RAG (few-shot wins)** | Steers small models | Can leak privacy if not local | Dev OK; VPC for prod |
| **SFT on verified accepts** | Specialist learns house dialect | Overfit / silent wrongs without gate | **Optional flywheel** |
| **DPO (accept ≻ incorrect)** | Cuts corruption rate of open-raw | Needs preference pairs | **After ≥200 pairs** |
| **RL / execution reward** | HarnessSQL-style accuracy jumps | Heavy infra | Later / research |

**Fine-tuning alone does not make sense as the product.** Datadog’s DBM team
keeps a high-precision heuristic engine (P≈0.90) and only lets an LLM propose
*extra* patterns — then they hammer precision with experiments. HarnessSQL keeps
*only verified trajectories* for SFT then RL. Same lesson: **the harness is the
product; FT is a specialist behind it.**

---

## What other companies / papers do

### Datadog DBM (query optimization agent)

- Multi-source **heuristic engine** first (parse tree + EXPLAIN + schema + metrics).
- LLM *after* heuristics to catch cross-signal patterns (stale stats, VACUUM, matviews).
- Zero-shot LLM: high recall, terrible precision (P=0.54). Autoresearch (23 experiments)
  → P=0.86 via prompt/tool chain, model rightsizing, **two-pass self-verification**.
- Eval set: ~100 cases, **30% negatives** (queries that must stay alone).

**Steal:** negatives matter; self-verify before emit; iterate with a sealed scoreboard;
never let LLM replace the hard gate.

### EverSQL / commercial SQL optimizers

- Rewrite + index recommendations; pattern libraries; plan-cost filtering.
- Implicit **shape reuse** (same query form → same advice).

**Steal:** fingerprint + cache verified rewrites; relative cost filters (our precheck).

### pganalyze Query Advisor

- `pg_stat_statements` → opportunity detection → human/advisor loop.
- Workload-centric, not chat-centric.

**Steal:** mine real fingerprints from `pg_stat_statements` into the cache and SFT
export (private loop step 1).

### HarnessSQL (2026)

- Isolated DB sandboxes + hidden execution oracles.
- Teacher rollouts **inside** the target harness; keep only verified trajectories.
- Full-sequence SFT → execution-reward RL.
- Reported: Qwen3-8B 15.5%→45.2% exec accuracy on Spider 2.0-SQLite.

**Steal:** never train on unverified SQL; trajectory format matches serving harness.

### Classic rewrite research (R-Bot, QUITE, LLM-R2, ReSequel)

- Rule selection / retrieval / generate-and-check.
- Equivalence is the bottleneck — sampled checks ≠ bag equality on fixtures.

**Steal:** retrieval of verified demos; repair with plan feedback; don’t trust soft judges alone.

---

## Our “crazy” stack (ordered by ROI)

```
pg_stat / agent SQL
        │
        ▼
┌───────────────────────┐
│ Workload fingerprint  │  ← $0 if hit; negative → keep original
│ cache (pos / neg)     │
└───────────┬───────────┘
            │ miss
            ▼
┌───────────────────────┐
│ Sound rules + precheck│  ← $0 / EXPLAIN-only
└───────────┬───────────┘
            │ miss / fail
            ▼
┌───────────────────────┐
│ Router → cascade      │  flash / oss → Nemotron Ultra
│ best_of + repair      │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Equivalence + ≥1.25×  │  ← hard gate (0 wrong SLA)
└───────────┬───────────┘
            │ accept / incorrect
            ▼
   cache += pos / neg
   SFT/DPO export (optional)
```

### 1. Workload fingerprint cache (shipped)

- Fingerprint = hash of literal-collapsed shape tokens.
- **Positive:** reuse rewrite only if it previously passed verify.
- **Negative:** known-corrupt shapes → abstain (keep original, skip LLM).
- Seed: `.venv/bin/python -c 'from surgeon.eval.workload_cache import seed_from_harness_runs; print(seed_from_harness_runs())'`
- Online learning: accepts from rules/model path append to `.local/training/workload_cache.jsonl`.

**Why it helps:** agentic traffic is heavy-tailed — the same ORM/agent shapes fire
thousands of times. First call pays; the rest are free and still gated historically.

### 2. Cascade + router (in repo)

- Cheap stage first; escalate only when unchanged / failed.
- Cuts median $/case and p95 latency vs always-Ultra.

### 3. Verified RAG

- Retrieve k accepted (query, rewrite) pairs by Jaccard on shape.
- Privacy: store under `.local/`; never upload held-out templates.

### 4. Soft recipes (eval-recipes bridge)

- Shape / abstain / tool-use soft scores for training triage — **not** for shipping.
- Hard gate remains equivalence + speedup.

---

## Fine-tuning — would it make sense? (ROI)

**Yes, as a specialist behind the harness — not instead of it.**

| Question | Answer for us |
| --- | --- |
| When? | After ≥~100–200 *verified* accepts from *customer* workload (deep research: ideal **500–2,000** pairs for LoRA). |
| On what? | Muse Glimmer LoRA (free SFT window) or on-prem; chat rows from accepted turns only. |
| Goal? | Raise **first-pass accept** and cut cascade escalations / repair rounds → lower $/case. |
| Risk? | Open-raw already shows 11 wrongs/98 — FT without gate can memorize bad habits. Result-only rewards have **~33% false-positive** rate (wrong SQL, matching rows on one DB). |
| DPO? | Preferred = accepted rewrite; rejected = incorrect / regression. Needs pairs. |
| RL? | Execution-reward like HarnessSQL — only after SFT + solid sandbox ops. |

**ROI evidence (industry / papers):**

| Signal | Implication for us |
| --- | --- |
| Verified train data +7.2pp; unverified **−7.0pp** (ReViSQL) | Never export non-accepted turns |
| HarnessSQL: Qwen3-8B 15.5%→45.2% exec acc via harness-native SFT+RL | Same verify loop at train & serve |
| Cascade routing: ~50–75% API cost cut | Keep flash→Nemotron; FT fills MEDIUM tier |
| Template cache hits 85–90% of workloads | Cache first; FT only on residual misses |
| EnumGRPO / Quail FinOps: 27×–317× vs naïve agents | Joint plan + abstain beats bigger models |
| Private LoRA: ~7–8× cheaper inference vs large API | Makes sense once VPC / no-deploy-card constraints lift |

**Harness-only wins** for hackathon MVP, OOD schemas, and when the backbone changes weekly (no retrain). **FT wins** for stable private workloads with a verified pool and a need to cut tail Ultra spend.

**How FT helps the pitch**

1. **FinOps:** more $0 cache/rules hits + fewer Ultra calls.
2. **Dialect:** learns customer schema idioms the frontier doesn’t see (and mustn’t).
3. **Safety theater → safety:** specialist proposes; harness still refuses wrongs.
4. **Privacy:** training data stays in-account / VPC; eval_v2 held-out never trains.

**When FT does *not* help**

- Tiny public eval only (overfit to 98 cases).
- Deploying LoRA without payment / without keeping verify=True.
- Replacing rules that already fire correctly.

Current status: Muse Glimmer SFT promoted
(`muse-starter-sl-sql-specialist-20261102-112625`); serverless inference OK;
dedicated LoRA deploy blocked on payment method — harness path does not need it.

---

## Workload patterns → stronger system

1. **Mine** `pg_stat_statements` → top CPU/time shapes → cases.
2. **Run** harness → accept / incorrect / abstain.
3. **Cache** fingerprints (pos/neg).
4. **Export** accepts → SFT; (accept, incorrect) → DPO.
5. **Re-measure** on sealed eval_v2 + customer shadow traffic.
6. **Promote** only if wrong=0 and accept↑ or $/case↓.

This is the private retrain loop (`scripts/private_retrain_loop.py pitch`).

---

## Hackathon scoring hooks

- **Benchmark:** 0 wrong + accept ≥ frontier (harness already ties 57.1%).
- **Business:** agentic boom + private fingerprints + FinOps ($/case collapse via cache/cascade).
- **Tech:** fingerprint cache + cascade + optional Muse SFT flywheel.
- **Demo:** show cache hit ($0) vs raw LLM wrong vs harness accept.
- **Docs:** this file + RESULTS.md.

---

## Deep-research priorities (mapped to us)

From the Nov 2026 synthesis (54 sources):

1. Correctness-gated harness + EXPLAIN — **we have this** (open-harness 57.1% / 0 wrong).
2. Template fingerprint cache — **shipped** (`workload_cache`, seeded 34 pos / 13 neg).
3. Model cascade routing — **in repo**; finish cascade report.
4. LoRA on verified pool (500–2k pairs) — **optional week-2**; Muse SFT already started (~109 rows).
5. Semantic / agentic cache — later (agent boom defense).

Industry parallel: Datadog keeps P≈0.90 heuristics, LLM only after, then autoresearch + self-verify → P=0.86. EverSQL ships rules+AI without FT. HarnessSQL: train *only* on harness-verified trajectories.

## Immediate next builds (priority)

1. ~~Fingerprint cache + pipeline wire~~
2. Replay hit-rate after Nemotron seed; tighten verify on `check_nulls` (Nemotron harness leaked 3).
3. Cascade report once stages complete.
4. Export DPO pairs from `incorrect` vs `accepted` on same case id.
5. Optional: two-pass self-verify prompt (Datadog) before emit when repair=0.
