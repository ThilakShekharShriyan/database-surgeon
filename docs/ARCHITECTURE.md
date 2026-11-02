# Database Surgeon: architecture and execution plan

Prepared November 1, 2026 PT for Fireworks access expected November 2.
Status: proposed system design. Only capabilities marked existing are implemented.
Read with [research and references](RESEARCH.md) and [benchmark/data protocol](BENCHMARKS.md).

## 1. Product, beneficiary, and claim

Beneficiaries: teams with recurring PostgreSQL analytics and reporting workloads, where inefficient queries waste database capacity and human tuning time.

Task: given a PostgreSQL SELECT, its declared result contract, schema constraints, physical configuration, and representative workload context, return a validated beneficial rewrite or retain the original.

Primary hypothesis: a routed open-model system can achieve useful rewrite coverage with lower end-to-end optimization cost than a named closed frontier baseline. A secondary hypothesis is lower optimizer latency. A separate quality track can test higher beneficial-rewrite coverage at a fixed budget.

A replacement's SQL speedup is not itself evidence that the open system beat the closed system. Compare the systems' delivered SQL, coverage, correctness evidence, latency, and cost on the same frozen inputs.

### What we can make enforceable

After implementation and tests, the orchestrator can enforce request/cost ceilings, require recorded validation evidence, reject unsupported inputs, retain the original on failure, exclude sealed test data from learning, and block promotion when release gates fail.

It cannot guarantee arbitrary SQL equivalence, a runtime win on every future database state, or superiority over a frontier model before measurement. A model checkpoint is only promoted after evidence supports the chosen claim. Failed and inconclusive experiments remain reportable outcomes.

## 2. Existing baseline and new work

| Layer | Existing | Planned |
| --- | --- | --- |
| Database | PostgreSQL 16, reader role, five fixtures, 50k-order performance DB | Multiple benchmark schemas/instances and snapshot-aware workers |
| Generation | OpenAI/Groq/Fireworks adapters; schema + EXPLAIN prompt; repair feedback | Capability-aware Fireworks registry, small/large model roles, local router |
| Validation | Conservative guard, column-name checks, exact-decimal unordered bags | AST eligibility, output types, ordered/tie-aware contracts, generated counterexamples |
| Measurement | Alternating paired execution times; variability; token artifacts | Workload weighting, run repetitions, cost ledger, CIs, cache tracks |
| Operations | Atomic checkpoints, exclusive evaluation lock, offline reports | Event ledger, candidate cache, model registry, shadow/canary serving |
| Learning | Saved generation/results | Curated SFT/preferences, exact-token RL trajectories, offline training and promotion |
| Evaluation | Three public development query families | Reproduction, stress, synthetic, and sealed evaluation tracks |

The current Python 3.9-compatible CLI remains the baseline. Add dependencies incrementally. Put provider cookbook/training integration in a separate environment matching its requirements; one inspected Fireworks/HUD example requires Python 3.11 or 3.12.

## 3. Architecture: serving and learning are separate loops

~~~mermaid
flowchart TD
    A[SQL or workload import] --> B[Contract and eligibility]
    B --> C{Supported?}
    C -- No --> O[Keep original and record reason]
    C -- Yes --> D[Context fingerprint and budget]
    D --> E{Valid rewrite cache?}
    E -- Yes --> V[Check cached evidence and drift]
    E -- No --> F[Rules and local retrieval]
    F --> G[Bounded candidate validation]
    G --> H{Beneficial rule candidate?}
    H -- Yes --> N[Decision and evidence]
    H -- No --> I[Small open model: first call]
    I --> J[Correctness and benefit gates]
    J --> K{Accepted?}
    K -- Yes --> N
    K -- No --> L{Repair or escalation worthwhile?}
    L -- No --> O
    L -- Yes --> M[One repair OR larger open model]
    M --> J
    V --> N
    N --> P[Shadow or serve with fallback]
    P --> Q[Event and trajectory ledger]
    O --> Q
    Q --> R[Curated training-only data]
    R --> S[SFT then optional preference or RL]
    S --> T[Validation and release gates]
    T --> U[Versioned champion registry]
    U --> I
~~~

Looping through candidate validation never replenishes the request budget. The model stage has at most two successful inference admissions per online optimization request.

Closed-model evaluation is a separate experiment branch, not an undisclosed online fallback. Teacher-assisted training, if used, is marked in the dataset and submission.

## 4. Contracts and component boundaries

### QueryContext

Include request_id, tenant/workload ID, raw SQL hash, parsed AST fingerprint, parameter values or declared parameter domain, supported-dialect/version, result contract, schema/constraints/index fingerprints, selected statistics, session settings, plan hash, dataset instance/version, split/template/lineage IDs, eligibility reasons, estimated repetition count, and budget.

### Candidate

Include candidate_id, parent candidate, source (rule/retrieval/model/repair/cache), exact SQL and hash, transformation ID, parameter binding policy, assumptions, source model/deployment/checkpoint, prompt version, request IDs, usage, and timestamps.

### ValidationEvidence

Include verifier version, supported fragment, output column names/types/order, result-comparison contract, fixture/seed/snapshot hashes, counterexamples or pass evidence, formal proof assumptions if any, per-parameter results, SQL errors/timeouts, and an explicit evidence level.

Suggested evidence levels: rejected; syntax_checked; instances_checked; generated_instances_checked; proved_in_supported_fragment. Never label instance agreement a universal proof.

### OptimizationDecision

Include original/candidate, selected route, why routing stopped, total calls/tokens/cost/DB budget consumed, correctness evidence, timing evidence, keep/replace outcome, and validity/invalidation policy.

### ModelVersion

Include provider model ID, returned model ID, base/adapter/checkpoint, tokenizer/renderer versions, inference endpoint, service mode, training method, train-data manifest, evaluator/reward hashes, sampling settings, rates/capture date, release decision, rollback version, and capability-test evidence.

## 5. Routing policy and hard budgets

### Routes

| Route | Trigger | Model calls | Output |
| --- | --- | ---: | --- |
| R0: retain | Unsupported semantics, low expected value, exhausted budget | 0 | Original and reason |
| R1: exact cache | Compatible validated entry and validity epoch | 0 | Reused candidate with evidence checks |
| R2: negative cache | Recently unproductive equivalent request/context | 0 | Original; short TTL and drift invalidation |
| R3: rules | Preconditions satisfied and candidate passes gates | 0 | Best measured rule candidate |
| R4: small model | Eligible miss with plausible tuning benefit | 1 | Validated candidate or further decision |
| R5: local repair | Localizable SQL/correctness failure and remaining budget | 2 total | One repair of the first model's candidate |
| R6: stronger model | Harder case where development evidence supports escalation | 2 total | Larger open-model candidate with compact feedback |
| R7: offline search | Training/dev workload under its own experiment budget | Separate explicit cap | More diverse candidates; never charged to online-call metrics |

R5 and R6 are alternatives, not successive steps. Do not call a model merely to choose a model. Initially use deterministic AST/plan features; train a local router only after enough outcome data exists.

Start with at most three candidate model IDs during development, then freeze one inexpensive role and one escalation role. A tunable student may be a third offline role until promotion. Benchmark exact versions; parameter count alone does not establish speed or SQL competence.

### Initial configurable limits

- Online inference admissions: maximum 2 per optimization request.
- Rule candidates: maximum 3; structural deduplication before database work.
- Default generation ceiling: 2048 output tokens for first call, with a separately declared total-token ceiling. Reassess on development data; match experimental budgets.
- Per-request wall-time, dollar, original-query, candidate-query, and total database-time ceilings are required configuration values before live serving.
- Every experiment/training job needs total request/token/dollar ceilings, with reserved worst-case cost before admitting work.
- Atomic budget reservations prevent concurrent requests overspending a shared cap.
- A missing price is unknown. Disable dollar-based routing/claims until pricing is known; other hard limits still apply.
- Provider/network/ambiguous-completion failures stop the route. Do not silently retry, replay on another endpoint, or spawn a replacement deployment. Record unknown charge status where relevant.

Zero API calls is not zero compute: rules, retrieval, checking and benchmarking have real costs.

### Expected-value routing

For a candidate route, estimate on development data:

Expected net value = probability of a valid beneficial rewrite x expected repeated-workload savings - inference cost - validation cost - expected regression/uncertainty penalty.

Only spend on routes whose calibrated expected value is positive and whose hard caps remain. Use conservative uncertainty estimates; early deployment should rely on simple gates, not uncalibrated probabilities.

Avoid optimizing sub-millisecond queries unless expected repetitions justify it. Measure the cost of discovering an improvement.

### Illustrative traffic calculation, not a forecast

For 100 requests: 40 valid cache hits, 30 accepted rules, 20 small-model successes, 8 two-call escalations, and 2 early abstentions require 36 model calls, or 0.36 calls/request.

This is arithmetic under an assumed mix, not a promised hit rate. Publish the observed distribution, including cold-start and unseen-schema tracks.

## 6. Minimizing calls, tokens, and database work

1. Single-flight identical in-progress requests within the same isolation/context scope.
2. Reuse metadata snapshots, original plans, and original timing evidence only within a declared validity window.
3. Use local AST matching/BM25 over training/development evidence before paid embedding retrieval.
4. Retrieve a small number of relevant examples; never retrieve sealed test references.
5. Keep stable task instructions, schema constraints and static examples at the prompt prefix; request-specific SQL and feedback follow.
6. Distinguish application rewrite-cache hits from provider prompt-cache hits. Prompt caching still makes an inference call.
7. Measure actual cached-token usage; affinity is an optimization hint, not a guaranteed hit.
8. Request compact structured SQL/action output; avoid multi-agent conversations where one candidate call suffices.
9. Generate small bounded candidate sets and stop on a sufficiently beneficial valid candidate.
10. Use planner estimates to prioritize candidates, not to declare measured wins.
11. Apply correctness checks before expensive performance trials. Reuse original outputs only on immutable snapshots with the same contract.
12. Keep offline exploration separate from serving metrics; batch offline jobs only if supported and appropriate for latency requirements.

Official cache details: [prompt caching](https://docs.fireworks.ai/guides/prompt-caching). Model/endpoint behavior must be capability-tested; do not assume a cache header available in Chat Completions also works identically through the current Responses adapter.

## 7. Cache validity and parameter sensitivity

A reusable entry needs more than a normalized query hash:

- Tenant/database and privileges/role context.
- Dialect and PostgreSQL version.
- Schema, constraints, index and relevant function definitions.
- Result contract, session timezone/collation/search_path and relevant settings.
- Parameter binding policy and validated domain/selectivity range.
- Statistics/performance epoch, validator version, model/rule version, evidence level.
- Expiry, observed drift and explicit invalidation reason.

Separate exact-SQL reuse from parameterized transformation reuse. pg_stat_statements query IDs group literals and are not equivalence certificates. Never reuse a literal-bound replacement for a different parameter value.

A full parameter-domain guarantee may be unavailable. Keep a narrow admitted domain, sample boundary/selectivity buckets, and retain the original outside it. Statistics or load changes may invalidate a performance decision even when semantics remain unchanged.

## 8. Validation and performance acceptance

### Stage A: supported-task eligibility

Parse as PostgreSQL. Initially admit SELECT-only deterministic queries in an explicitly documented fragment. Keep the current guard and restricted role while adding structured checks. Deny untrusted functions and unsupported constructs according to the task contract.

Ordering, LIMIT ties, windows, volatile expressions, session-sensitive behavior, output type changes, collations, floating-point comparisons, and era/date boundaries must have explicit handling. Initially abstain where the checker cannot evaluate the required semantics.

### Stage B: syntax and result shape

Use PostgreSQL parsing/planning. Compare output names, positions, and types. Our existing name check needs a type contract before claiming type preservation. A successful parse or EXPLAIN is not semantic evidence.

### Stage C: semantic evidence

- Compare exact multisets for bag-contract queries, preserving duplicates, NULLs, and exact numeric values.
- For ordered queries, use a declared ordered/tie-aware contract. Do not sort away observable ordering.
- Use consistent read snapshots so concurrent writes cannot create false mismatches.
- Test multiple small fixtures: empty inner/outer inputs, all/no/some NULLs, duplicate join keys, unmatched rows, skew, numeric boundaries, temporal boundaries.
- Use seeded generated counterexamples; replay every discovered counterexample as a regression test.
- Add formal verification only for supported fragments; store assumptions and unknown outcomes.
- An LLM critique may suggest counterexamples but cannot independently certify correctness.

ParSEval is an optional adapter, not a universally supported admission oracle. Its known limitations and our own checker limitations remain visible.

### Stage D: benefit evidence

Use an isolated performance instance and repeated paired executions. Alternate/randomize original/candidate order, retain all raw samples, record warm/cold policy, PostgreSQL settings, data/index fingerprints and load.

Initial candidate threshold: at least 20% median execution-time reduction, matching the pilot. Require sufficient absolute savings and acceptable uncertainty. A candidate selected using exploratory timing should be checked on a fresh confirmation batch before publishing its gain.

Do not benchmark training candidates concurrently against the same timing database. Parallel workers need independent instances/resources or their noisy measurements must be labeled screening-only.

### Stage E: decision

Accept only with supported semantic evidence and confirmed benefit. Otherwise retain the original and record the exact failure state. Timed-out/unsupported cases remain in full-denominator reports. Original-query timeouts are censored observations, not invented finite speedups.

## 9. Data collection: three separate products

### 9.1 Audit event ledger

Append events for received, eligible/rejected, cache lookup, candidate generated, correctness verdict, counterexample, timing trial, route stopped, decision, deployment observation, and training export.

Use idempotent event IDs with a deduplication key of request/candidate/attempt/event kind. Preserve append-only outcomes; corrected labels become new versioned records. SQLite plus JSONL export is sufficient for the first implementation. A message bus and distributed store are scaling options, not day-one dependencies.

Proposed event shape:

~~~json
{
  "event_version": 1,
  "event_id": "uuid",
  "request_id": "uuid",
  "case_id": "case-or-workload-id",
  "template_id": "structural-lineage-id",
  "split": "train",
  "context_sha256": "...",
  "candidate_id": "uuid",
  "source": "small_model",
  "policy_version": "base-or-adapter-snapshot",
  "status": "incorrect",
  "evidence": {
    "contract": "unordered_bag",
    "counterexample_artifact": "artifact-id",
    "validator_sha256": "..."
  },
  "usage": {
    "input_tokens": 0,
    "cached_tokens": 0,
    "output_tokens": 0,
    "cost_usd": null,
    "charge_status": "unknown"
  },
  "training_eligibility": {
    "sft": false,
    "preference": true,
    "on_policy_rl": false,
    "reason": "ordinary API log lacks exact trajectory data"
  }
}
~~~

Numbers above are placeholders. A rejected candidate may be the rejected half of a preference pair only if a valid chosen response for the same input exists.

### 9.2 Curated SFT/preference records

Store original input/context, exact chosen/rejected SQL, evidence IDs, transformation family, source/license/provenance, parameter assumptions, costs, and lineage. Keep valid abstentions. Sample by family and difficulty rather than successful speedups alone.

Exports must enforce split and lineage separation, remove credentials, handle workload-sensitive literals by policy, deduplicate template variants, and require label audits. No evaluator-only references or hidden test fixtures enter prompts or training.

Export rejection reasons and short observable feedback; do not invent or reconstruct private chain-of-thought.

### 9.3 RL-ready trajectories

Ordinary logs are not automatically on-policy training data. Record:

- Exact prompt and generated token IDs, aligned behavior-policy log probabilities, tokenizer and renderer versions.
- Loss masks that train generated policy tokens and exclude prompts, tool results, verifier outputs and environment observations.
- Base model, adapter/snapshot, per-segment policy version, sampling parameters, request IDs and declared staleness.
- Trajectory/group IDs, segment ancestry, actions, observations, terminal outcome, reward version and evidence.
- Repeated-prefix mask/ancestry so shared generated tokens are not trained twice.
- Trace validity and explicit infrastructure failure classification.

Require equal token/logprob/mask lengths; reject or explicitly segment non-append histories. Never fill missing logprobs with fabricated values. Old OpenAI/Groq pilot responses may support audited SFT/preference examples, not GRPO updates.

See the [official agentic RL contract](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/agentic-rl).

## 10. Training loop and reward design

### Phase T0: no training

Establish rules, routing, retrieval, baseline quality, API-call distribution and cost. Fix the evaluator before using it as a reward source.

### Phase T1: supervised specialization

Target a sufficiently capable, supported open student. Train on verified rewrites and repairs, plus useful original-query retention. First improve one-shot coverage or reduce output length/repair rounds.

Use a small learning-curve experiment with fixed validation data. Keep base/student/closed comparisons under the same contract. Use explicit group-aware evaluation data rather than an automatic random row split.

### Phase T2: preferences

Build chosen/rejected pairs for the same input. Prefer semantic validity first; rank correct candidates by reliably measured benefit and cost. Do not label measurement noise a preference. DPO/ORPO is optional and earns its place by validation results.

### Phase T3: execution-reward RL

Begin with synchronous, small groups from one pinned policy snapshot. Calibrate reward variation and inspect traces before any optimizer step. Use independent database workers; enforce time, memory, and rollout budgets.

A proposed bounded reward, to be calibrated on training/development only:

~~~text
if trace is broken or infrastructure failed:
    exclude from policy update; keep operational failure in experiment ledger
elif output violates syntax, permissions, or required semantic checks:
    reward = -1
elif measured candidate regresses:
    reward = a bounded negative value
elif candidate is valid and confidently beneficial:
    reward = clip(log(original_ms / candidate_ms), 0, 1)
             - bounded_token_cost_penalty
             - bounded_verifier_cost_penalty
else:
    reward = 0
~~~

This is a proposed local reward, not a Fireworks API specification. Adapt scale/range to the chosen recipe; never assume legacy managed-RFT reward rules apply. Keep infrastructure failures separate from valid environment failures. Introduce cost penalties only after correctness learning is stable so refusal/short outputs do not become a reward shortcut.

Reward under a finite verifier can still be exploited. Maintain independent validation, generated counterexamples, an untouched test set, and the inference-time acceptance gate. Do not reward empty results, textual changes or plan divergence alone.

For initial GRPO: at least two samples per prompt are needed for group-relative variation; try four in a bounded calibration. Choose the final group size and rollout count by measured signal and cost. Keep asynchronous/off-policy training deferred until synchronous trace and reward tests pass.

### Pretraining

Pretraining from scratch is outside the planned budget. Continued pretraining may be investigated later if a domain-language deficit is demonstrated and compatible training support exists. Start with retrieval and SFT, which directly target the task and use our available labels.

### Continual improvement without uncontrolled promotion

Collected training-only outcomes -> reviewed batch -> immutable dataset version -> bounded training job -> validation -> one-use release test -> champion/challenger decision -> shadow -> optional canary -> promotion or rejection.

Do not update serving weights after each request. Rotate future sealed tests after a release test is used for selection. Replay older families and counterexamples to detect forgetting.

## 11. Fireworks implementation contract

### Model capability registry

For each candidate model, record exact account resource ID; inference endpoint; structured output and reasoning behavior; context/output limits; cached-token metrics; method-specific training support; tokenizer/renderer; LoRA/base compatibility; available shapes/quota; checkpoint sampling; ordinary serving mode; pricing timestamp; and successful smoke-test evidence.

Model roles remain unassigned until discovery and development evaluation. Documentation examples such as Qwen 3.8 27B or GLM 5.3 Flash are leads, not verified choices for this account or SQL task.

### Training surfaces

- Managed SFT/DPO: simplest dataset-driven path when the selected model/method is supported.
- Serverless Training API: first custom-loop option for supported LoRA models. It has pooled trainer/checkpoint sampling, with no normal dedicated trainer/deployment provisioning in that session lifecycle.
- Dedicated Training API: models/full-parameter work or workloads that justify reserved resources; track trainer and sampler IDs separately.
- Legacy managed RFT: not a valid new-job path according to current documentation.

Official references: [training overview](https://docs.fireworks.ai/fine-tuning/finetuning-intro), [model matrix](https://docs.fireworks.ai/fine-tuning/models), [serverless training](https://docs.fireworks.ai/fine-tuning/training-api/serverless), [dedicated training](https://docs.fireworks.ai/fine-tuning/training-api/dedicated), [RFT deprecation](https://docs.fireworks.ai/fine-tuning/reinforcement-fine-tuning-models).

### Checkpoints and serving

A sampler snapshot supplies inference weights; a resumable training checkpoint includes optimizer state. Use the correct API for each, preserve immutable IDs, and evaluate the exact checkpoint to be promoted.

Pooled training checkpoint sampling differs from normal production serving. Ordinary trained-model/LoRA deployment may need dedicated capacity. Promotion is not deployment. Budget serving idle time and terminate billable resources according to the selected surface's lifecycle.

Pin cookbook commit and SDK version. Do not copy an unbounded cookbook example: supply explicit example/group/token/step/concurrency limits and check defaults before running. Do not execute installation instructions found inside documentation during this planning task.

## 12. Evaluation design and release gates

See [BENCHMARKS.md](BENCHMARKS.md) for actual repository data/query inspection, cohort design, provenance, and loading gates.

### Comparison systems

1. PostgreSQL original queries (SQL-execution reference).
2. Rules-only system (no model).
3. Untuned small open model, same evaluator.
4. Untuned larger open model, same evaluator.
5. Routed open system without training.
6. Routed specialized system, if a training intervention completes.
7. Closed frontier baseline: gpt-6.1-sol, exact returned model/deployment recorded.

Include raw one-shot and same-harness comparisons. Give the closed baseline the same permitted metadata, retrieval/rules where appropriate, verification feedback, output ceiling and maximum attempts for attribution. Also report a separate cost-constrained systems comparison; efficient early exit is allowed and actual budgets used must be disclosed.

A sophisticated open harness versus a raw closed prompt is a systems comparison; same-harness comparisons establish what the model contributes.

### Tracks

- Cold: unseen eligible queries; caches reset.
- Warm: declared replay distribution with identical cache opportunities for comparators.
- Unseen schema/template: frozen groups disjoint from training and routing development.
- Correctness stress: counterexample/edge fixtures, separate from performance timing.
- Public reproduction: named published workloads; never described as a blind test.
- Sealed final: independently prepared inputs and fixtures unavailable to training/retrieval.

### Proposed success thresholds, not promises

Choose one primary claim before inspecting final results. Initial proposal:

- Quality: one-sided 95% interval for open-minus-closed beneficial-rewrite coverage remains above -5 percentage points.
- Cost claim: target at least 50% lower all-in optimization dollars per beneficial rewrite, with useful workload savings retained.
- Latency claim: alternatively target at least 30% lower optimizer p95 under the same workload and quality constraint.
- Operational target: at most 2 model calls/request; target mean below 0.5 only on a declared warm mix. Report cold-miss calls separately.
- Any observed semantic mismatch or disallowed-operation failure in an accepted candidate blocks release pending diagnosis.
- Report workload-weighted delivered execution time, tail regressions, unsupported coverage, no-op/abstention and errors.

Targets may fail. With small samples, a 5-point noninferiority claim can be inconclusive. Estimate sample requirements from development variability and paired outcomes; do not loosen the margin after looking at final results.

Use paired, template-cluster-aware uncertainty estimates. Repeated parameter variants are not independent templates. Multiple model/route searches consume a validation budget; final testing should be locked and held aside. Zero observed unsafe outputs does not imply zero true risk.

## 13. Cost and business-value ledger

Separate:

- Input, cached input, generated/reasoning usage where exposed, failed-output usage and unresolved-charge status.
- Database validation, original/candidate timing, counterexample/prover work, storage and orchestration.
- Offline teacher/data generation, training and checkpoint evaluation.
- Dedicated trainer/sampler/serving setup, allocated idle time and teardown.
- Event credits and promotional pricing versus ordinary rates.

If no beneficial rewrites are delivered, cost per beneficial rewrite is undefined/infinite, never zero. Report both total cost and count.

Inference estimate = (uncached_input x input_rate + cached_input x cached_rate + output x output_rate) / 1e6.

Serverless Training API uses separate prefill, sample and train meters; use its published model/method rates rather than inference rates. Dedicated resources need allocated-time accounting.

Per-template break-even:

~~~text
optimization_cost = model + checking + timing + amortized training/serving costs
net_value_per_execution = measured billable savings - added runtime overhead
break_even_executions = optimization_cost / net_value_per_execution
~~~

Only compute break-even when savings are positive and a defensible billing conversion exists. Lower query wall time does not automatically reduce a fixed database bill. Report CPU/I/O capacity or latency value separately when dollar savings are not measurable.

## 14. Serving, shadowing, and rollback

Initial delivery is a CLI/notebook/API demonstration; no website is required. Later workload ingestion can use pg_stat_statements after separate extension setup.

Keep optimization and semantic/performance validation on an isolated staging/replica environment. Original/candidate comparisons need a consistent data snapshot. Do not blindly double production query traffic for validation.

Promote only a versioned candidate/rule/model policy with recorded eligibility and validity domains. Invalidate on schema/constraint/index/session/parameter drift. Monitor mismatches, query errors, latency distributions, support coverage and cache drift. Route to original if the acceptance service is unavailable.

A canary uses a predeclared small fraction and rollback thresholds, with a last-known-good version. A cached rewrite's future semantic correctness is not guaranteed merely because it passed earlier samples. Keep the product advisory until the admitted contract and evidence justify automatic use.

## 15. Proposed code organization

These paths are implementation targets, not existing commands/modules.

~~~text
surgeon/
  context.py             # snapshot, contracts, AST features, fingerprints
  routing.py             # deterministic first router and bounded decisions
  budgets.py             # atomic call/token/dollar/DB-time admission
  rules/                 # typed preconditions and tested transformations
  retrieval.py           # local matching of permitted verified traces
  cache.py               # exact and parameter-domain entries, invalidation
  validation/            # bag/ordered/type/counterexample/formal adapters
  providers.py           # normalized provider capabilities and usage
  collection/            # event ledger, lineage and exports
  training/              # provider-independent job specs and reward adapter
  evaluation/            # immutable manifests, paired runner and reports
benchmarks/
  manifest.template.json # intentionally unfrozen onboarding manifest
  README.md              # importer and provenance requirements
docs/
  RESEARCH.md
  ARCHITECTURE.md
  BENCHMARKS.md
~~~

Start with an embedded ledger and local worker queue. Introduce a separate API process, object store or distributed workers only when the measured workload requires them.

## 16. Execution milestones

### Tonight: planning artifacts

- [x] Preserve research with all original references and current provider constraints.
- [x] Specify architecture, routes, budgets, data contracts, release criteria and evaluation cohorts.
- [x] Inspect actual repository SQL and identify ordering, lineage and data-loading requirements.
- [ ] Build pipeline modules and benchmark adapters. Documentation does not satisfy this item.

### Tomorrow: first 60-90 minutes after access

1. Add the key locally; run existing doctor and database checks.
2. Discover Fireworks models and collect method/endpoint/rate/quota metadata.
3. Choose a small development subset; perform bounded structured-output/usage smoke tests for candidate roles.
4. Check the existing Fireworks Responses adapter against actual returned output before a broad sweep.
5. Pin the selected model IDs, endpoints, rates, tokenizer/renderers and source commits.

Existing commands:

~~~sh
bash scripts/check_local.sh
python3 -m surgeon models fireworks
python3 -m surgeon doctor --json
~~~

Only after selecting and pricing an accessible exact model, one bounded existing-harness run:

~~~sh
python3 -m surgeon run --provider fireworks --model EXACT_ACCESSIBLE_MODEL_ID --attempts 1 --max-output-tokens 4096
~~~

This is a paid command for tomorrow, not a command executed by this plan.

### First working session: evaluation and bounded routing

1. Admit a small public reproduction cohort with exact data/schema contracts.
2. Add unordered/type eligibility and implement ordered-result checks before including ordered cases.
3. Implement budget ledger, AST features, one rule route and original fallback.
4. Add positive/negative cache invalidation and local retrieval.
5. Add small-model -> one repair OR stronger-open-model routing.
6. Run same-harness baselines and ablations on development, then freeze.
7. Finish a modest diverse sealed pilot; publish inconclusive uncertainty honestly.

### Next session if training access and time permit

1. Export and audit diverse training-only verified examples.
2. Prepare a model-specific tokenization/rendering and explicit validation manifest.
3. Run a tightly bounded SFT smoke job with measured before/after.
4. Reject or promote the checkpoint through the same gates.
5. Calibrate a tiny SQL reward environment and exact trajectories; only then try one RL update.
6. A no-training pipeline remains a valid challenge submission if its measured efficiency claim passes.

### Following 1-2 weeks

Expand workloads/scales, add counterexample/prover coverage, train router/ranker, compare SFT/preference/RL, implement shadow serving and drift controls, and collect larger independent evaluation samples.

## 17. Submission evidence packet

- Beneficiary, input/output task and supported SQL contract.
- Exact open/closed IDs, prompts, metadata, route policies and budgets.
- Dataset provenance, source commits, generated-data seeds, split lineage and overlap audit.
- Full denominator, correctness funnel, unsupported cases, abstentions, errors and regressions.
- Raw samples, run repetitions, paired uncertainty, weighted workload benefit, optimizer p50/p95.
- API and infrastructure cost ledger, unknown costs, credits and amortization assumptions.
- Ablations for rules, retrieval, repair, routing, caching and training.
- Model/data/validator versions, release decision, rejected experiments and limitations.
- Notebook/CLI/API demo showing a fast rewrite, an incorrect rewrite rejected, and an already-good query retained.

An improvement claim is written only after these artifacts support it.
