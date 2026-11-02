# Database Surgeon

**Agents ask models to “make this SQL faster.” Without a harness, that’s a trap.**

Coding agents and copilots don’t open `EXPLAIN` — they prompt a model and ship the rewrite. Query volume keeps compounding as fleets grow (retries, tool loops, overnight jobs), so blind rewrites burn warehouse CPU, API dollars, tokens, **and** accuracy.

On our locked 98-case bench, open-raw still “accepts” **46.9%** of rewrites and returns **11 wrong** answers. Looks quicker. Corrupts results. Then the agent retries.

**The harness is the product:** same open model, verify-or-abstain — accept only if sealed fixtures match **and** SQL is ≥20% faster; else keep the original.

| System | Accept | Wrong | $/case | Optimizer p50 |
| --- | ---: | ---: | ---: | ---: |
| open-raw (baseline) | 46.9% | **11** | $0.0004 | 2.4s |
| frontier-raw | 56.1% | 0 | $0.0027 | 3.8s |
| **open-harness** | **62.2%** | **0** | **$0.0020** | **2.9s** |

One stack, four knobs: **latency · cost · tokens · accuracy**.

---

## Live research site

**https://thilakshekharshriyan.github.io/database-surgeon/**

Static graphs, McNemar / bootstrap tests, and the judge write-up — no API keys. Source lives in [`site/`](site/).

Local demo UI: `http://127.0.0.1:3100` · research board also at `/research` after `npm run dev` in `web/`.

---

## What this is

Hackathon build (Nov 2, 2026) for Forge × Fireworks × NVIDIA. Verified PostgreSQL SQL rewrite: open models + a surgical harness beat a blind frontier baseline on a fixed eval (98 dev + 73 template-held-out), with **0 wrong queries returned**. A harness is enough — fine-tuning is optional.

| Layer | Registry name | Role |
| --- | --- | --- |
| Baseline | `open-raw` / `oss20b-raw` | Blind model rewrite (corruption cliff) |
| Product | `open-harness` / `oss20b-harness` | EXPLAIN + retrieval + verify + repair |
| Cascade | `cascade-surgeon` | sqlglot → Fireworks Nemotron / open harness |
| Closed ref | `frontier-raw` | Optional closed baseline |

---

## Docs

| Doc | Why open it |
| --- | --- |
| [docs/FORGE_RESEARCH.md](docs/FORGE_RESEARCH.md) | Judge packet — problem → baseline → harness → stats |
| [docs/ADVANTAGES.md](docs/ADVANTAGES.md) | Multi-stat scoreboard |
| [docs/RESULTS.md](docs/RESULTS.md) | Measured eval_v2 traces |
| [docs/STUDY_MATERIALS.md](docs/STUDY_MATERIALS.md) | End-to-end study packet |
| [docs/WORKBENCH.md](docs/WORKBENCH.md) | Live CopilotKit lab |
| [docs/DEMO_VIDEO.md](docs/DEMO_VIDEO.md) | Recording / stage tabs |

---

## Reproduce the bench

```sh
# Same cases & scoring for every system. Held-out requires freeze first.
.venv/bin/python -m surgeon.eval freeze rules-only frontier-raw open-raw open-harness cascade-surgeon
.venv/bin/python -m surgeon.eval run open-raw --split dev --trials 1 --max-usd 8
.venv/bin/python -m surgeon.eval run open-harness --split dev --trials 1 --max-usd 12
.venv/bin/python -m surgeon.eval report --split dev
bash scripts/site/sync.sh   # refresh site/data for github.io
```

Fireworks + Nemotron (paste `FIREWORKS_API_KEY` first):

```sh
bash scripts/probe_fireworks.sh && bash scripts/run_fireworks_evals.sh
```

Traces: `benchmarks/eval_v2/runs/<system>/` · freeze: `benchmarks/eval_v2/FROZEN.json`.

---

## Start locally

Database-only check (no model API):

```sh
bash scripts/check_local.sh
```

Full stack:

```sh
cp .env.example .env          # OPENAI_API_KEY / FIREWORKS_API_KEY / GROQ_API_KEY
docker compose up -d --wait
python3 -m surgeon seed
python3 -m surgeon doctor
python3 -m unittest discover -s tests -v
cd web && npm run dev         # http://127.0.0.1:3100
```

Integration tests against real Postgres:

```sh
SURGEON_TEST_DATABASE=1 python3 -m unittest discover -s tests -v
```

One-shot closed vs open comparison (needs `OPENAI_MODEL` in `.env.local`):

```sh
bash scripts/first_baseline.sh
```

---

## Private retrain (optional)

Accepted rewrites only become SFT. Soft scores via [eval-recipes](https://github.com/microsoft/eval-recipes)-shaped recipes; the harness stays the hard gate.

```sh
.venv/bin/python scripts/private_retrain_loop.py plan
.venv/bin/python scripts/private_retrain_loop.py export-sft
bash scripts/finetune/muse_glimmer_serverless.sh plan
```

---

## Honest caveats

- Harness vs open-raw accept gain is significant (McNemar + template-cluster bootstrap).
- Harness vs frontier accept: point estimate favors us; CI still includes 0 — we claim open-stack competitiveness plus the raw-open safety story, and we beat frontier on **$/case** and **optimizer p50**.
- Held-out harness coverage is thinner than dev; see Step 6 in the Forge write-up.

Built in one day. Material use of a Cursor agent. Pre-existing work: none (`docs/HACKATHON.md`).
