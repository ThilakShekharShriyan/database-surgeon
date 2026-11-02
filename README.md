# Database Surgeon

**Learning the project:** [end-to-end study packet](docs/STUDY_MATERIALS.md) ·
[pipeline and remaining work](docs/PIPELINE_PLAYBOOK.md) ·
[presentation Q&A](docs/STUDY_CHEATSHEET.md). The packet separates implemented
features, captured measurements and claims that still need independent evidence.

**Built during the hackathon — Nov 2, 2026 (from ~10:45am PT).** All product code,
eval harness, Fireworks/NVIDIA stack, docs, and demo in this repo are from that day.

Verified PostgreSQL SQL rewrite: open models + surgical harness beat a blind frontier
baseline on a **fixed 171-case eval** (98 dev + 73 template-held-out), with **0 wrong
queries returned**. A harness is enough — fine-tuning is optional.

Live demo (Judge pitch · Live surgery · Experiments ledger): **http://127.0.0.1:3100**

**Judge research write-up:** [docs/FORGE_RESEARCH.md](docs/FORGE_RESEARCH.md) · scoreboard: [docs/ADVANTAGES.md](docs/ADVANTAGES.md) · measured results: [docs/RESULTS.md](docs/RESULTS.md) · research UI: `/research`

**Demo video:** [docs/DEMO_VIDEO.md](docs/DEMO_VIDEO.md) · stage tabs `bash scripts/open_demo_for_recording.sh` · record `./scripts/record_demo.sh --project="DBSurgeon"` · pick take `--pick`

## Eval v2 — reproduce every benchmark (rubric 40% + 5% docs)

```sh
# Same cases & scoring for every system. Held-out requires freeze first.
.venv/bin/python -m surgeon.eval freeze rules-only frontier-raw oss20b-raw oss20b-harness cascade-surgeon
.venv/bin/python -m surgeon.eval run frontier-raw --split dev --trials 3 --max-usd 8
.venv/bin/python -m surgeon.eval run oss20b-raw --split dev --trials 3 --max-usd 8
.venv/bin/python -m surgeon.eval run oss20b-harness --split dev --trials 1 --max-usd 12
.venv/bin/python -m surgeon.eval run rules-only --split heldout --trials 1
.venv/bin/python -m surgeon.eval run frontier-raw --split heldout --trials 1 --max-usd 5
.venv/bin/python -m surgeon.eval report --split dev
.venv/bin/python -m surgeon.eval report --split heldout
bash scripts/site/sync.sh
```

| Version | Registry name | What it is |
|---|---|---|
| v0 | `frontier-raw` | Closed baseline, blind |
| v1 | `oss20b-raw` | Open raw (shows corruption cliff) |
| v2 | `oss20b-harness` / `open-harness` | EXPLAIN + retrieval + verify + repair |
| v3 | `cascade-surgeon` | sqlglot → Fireworks Nemotron / open harness |

Traces: `benchmarks/eval_v2/runs/<system>/{dev,heldout}_t*.jsonl` · freeze file: `benchmarks/eval_v2/FROZEN.json`.

Fireworks + NVIDIA Nemotron prize stack (paste `FIREWORKS_API_KEY` first):

```sh
bash scripts/probe_fireworks.sh && bash scripts/run_fireworks_evals.sh
```

## Private retrain loop (agentic Postgres / Eval Recipes)

Workloads and schemas stay local. [microsoft/eval-recipes](https://github.com/microsoft/eval-recipes)-shaped
recipes soft-score turns; the surgical harness remains the hard gate. Only
**accepted** rewrites become SFT — optional free Muse Glimmer LoRA on Fireworks
(through 2026-11-30) or on-prem MLX/Vast.

```sh
.venv/bin/python scripts/private_retrain_loop.py plan
.venv/bin/python scripts/private_retrain_loop.py score-runs
.venv/bin/python scripts/private_retrain_loop.py export-sft
bash scripts/finetune/fireworks_sft.sh check
# Managed Datasets upload may be disabled on new accounts — prefer Serverless:
bash scripts/finetune/muse_glimmer_serverless.sh plan
# bash scripts/finetune/muse_glimmer_serverless.sh launch   # free Muse Glimmer LoRA SFT thru Nov 30
```

Fireworks Docs MCP is in `.cursor/mcp.json` (`https://docs.fireworks.ai/mcp`) — reload Cursor MCP to query docs live. Account already has preloaded Datasets `onboarding-prompt-router` / `onboarding-cord-receipts`; custom `sql-rewrite-sft-v1` needs upload access or the serverless local-file path above.

## Live workbench and expanded dataset

Open http://127.0.0.1:3100 or run `npm run dev` from `web/`. See [WORKBENCH.md](docs/WORKBENCH.md) for the CopilotKit lab path, key rotation, and local-only deployment limits.

## Research and build plan

- [**Forge-style research write-up (judge packet)**](docs/FORGE_RESEARCH.md) — six-step narrative + McNemar/bootstrap
- [Paired stats regenerator](scripts/compute_paired_stats.py) → `benchmarks/eval_v2/results/paired_stats.json`
- [Research, repository reuse guide, and all references](docs/RESEARCH.md)
- [Architecture, routing, data collection, training, and release gates](docs/ARCHITECTURE.md)
- [Repository datasets, inspected SQL, and benchmark protocol](docs/BENCHMARKS.md)
- [Unfrozen benchmark onboarding manifest](benchmarks/manifest.template.json)

These documents include the longer-term build plan. Six source-pinned public SQL inputs now run on synthetic fixtures alongside eight local inputs; see WORKBENCH.md for the implemented scope. Advanced routing and training remain planned. The larger manifest template is deliberately non-executable until its sources, data, contracts, and budgets are admitted.

## Start locally

Start with database-only verification. It checks the real database, runs the
integration suite, exercises the fixed mock rewrites and writes a report.
It does not call any model API:

```sh
bash scripts/check_local.sh
```

For the complete initial check and one-shot comparison, set an accessible exact
closed model as `OPENAI_MODEL` in `.env.local`, then run from a terminal with Docker
and network access:

```sh
bash scripts/first_baseline.sh
```

The script validates the real database before paid requests, lists accessible
provider models, and stops if the closed model is unset. An explicit model may
also be passed as its first argument. This is a development comparison only.
The optional argument is a model ID; flags such as `--yolo` are rejected before
database setup. Use `--help` for usage.

If discovery fails, the script stops before paid inference. For example, a Groq
HTTP 403 during discovery means access to its model-list endpoint was denied;
it does not establish whether generation or structured output works. After
checking the key's permissions, account restrictions and network filtering,
check discovery on its own before rerunning the full script:

```sh
python3 -m surgeon models groq
```

```sh
cp .env.example .env
docker compose up -d --wait
python3 -m surgeon seed
python3 -m surgeon doctor
python3 -m unittest discover -s tests -v
python3 -m surgeon run --provider mock
```

Run real database integration checks after seeding:

```sh
SURGEON_TEST_DATABASE=1 python3 -m unittest discover -s tests -v
```

The database tests check date boundaries, empty groups, NULL-sensitive rejection,
empty-result column names, exact decimals, actual read-only role enforcement and
server benchmark timings. They skip when
the explicit test flag is absent; a unit-only pass does not establish database readiness.

Put `OPENAI_API_KEY` and `GROQ_API_KEY` in `.env`. Keys and results are ignored by
Git. The mock uses fixed development candidates, including a deliberately unsafe
NULL-sensitive anti-join rewrite. Mock results are never model-performance evidence.

Discover models available to each account, then set an exact `OPENAI_MODEL` in `.env`.
The closed model should meet the event's frontier-baseline requirement; GPT-OSS
served by Groq is an **open-weight model**, even though its model ID starts `openai/`.

```sh
python3 -m surgeon models openai
python3 -m surgeon models groq
python3 -m surgeon run --provider openai --attempts 1
python3 -m surgeon run --provider groq --attempts 1
python3 -m surgeon run --provider openai --attempts 3
python3 -m surgeon run --provider groq --attempts 3
```

Use matching attempt/output budgets for harness comparisons. Also compare each
model's one-shot and iterative results to isolate harness effects. All model calls
are explicit; no live calls happen during tests, seeding or mock runs. Explicit Groq HTTP 429 rejections may rotate across up to four distinct configured keys, as authorized; every HTTP attempt is recorded. Other failed API calls are not replayed.

When Fireworks access is available, add `FIREWORKS_API_KEY`, discover accessible models and run:

```sh
python3 -m surgeon models fireworks
python3 -m surgeon run --provider fireworks --attempts 3
```

## Continuous local checks

Once the database is ready, keep checking the project with:

```sh
python3 -m surgeon watch --interval 60
```

Each cycle runs the unit suite and a fresh mock database benchmark. This command
only uses the mock provider. It never makes paid inference calls or changes source
code. Stop it with Ctrl-C or SIGTERM. To check a single cycle, add `--cycles 1`.
The interval is a delay after each completed cycle; checks do not overlap.

Status, the process ID, last successful check and logs live under `.local/`:

```sh
cat .local/watch.json
cat .local/watch-tests.log
cat .local/watch-benchmark.log
```

For a background process in your own terminal:

```sh
mkdir -p .local
nohup python3 -m surgeon watch --interval 60 > .local/watch.log 2>&1 &
```

The watcher holds an exclusive lock, and each evaluation holds a separate lock to
avoid concurrent benchmarks affecting timings. Database failures are recorded and
checked again on the next cycle. A finite check exits nonzero when its last check
failed. The loop runs while its process and computer remain running. Its artifacts
accumulate in `results/`; it does not delete earlier experiments. Compose restarts
Postgres after Docker restarts unless you explicitly stopped the service.

## Inspect and compare evidence

```sh
python3 -m surgeon doctor --json
python3 -m surgeon report
```

`doctor` returns a nonzero exit status if the database, restricted role or fixtures
are unavailable. Its output reports credential presence without printing keys.
`report` builds `results/report.md` and a companion JSON index entirely offline.
Reports group runs only when selected cases, actual fixture contents, indexes,
recorded database settings, evaluator code and inference/timing budgets match.
Mock experiments are kept separate. Older artifacts lack this metadata and are
labeled legacy/unverified in their own groups. Matching groups do not account for
hardware load or all server configuration, and do not establish a winner.

New run manifests record `running`, `completed`, `failed` or `interrupted` state.
Artifacts are replaced atomically; successful API output and usage are checkpointed
before SQL evaluation. Interruptions retain that output and mark unfinished
attempts. Runs with evaluation/API errors exit nonzero. No incomplete-cost estimate
is presented as a complete bill.

## Evaluation contract

- Default pilot: three development queries covering date filtering, correlated counting and NULL-sensitive anti-join. Add --suite all for the 14-case development lab, including six public SQL inputs on synthetic microfixtures.
- A 50,000-order performance instance and four smaller correctness instances,
  including no-NULL and empty-order fixtures.
- Unordered result bags: column names/order, duplicates and NULL values matter,
  even for empty results. Exact decimal values are preserved.
- Lab/all runs also compare output types. Correctness checks run before warmups and alternating paired timing trials.
- The default accepts a candidate only at >=20% median execution-time reduction.
- Postgres execution timing excludes client/process overhead. Total run wall time is separate.
- Timing artifacts include individual samples, paired reductions, win rate and
  median absolute deviations so variability is visible.
- Exact usage, returned model IDs, timings, attempts, price inputs, workload and
  evaluator hashes, actual fixture fingerprints and database metadata are saved in `results/`.
- Prices are manually configured USD/million tokens. Missing prices yield null, never zero.
- Estimated API cost excludes database compute, idle time and provider-specific discounts.

**This is a development pilot, not final benchmark evidence.** Cases and correctness
fixtures are public; no held-out claim is made. Before submission, add independently
held-out query families/instances, an immutable split manifest and repeated trials.
Finite execution and output-type checks are not a proof of SQL equivalence. Ordered results, general type-level
equivalence, volatile functions and arbitrary SQL dialects are outside this pilot.
Very fast queries have noisy timing; do not select a winner from one run.

## Database boundary

Compose creates only a project-owned database, bound to localhost port 55432.
Model candidates execute under `surgeon_reader`, with SELECT grants, read-only defaults,
statement timeouts and a conservative SQL guard. DDL/data generation uses only the
Compose service's admin connection. Never point this prototype at a production database.
The model cannot create indexes; index tuning and workload-wide write costs are deferred.

Stop the container without deleting its volume:

```sh
docker compose down
```

## Documentation checked

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://console.groq.com/docs/openai
- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/models
- https://docs.fireworks.ai/guides/response-api

Groq's documented strict-JSON models include `openai/gpt-oss-120b` and
`openai/gpt-oss-20b`. Access and prices must be verified for the account used.
