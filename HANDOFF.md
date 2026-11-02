# Database Surgeon — session handoff

## Demo surface — November 1, 2026

The local demo opens on a white single-column page at http://127.0.0.1:3100. It runs three steps:

1. **Rewrite by diff.** A person pastes one PostgreSQL SELECT, or picks one of five admitted examples. The CopilotKit agent may change that query only through `apply_sql_diff` unified diffs, which render as they stream and apply when a hunk matches. It never pastes a replacement query.
2. **Verify on Postgres.** When the cuts stop, the page calls `POST /api/verify`, which proxies to `POST /verify` on the Python service. Verification runs only when the pasted query is one of the 14 admitted dataset cases. The candidate then goes through the same path as a lab run: the SELECT guard, the read-only role, row checks on 5 fixtures with types enforced, a benchmark of 5 paired runs, the evaluation lock, and the 20% acceptance bar. An incorrect rewrite is never timed. Any other query shows as "not executed".
3. **Next idea.** The agent receives the measured verdict and must call `state_next_idea` once. If it doesn't, the page asks again. "Pursue" repeats the cycle. If pursuing an idea produces no new SQL, the previous measurement stays on screen.

The lab, experiment ledger and dataset registry stay one click away and are unchanged.

Measured during the November 1 browser check, on development data and local synthetic fixtures:

| Case | Original | Rewrite | Rows | Verdict |
| --- | --- | --- | --- | --- |
| `date_filter` | 16.0 ms | 0.23 ms | same | accepted, 69× |
| `nullable_antijoin` | 7.12 ms | 77.7 ms | same | not accepted, slower |
| `correlated_count` | 1.48 ms | 7.17 ms | same | not accepted, slower |

The next steps for the project are unchanged: Fireworks capability checks when access arrives, then held-out templates and repeated trials.

## Latest implementation — November 1, 2026, live workbench

This block supersedes older scope, credential, execution and test status below.
Read docs/WORKBENCH.md for the current runbook and docs/DEPENDENCIES.md before public deployment.

- Next.js/CopilotKit BuiltInAgent workbench is running at http://127.0.0.1:3100; Python API at 127.0.0.1:8765; PostgreSQL at 127.0.0.1:55432. Keep the requested local demo running.
- npm run dev at the root starts/reuses the local app/API. The built app lives in web/. Python backend remains standard-library-only.
- 14 admitted development cases: eight own, six public R-Bot SQL inputs pinned to commit c9c90e5d7867888c3aaba86e4fc9e6d48f53b375; synthetic microfixtures on five schemas. Not an official full-scale benchmark. Duplicate-column Calcite input excluded before inference.
- 50 tests passed with database integration, Next production build/typecheck passed. Final browser checks at 1440/768/390px: zero inspector failures, two contextual warnings. Navigation/14 dataset rows/run dialog/mobile overflow passed; a live chat tool call previously rendered measured evidence.
- A no-cost mock run through the actual Next evaluation API completed: 20261102T043920Z-b019e6. The refreshed report contains 14 runs in eight groups, zero skipped.
- Four distinct Groq credentials configured. Round robin and bounded rotation after explicit 429 only; do not replay uncertain network errors or HTTP 400. Credentials absent from browser bundles/build-traced environment files in final check. Never print values.
- Matched one-attempt all-suite trial: Groq20B 20261102T042033Z-95c12c completed 8/14 accepted, one unsafe candidate rejected, 80.766s; OpenAI gpt-6.1-sol 20261102T042312Z-e6a3b3 completed 8/14, no unsafe candidates, 128.512s. About 37% lower whole-run wall time in one development trial, not held-out superiority. Costs unknown.
- Groq120B 20261102T042154Z-c819b7 failed HTTP400 on calcite_exists, 5/14 accepted, two unsafe candidates rejected, two not attempted. No diagnosis inferred, no automatic replay.
- Offline export scripts/export_training.py produced 23 deduplicated SFT seeds in 11 template groups under .local/training/. They require label/rights/split review; ready_for_training=false, on_policy_rl_eligible=false. No training ran.
- CopilotKit onboarding CLI selected licensed Intelligence; stopped before signin/provisioning. Direct official Built-in Next.js setup works without that stack. Native React tools provide generative UI; no MCP Apps server is configured. Chat uses Groq20B, read-only evidence tools, max three model steps; no automatic page-load inference.
- Installed dependency audit has unresolved transitive findings; app remains loopback-only, no public deployment. No forced incompatible overrides. Research sources and larger architecture plan remain in docs/.
- Fireworks credentials/access still pending. Next: capability smoke tests, independent held-out templates/repeated trials, controlled routing ablations, then reviewed SFT data. Do not promise improvement before measurement.

## Planning update — November 1, 2026, research and Fireworks pipeline

The user requested persistent research, a sophisticated low-call open-model pipeline, training data collection, and a repository-grounded benchmark plan for Fireworks access expected November 2.

Read docs/RESEARCH.md, docs/ARCHITECTURE.md, and docs/BENCHMARKS.md. They preserve 94 source references, specify routing/caching/verification/training/release gates, and inspect actual SQL/schema/data artifacts. benchmarks/manifest.template.json lists 11 representative inputs with lineage and prerequisites; it is NOT_FROZEN and executable=false. It is not a benchmark runner.

Current Fireworks documentation: managed RFT accepts no new jobs; use Training API for new RL. Serverless Training API supports selected LoRA models and checkpoint sampling. Ordinary production serving of trained/custom models is a separate deployment decision. Account/model/method/quota/prices remain unverified. Pin SDK/cookbook and capture exact rollout token/logprob/mask ancestry before RL.

The plan does not promise a frontier-model win. It proposes quality-constrained cost/latency targets and gates; promotion depends on evidence. Existing three-case results remain development observations. No new public benchmark, model call, training job, package installation, or deployment was executed for this documentation task.

Next priorities: model capability discovery; immutable benchmark inputs/data; ordered/type result contracts; AST-aware policy (current guard rejects legitimate SUBSTRING ... FOR); then bounded rules/routing and training exports. Keep public reference rewrites out of model inputs and final evaluation. R-Bot Q17 variants and QUITE repeated templates must stay grouped; SQL-RewriteBench public release is reproduction/development, not blind test data.

## Latest verified execution — November 1, 2026, 18:39 PT

This section supersedes the execution block and credential/model status below.
Docker, localhost PostgreSQL and provider APIs work with approved execution outside
this session's read-only sandbox. Do not change socket permissions.

- Seeded all five fixture schemas, preserving existing rows; 50,000 benchmark orders.
- Fixed preflight collation lookup: read pg_database.datcollate instead of the
  unsupported current_setting('lc_collate').
- All 39 tests passed with SURGEON_TEST_DATABASE=1; no skipped integration tests.
- Doctor passes under surgeon_reader; PostgreSQL remains healthy on port 55432.
- OpenAI and Groq discovery and inference both succeeded. OPENAI_MODEL is now
  gpt-6.1-sol in .env.local. Never display credentials. Fireworks still has no key.
- Mock run 20261102T023654Z-071cfc completed; unsafe NULL rewrite rejected.
- Matching one-shot runs (4096 output tokens, five timing pairs):
  OpenAI 20261102T023702Z-8bb361 accepted 2/3;
  Groq 20261102T023730Z-932e89 accepted 1/3 and rejected one incorrect rewrite.
- Matching up-to-three-attempt runs with the same output/timing budgets:
  OpenAI 20261102T023740Z-f9137b accepted 2/3;
  Groq 20261102T023819Z-4e6651 accepted 2/3, repairing its incorrect anti-join
  after evaluation feedback. Corrected anti-join median: 7.117 ms to 0.087 ms.
- All four live runs completed with zero errors. OpenAI cost remains unknown
  because prices are unset. Configured Groq estimates total $0.00315060.
- results/report.md and results/report.json contain six runs in four groups;
  matched providers share groups; mock and legacy results remain separate.
- All evidence is on public development fixtures, not held-out or universal
  equivalence evidence. Repeated independent trials are needed to compare quality.

Rerun the complete baseline: bash scripts/first_baseline.sh
Generate the offline report: python3 -m surgeon report
Next: configure Fireworks access when available; add held-out evaluation and trials.

Preparing for Fireworks: Deploy with Microsoft & NVIDIA, November 2, 2026.
The user chose Database Surgeon. Continue this project rather than restarting ideation.
The latest request is to understand and improve the project continuously; prioritize
reliable evaluation and a credible demo. A preference question was sent, with no answer yet.

## Product

Open models propose faster PostgreSQL SELECT rewrites; one evaluator rejects
incorrect or slower candidates. Compare against an explicitly identified closed
frontier model under matching budgets. Groq is the initial open-model provider;
Fireworks is planned for the event. OpenAI supplies the closed baseline.

Python 3.9+ standard library only. Docker Compose owns Postgres 16 on localhost
port 55432. No UI is required by the current scope.

## Implemented in this session

- Crash-safe atomic JSON artifacts, per-attempt checkpoints and final run states.
- Preserve successful model output/usage before SQL evaluation, including interruption.
- Exclusive evaluation lock to avoid overlapping benchmark processes.
- Preflight requires surgeon_reader with no elevated role flags; validates fixture
  availability and all selected originals before any paid request.
- Manifest fingerprints for evaluator code, seed definitions, actual fixture
  contents, indexes, relevant server settings and selected cases; records prices.
- Five fixture schemas: bench, check_a, check_b, check_nonnull, check_empty.
  Existing three development query families remain unchanged.
- Empty-result column names/order checked via psql gdesc; exact decimal parsing;
  duplicate/NULL-aware bags; quoted disallowed-function guard and session/sequence
  mutation rejection; backslashes rejected conservatively.
- Timing variability: paired reductions, candidate win rate and median absolute deviations.
- `python3 -m surgeon report`: offline grouped Markdown report and JSON index.
  Legacy runs are isolated and marked unverified. Mock runs cannot share groups
  with real-provider experiments. No automatic winner is declared.
- `python3 -m surgeon watch --interval 60`: exclusive continuous unit + mock checks,
  machine-readable status and logs under .local; no paid calls or source changes.
- `python3 -m surgeon doctor --json`: explicit readiness and failure exit status.
- `bash scripts/check_local.sh`: real database + integration + mock + report, no APIs.
- Compose restart policy unless-stopped; first_baseline.sh includes readiness/report.

## Current execution block

The user changed Docker socket user settings and asked to retry. We retried.
Docker context is desktop-linux; the socket and its owner are correct, and
/var/run/docker.sock points to the same socket. Nevertheless this Codex session
still gets permission denied on the socket, and psql to 127.0.0.1:55432 fails
with Operation not permitted. These are current session sandbox restrictions;
do not claim the Docker service is stopped. Do not change socket permissions.
A local initdb attempt also failed because shared memory creation is restricted;
initdb cleaned up its own partial cluster. No extra Postgres process was started.

Restart the Codex session with Docker socket and localhost access, or run
`bash scripts/check_local.sh` in the user's normal terminal. Live verification is
still required for the new fixtures and psql gdesc path. Do not claim these passed.

## Credentials

OPENAI_API_KEY and GROQ_API_KEY are present in .env.local. Never print their values.
OPENAI_MODEL is now gpt-6.1-sol. GROQ_MODEL is openai/gpt-oss-120b (OPEN weights).
Fireworks has no key yet. This agent did not initiate paid calls; an external
process wrote successful OpenAI/Groq runs while this session was active.
Provider API behavior was not changed in this session.

## Evidence and next actions

Final local unit suite: 29 passed, 10 database integration tests skipped.
An explicit integration attempt failed at setup with Operation not permitted;
these tests cannot be claimed as passed from this session.
Bash syntax checks and Compose configuration validation pass.
The one-cycle watcher passes unit tests and exits 1 when it cannot evaluate.
It records check_failed with the exact cause (database denied or another evaluation
holding the lock). No background watcher was left running here.
The original results/20261102T014223Z-48856c run is a mock fixture experiment and
uses the older three-instance evaluator. It cannot validate the updated harness.

Fresh externally written runs DO exercise the new five-schema evaluator, including
psql gdesc, before any model call. These artifacts completed without errors:

- 20261102T023654Z-071cfc: updated mock, 1/3 accepted, unsafe NULL rewrite rejected.
- 20261102T023702Z-8bb361: OpenAI one-shot, 2/3 accepted.
- 20261102T023730Z-932e89: Groq one-shot, 1/3 accepted, unsafe NULL rewrite rejected.
- 20261102T023740Z-f9137b: OpenAI three-attempt budget, 2/3 accepted.
- 20261102T023819Z-4e6651: Groq three-attempt budget, 2/3 accepted; feedback repaired
  its NULL-sensitive rewrite on the second attempt.

results/report.md and report.json have been refreshed: six runs, four comparison
groups, zero unreadable artifacts. Costs remain unknown for OpenAI because price
inputs are missing. These are development trials, not a final model ranking.
Additional edge worth testing: date_filter uses to_char without era; OpenAI's
rewrite explicitly handles BC dates, while the current fixtures only use AD dates.

1. Run `bash scripts/check_local.sh` with Docker and localhost access.
2. Address any real-database failures before paid inference.
3. Confirm the externally selected baseline and configure its price inputs.
4. Repeat the matching one-shot and iterative runs for timing/model variability.
5. Generate the offline report; compare matching groups, keep mock evidence separate.
6. Add independently held-out query families and immutable split manifests before
   claiming final model-quality results. Current fixtures remain public development data.

Finite execution tests do not prove universal SQL equivalence. Row ordering,
type-level equivalence, volatile functions and arbitrary SQL dialects remain outside
the pilot. Timing variation and machine load require repeated trials.
