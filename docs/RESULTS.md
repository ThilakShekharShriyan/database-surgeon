# Results — Database Surgeon (eval v2)

**Rubric:** 40% Benchmark (171 fixed cases) · 25% Business · 20% Tech · 10% Demo · 5% Docs. *Harness enough; fine-tuning optional.*

**Judge research write-up:** [FORGE_RESEARCH.md](FORGE_RESEARCH.md) · **all-round scoreboard:** [ADVANTAGES.md](ADVANTAGES.md) · crazy harness: [CRAZY_HARNESS.md](CRAZY_HARNESS.md) · priors: [CRAZY_HARNESS_DEEP_RESEARCH.md](CRAZY_HARNESS_DEEP_RESEARCH.md)

**Full bench (durable):** `bash scripts/run_all_advantages_bench.sh` · launchd `com.databasesurgeon.fullbench` · live log `.local/eval_v2/all_advantages.out`

**Live Fireworks stack:** `glm-5p3-flash` → **NVIDIA `nemotron-3-ultra-nvfp4`** · `gpt-oss-120b`.

## Frontier hardening (critique → fixes)

| Gap | Status |
| --- | --- |
| Null-fixture verify leak | **Fixed** — harness verify now uses full `EVAL_SCHEMAS` (incl. `check_nulls`). Old incorrect returns now fail verify (`stage=check`) → abstain. |
| Held-out open-harness | **Running** via `scripts/run_frontier_hardening.sh` |
| Cache hit-rate A/B | **Done (offline)** — 68.4% hit rate on 98-dev; ~**3.16×** estimated optimizer LLM latency with warm cache (see `.local/training/cache_ab_report.json`). Live `cache-rules` / `open-harness-nocache` in flight. |
| Specialist LoRA vs base | **Queued** — Muse specialist `accounts/thilaksshriyan-0lo68/models/muse-starter-sl-sql-specialist-…` (probe may need deploy). |
| Real `pg_stat_statements` slice | **Done** — extension enabled; 38 statements replayed; export at `.local/training/pg_stat_slice.jsonl` (parameterized fingerprints). |
| Optimizer latency p50/p95 | **Done in reporter** — `latency_*` + `optimizer_llm_*` + `optimizer_verify_*` in `surgeon.eval report`. |

## Headline (dev, same scoring)

| Version | System | n | Accept | Wrong | $/case | Notes |
|---|---|---:|---:|---:|---:|---|
| v0 | frontier-raw | 98 | **56.1%** | **0** | $0.0027 | closed baseline |
| v1 | open-raw (FW) | 98 | **46.9%** | **11** | $0.0004 | corruption cliff |
| v2 | **open-harness** (FW) | 98 | **57.1%** | **0** | $0.0028 | ties/beats frontier, **0 wrong** |
| v2f | **fw-fast-harness** | 98 | **57.1%** | **0** | $0.0074 | flash + strict path |
| v2n | fw-nemotron-harness | 98 | 60.2% | 3 | $0.0114 | *pre-strict* — archived & re-running |
| v3 | cascade-surgeon | 98 | 62.2% | 2 | $0.0156 | *pre-strict* — re-running after stages |
| — | rules-only | 98 | 14.3% | 0 | $0 | sound rules floor |
| — | cache A/B (offline) | 98 | — | — | — | **68%** fingerprint hit → **3.16×** LLM latency |

**Pitch:** Open-raw is cheap but returns **11 wrong** queries. The surgical harness (full-fixture verify) drives wrong→**0** and matches/beats frontier accept. Workload fingerprints cut optimizer LLM time ~3× on repeated agent shapes. Nemotron/cascade accept↑ only ships after strict re-run proves 0 wrong.

## Reproduce

```bash
# Critique-gap closer (held-out, strict re-runs, cache, specialist, reports)
bash scripts/run_frontier_hardening.sh

# Offline cache A/B + pg_stat slice
.venv/bin/python scripts/measure_cache_ab.py
PGUSER=surgeon_admin PGPASSWORD=local-admin-only .venv/bin/python scripts/pg_stat_workload_slice.py

.venv/bin/python -m surgeon.eval report --split dev
.venv/bin/python -m surgeon.eval report --split heldout
```

Demo: http://127.0.0.1:3100
