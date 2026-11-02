# Local workbench: running, data, and verified scope

Updated November 1, 2026 PT (November 2 UTC).

## Open the app

[Database Surgeon workbench](http://127.0.0.1:3100).

The Next.js UI and Python evaluator API run locally:
- UI: 127.0.0.1:3100
- Evaluator API: 127.0.0.1:8765
- PostgreSQL: 127.0.0.1:55432

The app is bound to loopback. It has not been deployed publicly.

From the project root, start/reuse the local stack:

~~~sh
npm run dev
~~~

For separate terminals:

~~~sh
python3 -m surgeon.service --port 8765
cd web
npm start
~~~

npm start serves the built app. Use npm run build in web/ after changes, or npm run dev there for development.

## What works

- Live artifact-backed experiment selector and query queue.
- Original/candidate SQL, rationale, correctness state, raw-derived median timings and win rate.
- Completed comparable model runs plus a ledger retaining failed, legacy and mock runs.
- Dataset registry, source commit, structural lineage and a documented unsupported public query.
- Bounded evaluation dialog: provider/model allowlist, up to three candidate attempts/case, maximum 42 candidate generations/run, fixed output and timing budgets.
- Server-side provider keys; same-origin mutation routes; loopback evaluator service; chat input size/count limits.
- CopilotKit v2 BuiltInAgent using Groq GPT-OSS 20B, custom provider and explicit frontend tools.
- A read_evidence tool reads current measurements; show_query opens real query evidence and renders a native UI card.
- The assistant cannot execute SQL, modify files or launch evaluations. Evaluation actions stay on explicit controls.
- No model call is made just to load the workbench. Chat inference starts when the user submits a prompt or suggestion.
- Failed/unknown results and missing costs are displayed explicitly.

The old guided onboarding command was run with the supplied run ID. It selected a larger licensed Intelligence local stack. We stopped that route before sign-in/provisioning and implemented the direct official Next.js Built-in quickstart instead. No Intelligence stack, external chat storage, or cloud deployment was created.

Official setup references:
- [Built-in quickstart](https://docs.copilotkit.ai/quickstart)
- [Model selection](https://docs.copilotkit.ai/model-selection)
- [Frontend tools](https://docs.copilotkit.ai/reference/v2/hooks/useFrontendTool)
- [MCP Apps](https://docs.copilotkit.ai/generative-ui/mcp-apps)
- [Generative UI patterns](https://www.copilotkit.ai/generative-ui)

MCP Apps are optional remote HTML/UI-resource tools, requiring an actual MCP server. This build uses native React frontend tools to keep SQL/evidence presentation under app control. It does not claim an MCP Apps server integration.

## Dataset admitted today

14 SQL inputs on five deterministic synthetic fixture schemas:

- Three existing development cases.
- Five additional locally authored cases.
- Six public R-Bot inputs: two TPC-H Q17 parameter variants and four Calcite semantic tests.
- Performance fixture adds 50,000 line items and 10,000 employee rows alongside 50,000 existing orders.
- Smaller fixtures cover empty order/employee inputs, NULL-free order references and other development data variations.
- Lab/all suites add output type comparison to the existing column-name and exact bag checks.
- Duplicate-column Calcite testDistinctWithGrouping was excluded before inference and remains listed as unsupported.
- Two Q17 variants share one template; rows are not independent template samples.

Public SQL is pinned to R-Bot commit c9c90e5d7867888c3aaba86e4fc9e6d48f53b375. Files, Apache license and SHA-256 provenance are under benchmarks/sources/rbot/.

This is not official TPC-H/Calcite scale data and not a reproduction of published full-scale speedups. Ordered/LIMIT-sensitive multirow workloads remain outside the admitted oracle. Correctness checks are finite evidence, not a universal equivalence proof.

See [BENCHMARKS.md](BENCHMARKS.md) for the larger workload plan.

## Matched development comparison after key-pool support

Same 14-case workload, evaluator hashes, five timing pairs, one candidate attempt/case and 4,096 output-token ceiling:

| Model | State | Accepted | Incorrect candidates rejected | Whole-run wall time |
| --- | --- | ---: | ---: | ---: |
| Groq GPT-OSS 20B | completed | 8/14 | 1 | 80.766 s |
| OpenAI GPT-6.1 Sol | completed | 8/14 | 0 | 128.512 s |
| Groq GPT-OSS 120B | failed / incomplete | 5/14 | 2 | 78.054 s, not comparable as a complete-run latency |

Run IDs:
- 20B: 20261102T042033Z-95c12c
- 120B: 20261102T042154Z-c819b7
- Closed: 20261102T042312Z-e6a3b3

The 120B run stopped on HTTP 400 for calcite_exists; two remaining cases were recorded not_attempted. No error-body diagnosis or success was invented. Earlier 20B/120B rate-limited runs remain in the ledger.

The completed 20B run had about 37% lower whole-run wall time than the matched closed run in this trial, with the same accepted count. This is one small development comparison. It does not establish statistical noninferiority, general SQL correctness, or a production advantage. Some semantic-test queries are extremely short, so percentage speedups can be noisy and economically trivial.

The closed model's prices are not configured. Provider-level Groq prices only apply to the configured exact model; the 20B run is not priced using 120B rates. Unknown costs stay unknown. No cost-win claim is made.

Reproduce a fresh bounded comparison (paid):

~~~sh
python3 scripts/compare_today.py
~~~

This permits up to 42 candidate generations, plus the separately recorded HTTP rotation attempts. Treat it as a new trial, not a repair of historical evidence.

## Four-key Groq pool

Supported local environment names include GROQ_API_KEY, GROQ_API_KEY2, GROQ_API_KEY3, GROQ_API_KEY4 and underscore-number variants. Values stay in .env.local / server environment and are never exposed through the UI.

- Deduplicate identical key values in memory.
- Round-robin successful generations across configured distinct slots.
- After an explicit Groq HTTP 429 rejection, try another distinct key, at most four total slots for that generation.
- Stop on uncertain network failures and other API failures; do not silently replay them.
- Respect available quota-reset headers for each slot/model before another request.
- OpenAI credentials never rotate into Groq, or vice versa.
- Track credential-slot labels, HTTP statuses, waiting, request counts and candidate generations separately.
- Multiple keys may share account-level quotas; rotation is not a promise of more capacity.

The CopilotKit assistant uses the same bounded 429-only rotation concept, beginning with spare slots. Its chat usage is separate from evaluator benchmark usage and is not included in experiment token totals.

## Training seed collection

~~~sh
python3 scripts/export_training.py
~~~

Outputs:
- .local/training/seed_sft.jsonl
- .local/training/manifest.json

The initial export contains 23 deduplicated examples across 11 template groups from completed development runs. Regenerating after more runs may change these counts.

The export includes successful rewrites and appropriate original-query retention; it excludes mock/failed runs and public reference targets. Its messages are reconstructed schema-only SFT inputs, because earlier exact EXPLAIN prompts were not persisted. Provenance identifies every source row/run/model.

It is marked ready_for_training=false and on_policy_rl_eligible=false. Review labels and rights, create independent group-aware validation/test splits, and verify tokenization before training. Ordinary API logs are not exact-token/logprob RL trajectories. No fine-tuning or reinforcement-learning job ran today.

## Verification

- 50 Python tests passed with real database integration enabled.
- Next.js production build and TypeScript checks passed.
- Chrome screenshots inspected at 1440, 768 and 390px.
- Browser smoke test passed navigation, all 14 dataset rows, run history, bounded-dialog disclosure, mobile overflow, no uncaught exceptions, and a live CopilotKit tool call rendering actual query evidence.
- Copilot runtime /info confirms the BuiltInAgent, tools and streaming; telemetry is disabled.
- A no-cost 14-case mock job completed through the real Next.js evaluation API; the refreshed report includes 14 runs across eight groups, zero skipped.
- Final browser-bundle and build-trace scan found zero configured credential matches and zero traced environment files.
- Generated experiment reports preserve incomplete runs.

Browser verification (one conversation incurs Groq usage):

~~~sh
node scripts/verify_workbench.mjs --chat
~~~

The browser helper uses the installed design skill's local Chrome driver. Reports/screenshots are under .local/ui-qa/ and .taste-skill/.

### Design decisions

Style: data-terminal, seed 430987251; no redraws. Public Sans for interface text and IBM Plex Mono for SQL/figures. Signature: the SQL rewrite comparison linked directly to its verification and paired timing evidence. The main question is whether this candidate earned acceptance.

The final inspector returned zero failures and two contextual warnings (small metadata text and a tiny data bar). Inspector warnings are contextual: monospaced figures/units are intentional, small text is confined mainly to SQL/metadata, and the genuinely tiny candidate-time bar preserves its magnitude rather than being enlarged to satisfy a color-area threshold. Final screenshots are the visual check, not just the automatic score.

## Deployment limitation: dependency audit

The installed CopilotKit dependency tree reports 34 audit entries, including 22 high-severity entries, many propagated from shared dependencies. Review is in docs/DEPENDENCIES.md. No safe current nonbreaking upgrade was verified for every underlying issue. No forced major overrides or automatic downgrade were applied.

This app remains a local demonstration, not a public-production deployment. Keep loopback binding and request limits. Public access needs authentication/authorization, rate/usage controls, dependency remediation/review and deployment-specific hardening.

## Next

1. Finish the Fireworks capability matrix and provider smoke tests when access arrives.
2. Expand source-pinned data with independently prepared templates and explicit ordered-result contracts.
3. Add controlled rule/retrieval/caching routes and evaluate ablations.
4. Audit and expand the training-only seed dataset; then try a bounded SFT experiment.
5. Collect exact policy-versioned RL trajectories before attempting execution-reward training.
