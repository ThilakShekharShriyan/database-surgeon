# Module map (production layout)

## Layers

| Package | Responsibility | Key types |
|---------|----------------|-----------|
| `surgeon.sql` | SQL text normalize / equality | `normalize`, `same_sql` |
| `surgeon.database` | Postgres I/O, guard, equivalence | `Database`, `validate_sql` |
| `surgeon.settings` | Process config from env | `Settings`, `get_settings()` |
| `surgeon.lab` | Pinned microfixture demo cases | `suite_cases` |
| `surgeon.eval.*` | Frozen eval v2 (systems, judge, router, report) | `System`, `SystemConfig`, `Judge`, `Client` |
| `surgeon.service` | Loopback HTTP for demo/lab | `/optimize`, `/verify` |
| `surgeon.providers` | Legacy lab Provider (Groq/OpenAI HTTP) | still used by CLI lab runs |
| `scripts/overnight` | Ops: LaunchAgents, Vast, finish hooks | `vast_manager`, `state` |

## Two loops (do not merge)

1. **Online serve** — `cascade-local` / `/optimize`: rules → local model, verify, abstain.
2. **Offline measure** — `python -m surgeon.eval run …`: frozen cases, hidden fixtures, CIs.

Training reads verified traces from (2); it never trains on held-out.

## OOP style we use

- **Dataclasses** for immutable config (`SystemConfig`, `Settings`).
- **Classes with one job**: `System` (generate), `Verifier`/`Judge` (check), `Client` (LLM), `Database` (IO), `LearnedRouter` (route).
- **Functions** for pure transforms (normalize, metrics, rules).
- Prefer **composition** (cascade = list of `SystemConfig`) over inheritance.

## Dual report roots (do not confuse)

| UI / CLI | Reads | Meaning |
|----------|-------|---------|
| `python -m surgeon.eval report` / site sync / `/frontier` | `benchmarks/eval_v2/results/` | **Canonical** measured systems |
| Lab `python -m surgeon report` / `/snapshot` | `results/` | Older workbench lab runs |

Pitch and Pages use **eval_v2 only**.

## Dead / legacy (cleanup queue)

| Item | Status | Action |
|------|--------|--------|
| `ollama-qwen*:raw` runs | Measured once | Keep artifacts; do not re-run |
| `ollama-qwen35-2b-raw/` | Hung, 0 lines | Quarantine; never re-register |
| `com.databasesurgeon.rest` full queue | Superseded by gptoss+vast+finish | Leave unloaded |
| `scripts/overnight/continue_after_harness.sh` + `eval_pipeline.sh` | Collides with agents | Do not start while gptoss/vast/finish run |
| `surgeon/reporting.py` vs `eval/report.py` | Both live | Lab vs eval_v2 — keep until lab CLI removed |
| `providers.Provider` vs `eval.llm.Client` | Dual HTTP stacks | Long-term: Client only; Provider stays for lab CLI |
| `router.CASCADES["cascade-local"]` | Must match registry | Prefer `ollama-gpt-oss-20b-harness` |

## Production workload knobs

Read via `Settings`: DB timeout, `min_reduction`, demo system name, local models, Vast $/hr and image.
Single evaluation lock (`artifacts.evaluation_lock`) serializes timing so CI measurements stay comparable.
