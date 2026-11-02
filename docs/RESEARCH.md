# Database Surgeon: research and reuse guide

Prepared November 1, 2026, America/Los_Angeles; official Fireworks documentation checked November 2 UTC.
Status: research and proposed integration decisions, not implemented capabilities or a model-performance claim.
Companion: [Architecture and execution plan](ARCHITECTURE.md).
Original research: [TinyFish deep-research report](https://agent.tinyfish.ai/playground/research/share/01a19a29-6e7d-76e5-a134-e0e4b25888c7).

## 1. Decision in one paragraph

Build a PostgreSQL SQL-to-SQL rewrite specialist that returns a validated, beneficial replacement or keeps the original. Combine guarded rules, retrieval of verified examples, a small open model, selective repair/escalation, and an offline training loop. Start with the existing execution harness. Measure lower end-to-end optimization cost or latency at useful rewrite coverage against an explicitly identified closed frontier model on the same cases. Treat fine-tuning as an intervention to evaluate, not an assumed improvement. Fireworks is the intended inference/training platform when account access arrives.

## 2. What exists and what remains proposed

### Observed local evidence

The local project is a Python standard-library CLI with PostgreSQL 16. It already supplies schema and EXPLAIN context, validates original queries before inference, checks row bags on five fixtures, benchmarks alternating original/candidate executions, provides repair feedback, and writes checkpointed artifacts.

| System | Maximum attempts per case | Accepted beneficial rewrites | Whole-run wall time |
| --- | ---: | ---: | ---: |
| OpenAI gpt-6.1-sol | 1 | 2/3 | 22.704 s |
| Groq openai/gpt-oss-120b | 1 | 1/3 | 7.068 s |
| OpenAI gpt-6.1-sol | 3 | 2/3 | 20.854 s |
| Groq openai/gpt-oss-120b | 3 | 2/3 | 11.720 s |

These are single development runs on three public cases, with five timing pairs per evaluated candidate and a 20% median reduction threshold. They are not confidence intervals, held-out results, or a winner declaration. Whole-run times include setup and differ from candidate SQL execution times. Three maximum attempts does not mean every case used three calls.

- All 39 tests passed in the earlier approved execution, including database integration.
- Fixtures: bench, check_a, check_b, check_nonnull, check_empty; benchmark has 50,000 orders.
- Groq's iterative run rejected an incorrect NULL-sensitive anti-join, then accepted its repaired candidate.
- Configured Groq cost estimates total $0.00315060 for the two live Groq runs; these are not independently reconciled invoices.
- OpenAI cost is unknown because price fields are unset.
- Fireworks account inference and training are untested. Its API key was absent at the last check.

Evidence: [experiment report](../results/report.md), run IDs 20261102T023702Z-8bb361, 20261102T023730Z-932e89, 20261102T023740Z-f9137b, and 20261102T023819Z-4e6651.

### Proposed additions

AST-based eligibility, workload mining, rule routing, verified-example retrieval, positive/negative caches, capability-aware Fireworks model registry, counterexample generation, richer result contracts, immutable data splits, trajectory collection, training exports, SFT/DPO/RL, statistical release gates, and a serving layer are plans. Their implementation is described in the companion document.

## 3. Reading order and evidence standards

Read R-Bot, QUITE, SQLGlot, ParSEval, the SQL-RewriteBench paper, TRL, and the official Fireworks cookbook first.

- Direct README checks in this session's research cover R-Bot, QUITE, LLM-R2, ReSequel, SQLSolver, ParSEval, SQLGlot, TRL, Unsloth, and the Fireworks cookbook.
- Other repository observations below come from the prior deep-research source review. Recheck the selected commit, license file, supported SQL fragment, dependencies, and a small reproduction before integration.
- A paper is evidence of a method and its reported experiment, not proof that an artifact runs in our environment.
- Star counts are deliberately omitted: relevance, supported SQL, correctness contract, reproducibility, and integration cost matter more.
- All 44 original report source URLs are retained below. Discovery lists and issue trackers are background, not substitutes for primary documentation.
- We have not cloned, executed, or benchmarked these external repositories in this research task.

## 4. Closest SQL rewrite systems

| System | Method and useful artifact | Integration decision | Important limitation |
| --- | --- | --- | --- |
| [R-Bot / LLM4Rewrite][R01] | Retrieve evidence and choose/order Calcite rewrite rules; rule specifications and retrieval modules | Study first; adapt evidence retrieval and rule-selection ideas | README tests PostgreSQL 14.13 with Java 17; our engine is PostgreSQL 16. Rule soundness depends on semantics and preconditions |
| [QUITE][R30] | Training-free reasoning, verification, and decision loop with plan feedback | Study repair protocol and failure taxonomy | README documents a rewrite matching one benchmark instance without strict semantic equivalence |
| [LLM-R2][R42] | LLM-guided rule selection and contrastively trained demonstration selector | Evaluate retrieval specialization as an alternative to generator training | PostgreSQL 14.4 and Java dependencies; inspected README does not establish reuse licensing |
| [ReSequel][R26] | Generate, sample-check, and rank variants across PostgreSQL/MySQL/DuckDB | Reuse design lessons and inspect evaluation adapters | Large published reproduction environment; sampled checks do not establish general equivalence |
| [QueryBooster][R04] | Expert-authored rules applied by middleware | Reference for reusable rules and query interception | Rule authoring and middleware integration are substantial work; inspect license before reuse |
| [LearnedRewrite][R31] | Monte Carlo tree search over rewrites | Optional search baseline after basic routes work | Research artifact with schema/front-end constraints; do not assume correctness coverage |
| [WeTune][R05] | Discover and verify rewrite rules | Study rule preconditions and available rule artifacts | Full discovery reproduction is expensive; do not transfer rules across dialects without checking semantics |
| [GenRewrite paper][R39] | Natural-language rewrite rules and iterative correction | Method reference | No author-maintained implementation was confirmed in this review; [R44] is an unofficial implementation |
| [E3-Rewrite paper][R32] | Correctness/performance-oriented learning and staged validation | Training-design reference | Code availability was not confirmed; validate reward details from paper before reproducing |
| [SPA paper][R33] | Plan-aware reinforcement learning for rewriting | Investigate reward curriculum and plan features after SFT | Paper-level evidence; no confirmed runnable official repository in this review |

Do not reproduce papers' speedup numbers as a leaderboard. Their SQL, hardware, data distributions, scale, caches, and acceptance criteria differ.

## 5. Infrastructure worth using

| Component | Role | Initial action |
| --- | --- | --- |
| [SQLGlot][R10] | PostgreSQL AST, fingerprints, normalization, structural deduplication | First external runtime library to trial; retain PostgreSQL validation and the database permission boundary |
| [Apache Calcite][R25] | Rule engine and relational transformations | Optional later adapter; isolate the JVM dependency |
| [ParSEval][R27] | Generate distinguishing databases; disprove candidate equivalence | Spike on a supported SQL subset, preserve generated counterexamples |
| [SQLSolver][R38] | Formal equivalence evidence for supported queries | Optional isolated service/subprocess; UNKNOWN/TIMEOUT do not mean equivalent |
| [VeriEQL][R37] / [SPES][R36] | Additional bounded/symbolic verification approaches | Research alternatives; evaluate SQL coverage and assumptions first |
| [SQLancer][R34] | Differential-testing and metamorphic-testing techniques | Borrow edge-case taxonomy and seeded generation methods |
| [SQLsmith][R35] | Random SQL generation | Optional workload source; filter unsupported and uninteresting outputs |
| [SQL-RewriteBench paper][R43] and [linked artifact][A01] | Full-denominator end-to-end rewrite evaluation | Inspect artifact version/license, reproduce a small subset, reserve final evaluation from development |
| [BenchBase][R09] | Database workload execution and generation | Optional larger-scale workload adapter |
| [JOB][R08], [DSB][A02], [CEB][R28], [SQLStorm][A03] | Complex queries and varied distributions | Select a manageable licensed subset; distinguish public benchmark familiarity from novel held-out evaluation |
| [Fireworks cookbook][F13] | Supported training recipes and lifecycle examples | First provider-specific training integration, pinned to a commit |

ParSEval's README distinguishes NEQ with a counterexample from EQ on generated databases, which is evidence rather than proof. It also reports known DISTINCT-aggregate false positives. Formal tools have restricted front ends and semantics. No checker should silently relabel unsupported queries as safe.

SQLGlot's parser and optimizer are not a universal PostgreSQL equivalence oracle. AST changes or different plans alone do not show a benefit.

## 6. Adjacent approaches and scope boundaries

- [Bao][R24], [Balsa][R07], [pg_hint_plan][R23], and [AQO][R29] optimize planning choices or cardinality estimates. Study their routing/learning ideas; adding them would create a separate plan-steering track.
- [DB-GPT][R18], [DB-GPT-Hub][R19], and [SQL-R1][R41] are mainly relevant to natural-language-to-SQL and specialization infrastructure. Their task metrics do not establish SQL rewrite correctness or speed.
- Index recommendations, materialized views, configuration tuning, write-side workload costs, schema changes, and arbitrary SQL dialect support are deferred. They need different permissions and evaluation contracts.

## 7. Training methods and repositories

| Method | Candidate tooling | Data and decision |
| --- | --- | --- |
| Train a router/ranker | Local supervised classifier, embeddings if needed | Start with inexpensive AST/plan features and measured outcomes; an LLM router would add a call |
| SFT with LoRA | [Fireworks managed SFT][F03], [Training API][F11], [TRL][R12], [Unsloth][R11], [Axolotl][R13] | Verified input/output examples, repairs, and appropriate original-query retention |
| DPO / ORPO | [Fireworks managed training][F02], TRL, Axolotl | Preferred/rejected outputs from the same input; distinguish correctness failures from noisy performance differences |
| GRPO / execution rewards | [Fireworks RL cookbook][F16], [verl][R14], [OpenRLHF][R15], TRL | Fresh policy rollouts, a stable reward environment, exact tokens/logprobs/masks, and independent evaluation |
| Distillation | [Fireworks Training API][F05] and verified teacher examples | Disclose teacher use and data provenance; observe provider/model/data terms |
| Continued pretraining | Compatible custom/full-parameter tooling if justified | Deferred until evidence shows SFT/retrieval is insufficient; not required for this challenge |
| Pretraining from scratch | A separate research program | Outside the hackathon scope and current data/compute plan |

SFT, DPO, and RL are distinct interventions. Evaluate each against its immediate predecessor and the closed baseline. No minimum dataset size guarantees improvement; use learning curves and a validation split. A useful first milestone is a few hundred genuinely diverse verified traces, not thousands of literal substitutions.

Unsloth's inspected README describes Apache-2.0 core licensing with some optional AGPL-3.0 components. Review exact components and commits. This document does not provide licensing clearance.

## 8. Fireworks capability findings for November 2

These are documentation findings, not confirmed account entitlements.

| Capability | Official documentation says | Design consequence |
| --- | --- | --- |
| Managed RFT | New managed RFT jobs are no longer accepted; RL moved to Training API [F04] | Do not build around the legacy managed-RFT endpoint |
| Managed SFT/DPO | Supported methods and training shapes vary per model [F02] [F15] | Maintain a model/method capability matrix |
| Serverless Training API | Shared LoRA training/sampling supports SFT, preference methods, RL and custom loops for listed models [F11] | Preferred first training path if account/model eligible |
| Dedicated Training API | Additional model/full-parameter choices with separately managed trainer and sampler resources [F05] | Use only when justified; account for setup, idle time and cleanup |
| Serving trained models | Ordinary user-model/LoRA deployment requires dedicated serving under the inspected model/SFT guides [F03] [F09] | Separate pooled checkpoint evaluation from production deployment planning |
| RL checkpoint sampling | Serverless training can sample base models or checkpoint snapshots without provisioning a normal dedicated deployment [F11] | A training sampler is not automatically a production serving endpoint |
| Prompt caching | Exact prefix reuse; locality/affinity matters; generation is still sampled and billed [F06] | Stable prefix and measured cache usage; not equivalent to zero-call rewrite caching |
| Structured output | JSON/grammar constraints with endpoint/model-specific limitations [F07] [F08] | Validate output locally; schema compliance does not imply correct SQL |
| RL trajectories | Preserve exact token ancestry, behavior logprobs and masks; distinguish broken traces from task failures [F17] | Separate RL-ready traces from ordinary inference logs |
| Async RL | Current cookbook recipes are experimental and version-sensitive [F16] | Pin SDK/cookbook; start with a bounded synchronous calibration |
| Costs | Training, inference, deployment, and rollout work have different meters [F11] [F12] [F18] | Record rates and usage per model, method, service mode, and date |

The live catalog is [F15]. Example IDs in documentation are discovery leads, not an approved model selection. Existing FIREWORKS_MODEL in .env.local is also not verified merely because it is configured. Recheck access, supported endpoint, structured output, tokenizer/renderer, context, training method, and prices tomorrow.

Do not rely on a temporary promotion in the architectural budget. Capture any event credits separately from undiscounted economics.

## 9. Corrections and qualifications to the raw research report

The original report is useful discovery material, but these corrections take precedence:

1. Our current project already sends EXPLAIN context and supports iterative repair. Implementing them is not new work.
2. Workload mining through pg_stat_statements is proposed, not present. Enabling it requires an extension/preload setup and appropriate privileges [P01].
3. NULL = NULL evaluates to UNKNOWN in SQL, not FALSE. Preserve three-valued logic.
4. Matching results on finite databases is not universal equivalence. Unsupported formal-verifier inputs and timeouts require explicit evidence states.
5. TPC-related membership, redistribution, and public-domain claims in the generated report were not verified against controlling terms. Do not rely on them. Check each code/data artifact's terms before redistribution.
6. DSB and third-party workload repositories do not automatically remove upstream data or benchmark obligations.
7. Public availability, reported deployment, a README setup command, or a paper result does not establish production readiness.
8. There is no evidence for a universal claim that no existing system can outperform a closed model. SQL-RewriteBench reports specific methods/configurations under its own protocol.
9. An API key does not establish training quota or serving capacity. Managed RFT and Training API are different products.
10. Normalized query IDs are useful workload groups, not sufficient correctness/performance cache keys across parameter values.
11. Cache hits still cost lookup, invalidation, and possible validation work. Fewer calls and less prompt work are distinct improvements.
12. A changed physical plan is not proof of a faster query. Estimated planner costs are not measured execution times.
13. No fixed SFT example count, GPU class, LoRA rank, or reward recipe guarantees a gain.
14. Read-only execution still consumes CPU, memory, and I/O. Shadow checks belong on an isolated evaluation database and must use consistent snapshots.
15. The screenshot supplied with the planning request was unreadable. No details have been inferred from it.

## 10. What to reuse tomorrow

1. Keep our existing provider-neutral evaluator and artifact checkpoints.
2. Trial SQLGlot for AST features, candidate deduplication, and eligibility checks.
3. Add a small rule registry with explicit constraints and PostgreSQL tests.
4. Retrieve our own verified development examples using local matching first.
5. Spike ParSEval on a small supported subset and save counterexamples.
6. Discover Fireworks model capabilities, choose two open roles on development data, and preserve the closed baseline.
7. Use the Fireworks cookbook for a bounded training pilot only after trace/data validation.
8. Publish ablations, full denominators, cost/latency distributions, and limitations.

Implementation detail, proposed budgets, diagrams, dataset contracts, gates, and the phased build plan are in [ARCHITECTURE.md](ARCHITECTURE.md).

## 11. Query-level follow-up

The follow-up inspected repository directories, raw query files, schema metadata, and data setup instructions. See [BENCHMARKS.md](BENCHMARKS.md) for concrete SQL patterns, repeated-template leakage, deliberate-degradation cases, and runtime prerequisites. W references below preserve the inspected artifacts. SQL-RewriteBench's repository README clarifies its project Apache-2.0 default and separate third-party notices; the paper's license is not the repository's blanket license.

## 12. Complete reference library

R01-R44 preserve every URL in the original research report, including discovery lists, issue pages, and duplicate abstract/HTML views. Their inclusion does not mean every claim in the source is endorsed. F references are official Fireworks material checked for this plan; P01 is PostgreSQL documentation. A references are additional artifacts linked by inspected primary sources and require a reproduction/license check before use.

- **R01** — [R-Bot / LLM4Rewrite repository](https://github.com/curtis-sun/LLM4Rewrite)
- **R02** — [GenRewrite paper HTML](https://arxiv.org/html/2403.09060v3)
- **R03** — [R-Bot paper HTML](https://arxiv.org/html/2412.01661v2)
- **R04** — [QueryBooster repository](https://github.com/ISG-ICS/QueryBooster)
- **R05** — [WeTune code repository](https://github.com/WeTune/WeTune-code)
- **R06** — [Bao issue tracker](https://github.com/learnedsystems/BaoForPostgreSQL/issues)
- **R07** — [Balsa repository](https://github.com/balsa-project/balsa)
- **R08** — [Join Order Benchmark repository](https://github.com/gregrahn/join-order-benchmark)
- **R09** — [BenchBase repository](https://github.com/cmu-db/benchbase)
- **R10** — [SQLGlot repository](https://github.com/tobymao/sqlglot)
- **R11** — [Unsloth repository](https://github.com/unslothai/unsloth)
- **R12** — [Hugging Face TRL repository](https://github.com/huggingface/trl)
- **R13** — [Axolotl repository](https://github.com/axolotl-ai-cloud/axolotl)
- **R14** — [verl repository](https://github.com/verl-project/verl)
- **R15** — [OpenRLHF repository](https://github.com/openrlhf/openrlhf)
- **R16** — [Awesome SQL Query Rewrite discovery list](https://github.com/Ricardo-Ping/Awesome-SQL-Query-Rewrite)
- **R17** — [Verified SQL query rewrite course project](https://github.com/s-wangru/Verified-SQL-query-rewrite)
- **R18** — [DB-GPT repository](https://github.com/eosphoros-ai/DB-GPT)
- **R19** — [DB-GPT-Hub repository](https://github.com/eosphoros-ai/db-gpt-hub)
- **R20** — [pg_hint_plan historical issue](https://github.com/ossc-db/pg_hint_plan/issues/57)
- **R21** — [AQO implementation header](https://github.com/postgrespro/aqo/blob/master/aqo.h)
- **R22** — [AI4DB paper discovery list](https://github.com/Wind-Gone/awesome-ai4db-paper/blob/main/README.md)
- **R23** — [pg_hint_plan repository](https://github.com/ossc-db/pg_hint_plan)
- **R24** — [Bao repository (lowercase URL from original report)](https://github.com/learnedsystems/baoforpostgresql)
- **R25** — [Apache Calcite repository](https://github.com/apache/calcite)
- **R26** — [ReSequel repository](https://github.com/CoDS-GCS/ReSequel)
- **R27** — [ParSEval repository](https://github.com/sfu-db/ParSEval)
- **R28** — [Cardinality Estimation Benchmark repository](https://github.com/learnedsystems/ceb)
- **R29** — [Postgres Pro AQO repository](https://github.com/postgrespro/aqo)
- **R30** — [QUITE repository](https://github.com/Yuyang-Song/QUITE)
- **R31** — [LearnedRewrite repository](https://github.com/XuanheZhou/LearnedRewrite)
- **R32** — [E3-Rewrite paper HTML](https://arxiv.org/html/2508.09023v2)
- **R33** — [SPA paper HTML](https://arxiv.org/html/2606.08620v1)
- **R34** — [SQLancer repository](https://github.com/sqlancer/sqlancer)
- **R35** — [SQLsmith repository](https://github.com/anse1/sqlsmith)
- **R36** — [SPES repository](https://github.com/georgia-tech-db/spes)
- **R37** — [VeriEQL repository](https://github.com/VeriEQL/VeriEQL)
- **R38** — [SQLSolver repository](https://github.com/SJTU-IPADS/SQLSolver)
- **R39** — [GenRewrite paper abstract](https://arxiv.org/abs/2403.09060)
- **R40** — [SPA paper abstract](https://arxiv.org/abs/2606.08620)
- **R41** — [SQL-R1 repository](https://github.com/IDEA-FinAI/SQL-R1)
- **R42** — [LLM-R2 repository](https://github.com/DAMO-NLP-SG/LLM-R2)
- **R43** — [SQL-RewriteBench paper HTML](https://arxiv.org/html/2607.09251v2)
- **R44** — [Unofficial GenRewrite implementation](https://github.com/Orderheart/GenRewrite)
- **F01** — [Fireworks training overview](https://docs.fireworks.ai/fine-tuning/finetuning-intro)
- **F02** — [Fireworks managed training overview](https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro)
- **F03** — [Fireworks supervised fine-tuning](https://docs.fireworks.ai/fine-tuning/fine-tuning-models)
- **F04** — [Fireworks managed RFT deprecation notice](https://docs.fireworks.ai/fine-tuning/reinforcement-fine-tuning-models)
- **F05** — [Fireworks dedicated Training API](https://docs.fireworks.ai/fine-tuning/training-api/dedicated)
- **F06** — [Fireworks prompt caching](https://docs.fireworks.ai/guides/prompt-caching)
- **F07** — [Fireworks structured outputs](https://docs.fireworks.ai/structured-responses/structured-response-formatting)
- **F08** — [Fireworks Responses API](https://docs.fireworks.ai/guides/response-api)
- **F09** — [Fireworks model and deployment overview](https://docs.fireworks.ai/models/overview)
- **F10** — [Fireworks inference for RL rollouts](https://docs.fireworks.ai/guides/rollout-inference)
- **F11** — [Fireworks serverless Training API](https://docs.fireworks.ai/fine-tuning/training-api/serverless)
- **F12** — [Fireworks serverless inference pricing](https://docs.fireworks.ai/serverless/pricing)
- **F13** — [Fireworks official cookbook repository](https://github.com/fw-ai/cookbook)
- **F14** — [Fireworks x HUD RL training guide](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/hud-rl-training)
- **F15** — [Fireworks per-model training support matrix](https://docs.fireworks.ai/fine-tuning/models)
- **F16** — [Fireworks reinforcement-learning cookbook](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/rl)
- **F17** — [Fireworks agentic RL trajectory contract](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/agentic-rl)
- **F18** — [Fireworks training cost estimator](https://docs.fireworks.ai/fine-tuning/cost-estimator)
- **P01** — [PostgreSQL 16 pg_stat_statements](https://www.postgresql.org/docs/16/pgstatstatements.html)
- **A01** — [SQL-RewriteBench artifact linked by its paper](https://github.com/SQL-RewriteBench/benchmark)
- **A02** — [Microsoft DSB artifact linked by LLM-R2](https://github.com/microsoft/dsb)
- **A03** — [SQLStorm artifact linked by SQL-RewriteBench](https://github.com/SQL-Storm/SQLStorm)

[R01]: https://github.com/curtis-sun/LLM4Rewrite
[R02]: https://arxiv.org/html/2403.09060v3
[R03]: https://arxiv.org/html/2412.01661v2
[R04]: https://github.com/ISG-ICS/QueryBooster
[R05]: https://github.com/WeTune/WeTune-code
[R06]: https://github.com/learnedsystems/BaoForPostgreSQL/issues
[R07]: https://github.com/balsa-project/balsa
[R08]: https://github.com/gregrahn/join-order-benchmark
[R09]: https://github.com/cmu-db/benchbase
[R10]: https://github.com/tobymao/sqlglot
[R11]: https://github.com/unslothai/unsloth
[R12]: https://github.com/huggingface/trl
[R13]: https://github.com/axolotl-ai-cloud/axolotl
[R14]: https://github.com/verl-project/verl
[R15]: https://github.com/openrlhf/openrlhf
[R16]: https://github.com/Ricardo-Ping/Awesome-SQL-Query-Rewrite
[R17]: https://github.com/s-wangru/Verified-SQL-query-rewrite
[R18]: https://github.com/eosphoros-ai/DB-GPT
[R19]: https://github.com/eosphoros-ai/db-gpt-hub
[R20]: https://github.com/ossc-db/pg_hint_plan/issues/57
[R21]: https://github.com/postgrespro/aqo/blob/master/aqo.h
[R22]: https://github.com/Wind-Gone/awesome-ai4db-paper/blob/main/README.md
[R23]: https://github.com/ossc-db/pg_hint_plan
[R24]: https://github.com/learnedsystems/baoforpostgresql
[R25]: https://github.com/apache/calcite
[R26]: https://github.com/CoDS-GCS/ReSequel
[R27]: https://github.com/sfu-db/ParSEval
[R28]: https://github.com/learnedsystems/ceb
[R29]: https://github.com/postgrespro/aqo
[R30]: https://github.com/Yuyang-Song/QUITE
[R31]: https://github.com/XuanheZhou/LearnedRewrite
[R32]: https://arxiv.org/html/2508.09023v2
[R33]: https://arxiv.org/html/2606.08620v1
[R34]: https://github.com/sqlancer/sqlancer
[R35]: https://github.com/anse1/sqlsmith
[R36]: https://github.com/georgia-tech-db/spes
[R37]: https://github.com/VeriEQL/VeriEQL
[R38]: https://github.com/SJTU-IPADS/SQLSolver
[R39]: https://arxiv.org/abs/2403.09060
[R40]: https://arxiv.org/abs/2606.08620
[R41]: https://github.com/IDEA-FinAI/SQL-R1
[R42]: https://github.com/DAMO-NLP-SG/LLM-R2
[R43]: https://arxiv.org/html/2607.09251v2
[R44]: https://github.com/Orderheart/GenRewrite
[F01]: https://docs.fireworks.ai/fine-tuning/finetuning-intro
[F02]: https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro
[F03]: https://docs.fireworks.ai/fine-tuning/fine-tuning-models
[F04]: https://docs.fireworks.ai/fine-tuning/reinforcement-fine-tuning-models
[F05]: https://docs.fireworks.ai/fine-tuning/training-api/dedicated
[F06]: https://docs.fireworks.ai/guides/prompt-caching
[F07]: https://docs.fireworks.ai/structured-responses/structured-response-formatting
[F08]: https://docs.fireworks.ai/guides/response-api
[F09]: https://docs.fireworks.ai/models/overview
[F10]: https://docs.fireworks.ai/guides/rollout-inference
[F11]: https://docs.fireworks.ai/fine-tuning/training-api/serverless
[F12]: https://docs.fireworks.ai/serverless/pricing
[F13]: https://github.com/fw-ai/cookbook
[F14]: https://docs.fireworks.ai/fine-tuning/training-api/cookbook/hud-rl-training
[F15]: https://docs.fireworks.ai/fine-tuning/models
[F16]: https://docs.fireworks.ai/fine-tuning/training-api/cookbook/rl
[F17]: https://docs.fireworks.ai/fine-tuning/training-api/cookbook/agentic-rl
[F18]: https://docs.fireworks.ai/fine-tuning/cost-estimator
[P01]: https://www.postgresql.org/docs/16/pgstatstatements.html
[A01]: https://github.com/SQL-RewriteBench/benchmark
[A02]: https://github.com/microsoft/dsb
[A03]: https://github.com/SQL-Storm/SQLStorm

### Query and dataset artifacts inspected in the follow-up

- **W01** — [LLM4Rewrite/tpch at main · curtis-sun/LLM4Rewrite](https://github.com/curtis-sun/LLM4Rewrite/tree/main/tpch)
- **W02** — [LLM4Rewrite/dsb at main · curtis-sun/LLM4Rewrite](https://github.com/curtis-sun/LLM4Rewrite/tree/main/dsb)
- **W03** — [QUITE/dataset at main · Yuyang-Song/QUITE](https://github.com/Yuyang-Song/QUITE/tree/main/dataset)
- **W04** — [GitHub - DAMO-NLP-SG/LLM-R2](https://github.com/DAMO-NLP-SG/LLM-R2/tree/main)
- **W05** — [LLM4Rewrite/tpch/query17 at main · curtis-sun/LLM4Rewrite](https://github.com/curtis-sun/LLM4Rewrite/tree/main/tpch/query17)
- **W06** — [LLM4Rewrite/dsb/query001 at main · curtis-sun/LLM4Rewrite](https://github.com/curtis-sun/LLM4Rewrite/tree/main/dsb/query001)
- **W07** — [LLM4Rewrite/calcite at main · curtis-sun/LLM4Rewrite](https://github.com/curtis-sun/LLM4Rewrite/tree/main/calcite)
- **W08** — [QUITE/dataset/queries at main · Yuyang-Song/QUITE](https://github.com/Yuyang-Song/QUITE/tree/main/dataset/queries)
- **W09** — [benchmark/benchmark at main · SQL-RewriteBench/benchmark](https://github.com/SQL-RewriteBench/benchmark/tree/main/benchmark)
- **W10** — [join-order-benchmark/1a.sql at master · gregrahn/join-order-benchmark](https://github.com/gregrahn/join-order-benchmark/blob/master/1a.sql)
- **W11** — [SQLStorm/v1.0/tpch/queries at master · SQL-Storm/SQLStorm](https://github.com/SQL-Storm/SQLStorm/tree/master/v1.0/tpch/queries)
- **W12** — [LLM-R2/data/data_llmr2 at main · DAMO-NLP-SG/LLM-R2](https://github.com/DAMO-NLP-SG/LLM-R2/tree/main/data/data_llmr2)
- **W13** — [curtis-sun/LLM4Rewrite/main/tpch/query17/query17_0.sql](https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/tpch/query17/query17_0.sql)
- **W14** — [curtis-sun/LLM4Rewrite/main/tpch/query17/query17_1.sql](https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/tpch/query17/query17_1.sql)
- **W15** — [curtis-sun/LLM4Rewrite/main/dsb/query001/query001_0.sql](https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/dsb/query001/query001_0.sql)
- **W16** — [curtis-sun/LLM4Rewrite/main/calcite/calcite.jsonl](https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/calcite/calcite.jsonl)
- **W17** — [Yuyang-Song/QUITE/main/dataset/queries/tpch_queries.json](https://raw.githubusercontent.com/Yuyang-Song/QUITE/main/dataset/queries/tpch_queries.json)
- **W18** — [SQL-RewriteBench/benchmark/main/docs/dataset_setup.md](https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/docs/dataset_setup.md)
- **W19** — [SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs packages/cases/EQUIV-001/sql/benchmark_input.sql](https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/EQUIV-001/sql/benchmark_input.sql)
- **W20** — [SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs packages/cases/PERF-001/sql/benchmark_input.sql](https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/PERF-001/sql/benchmark_input.sql)
- **W21** — [SQL-Storm/SQLStorm/master/v1.0/tpch/queries/100.sql](https://raw.githubusercontent.com/SQL-Storm/SQLStorm/master/v1.0/tpch/queries/100.sql)
- **W22** — [gregrahn/join-order-benchmark/master/1a.sql](https://raw.githubusercontent.com/gregrahn/join-order-benchmark/master/1a.sql)
- **W23** — [SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs packages/cases/EQUIV-001/schema/schema_profile.yaml](https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/EQUIV-001/schema/schema_profile.yaml)
- **W24** — [SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs packages/cases/ROBUST-001/sql/benchmark_input.sql](https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/ROBUST-001/sql/benchmark_input.sql)
- **W25** — [SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs packages/cases/PG-AWARE-001/sql/benchmark_input.sql](https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/PG-AWARE-001/sql/benchmark_input.sql)
- **W26** — [curtis-sun/LLM4Rewrite/main/tpch/create_tables.sql](https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/tpch/create_tables.sql)
- **W27** — [curtis-sun/LLM4Rewrite/main/calcite/create_tables.sql](https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/calcite/create_tables.sql)
- **W28** — [microsoft/dsb/main/scripts/workload_config.json](https://raw.githubusercontent.com/microsoft/dsb/main/scripts/workload_config.json)

[W01]: https://github.com/curtis-sun/LLM4Rewrite/tree/main/tpch
[W02]: https://github.com/curtis-sun/LLM4Rewrite/tree/main/dsb
[W03]: https://github.com/Yuyang-Song/QUITE/tree/main/dataset
[W04]: https://github.com/DAMO-NLP-SG/LLM-R2/tree/main
[W05]: https://github.com/curtis-sun/LLM4Rewrite/tree/main/tpch/query17
[W06]: https://github.com/curtis-sun/LLM4Rewrite/tree/main/dsb/query001
[W07]: https://github.com/curtis-sun/LLM4Rewrite/tree/main/calcite
[W08]: https://github.com/Yuyang-Song/QUITE/tree/main/dataset/queries
[W09]: https://github.com/SQL-RewriteBench/benchmark/tree/main/benchmark
[W10]: https://github.com/gregrahn/join-order-benchmark/blob/master/1a.sql
[W11]: https://github.com/SQL-Storm/SQLStorm/tree/master/v1.0/tpch/queries
[W12]: https://github.com/DAMO-NLP-SG/LLM-R2/tree/main/data/data_llmr2
[W13]: https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/tpch/query17/query17_0.sql
[W14]: https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/tpch/query17/query17_1.sql
[W15]: https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/dsb/query001/query001_0.sql
[W16]: https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/calcite/calcite.jsonl
[W17]: https://raw.githubusercontent.com/Yuyang-Song/QUITE/main/dataset/queries/tpch_queries.json
[W18]: https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/docs/dataset_setup.md
[W19]: https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/EQUIV-001/sql/benchmark_input.sql
[W20]: https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/PERF-001/sql/benchmark_input.sql
[W21]: https://raw.githubusercontent.com/SQL-Storm/SQLStorm/master/v1.0/tpch/queries/100.sql
[W22]: https://raw.githubusercontent.com/gregrahn/join-order-benchmark/master/1a.sql
[W23]: https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/EQUIV-001/schema/schema_profile.yaml
[W24]: https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/ROBUST-001/sql/benchmark_input.sql
[W25]: https://raw.githubusercontent.com/SQL-RewriteBench/benchmark/main/benchmark/benchmark_inputs%20packages/cases/PG-AWARE-001/sql/benchmark_input.sql
[W26]: https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/tpch/create_tables.sql
[W27]: https://raw.githubusercontent.com/curtis-sun/LLM4Rewrite/main/calcite/create_tables.sql
[W28]: https://raw.githubusercontent.com/microsoft/dsb/main/scripts/workload_config.json
