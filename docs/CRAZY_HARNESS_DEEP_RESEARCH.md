# LLM-Powered PostgreSQL / SQL Query Optimization: A Decision-Maker's Research Synthesis
### As of November 2026

---

## Executive Summary

A combinatorial explosion of research and product activity in 2025–2026 has transformed how SQL query workloads are optimized. The field has split into three partly overlapping fronts: **(1) SQL-to-SQL rewrite** — using LLMs or learned search to emit semantically equivalent but faster SQL; **(2) query-level harness engineering** — orchestrating cheap rules, small models, verification gates, caches, and large models in cost-aware cascades; and **(3) production FinOps for agentic SQL traffic** — jointly planning query execution and LLM inference to slash per-query token cost by 27×–317× versus naïve baselines.

Key findings that should drive immediate decisions:

- **No existing rewrite system achieves both 0% incorrect rewrites and comprehensive coverage** on a hard benchmark (SQL-RewriteBench full-denominator CGOQ is negative for all seven evaluated systems) [38][48]. Correctness gates are the decisive engineering challenge, not rewrite generation.
- **Fine-tuning (SFT + RL/GRPO) beats harness-only on private in-distribution workloads**, but harness-first wins on latency, portability, and fast iteration; the optimal architecture is harness-native training (HarnessSQL pattern) [14].
- **FinOps leverage is enormous**: Snowflake reports 300× fewer LLM calls from AI-aware predicate ordering alone [39]; Quail reports 27× wall-clock speedup from joint query-inference planning [34][41]; EnumGRPO achieves 317× cost reduction vs. naïve agentic baselines [4][31]; AlloyDB proxy-model distillation reports 6,000× cost reduction on ai.if (internal tests, preview) [15][35].
- **pg_stat_statements-based workload fingerprinting + template-level caching** is the highest-leverage, lowest-risk upgrade for any PostgreSQL 16 rewrite agent [36][44].

---

## Part 1: Industry Products

### 1.1 EverSQL (now Aiven)

EverSQL, founded 2019, was acquired by Aiven to deliver AI-powered query optimizations and index recommendations for PostgreSQL and MySQL [52]. With 100,000+ engineers across 90 countries reported as users [52], it represents the largest deployed SQL-AI footprint. Aiven planned to roll out EverSQL-powered query optimization and index recommendations in H1 2024, with monitoring and alerting with auto-generated insights to follow [52]. EverSQL's core approach is rule-and-AI-assisted query rewriting plus index recommendation; it does not appear to use LLM fine-tuning for rewrite generation based on available evidence.

### 1.2 OtterTune (Closed)

OtterTune — the CMU spin-off founded by Andy Pavlo, Dana Van Aken, and Bohan Zhang that pioneered ML-driven knob tuning for PostgreSQL/MySQL on RDS — **ceased operations in 2024** [19]. It was the most academically rigorous ML database configuration tuner commercially deployed. Its closure leaves DBtune as the primary heir in the ML-knob-tuning market.

### 1.3 DBtune 4.0 (October 2026)

DBtune, a Stanford/Lund University spin-off (2020/2021, Malmö, Sweden), released **DBtune 4.0 on October 6, 2026**, expanding from server-parameter tuning to include index optimization and autovacuum monitoring as a unified Autonomous PostgreSQL vision [16][30]. Key capabilities:

- **Parameter tuning**: Tests configurations against workload and machine type; applies automatically or with user approval [16][30].
- **Index optimization**: Ranks index opportunities with expected impact, cost, and DDL; user decides whether to apply [16][30].
- **Autovacuum monitoring**: Identifies where autovacuum is falling behind [30].

Reported customer result: Midwest Tape saw average query runtime fall from 76 ms to 7 ms (~10×) in ~4 hours [16][17]. DBtune's own benchmark (Intel Xeon) reported 87% throughput increase in initial tuning, 43% disk I/O reduction, and 23% WAL reduction [17]. DBtune founder Nardi explicitly states that "fully autonomous Postgres is still some way off" and requires significant source-code adaptation [17]. DBtune offers both SaaS and on-prem (air-gapped) options, the latter with no internet connection for enterprise data privacy [19]. **Note**: The headline "50% cloud cost reduction" claim in press materials is not substantiated in body text [16].

DBtune uses workload-aware AI and ML optimization algorithms but does not appear to employ LLM-based SQL-to-SQL rewriting in its current release [30].

### 1.4 AWS: Performance Insights → CloudWatch Database Insights

AWS deprecated Performance Insights for RDS/Aurora on **June 30, 2026**, migrating to CloudWatch Database Insights [18]. Standard mode (free) retains only 7 days of data and lacks execution plans, per-query statistics, and fleet view. Advanced mode retains 15 months and adds these, but costs up to $292/month per 32-vCPU instance and $584/month per 64-vCPU instance in us-east-1 [18]. A reported production example reached ~$490/month for one db.r7g.8xlarge [18]. The transition adds FinOps pressure; alternatives like pganalyze are positioned at $100/month per instance [18].

There is **no evidence in available sources** that CloudWatch Database Insights or AWS DevOps Guru include LLM-based SQL rewrite capabilities. Amazon Q Developer's database features (schema recommendations, query assistance in IDE) exist but are not covered by the available evidence at the rewrite-harness level.

### 1.5 Azure SQL Automatic Tuning

Azure SQL's automatic tuning continuously monitors queries and automatically applies CREATE INDEX, DROP INDEX, and FORCE LAST GOOD PLAN recommendations [45]. Key operational characteristics:

- Recommendations applied only during low CPU/IO utilization windows [45].
- Automatic verification: if no improvement or regression detected, changes are reverted within 30 minutes to 72 hours [45].
- Managed Instance supports only FORCE LAST GOOD PLAN; Fabric SQL Database enables CREATE INDEX by default [45].
- History retained 21 days for Azure SQL Database [45].

Azure SQL automatic tuning is described as using AI/ML and having been "perfected on several million databases" [45], but the documentation does not reference LLM-based SQL rewriting. A speculative blog post about "SQL Server 2026 Full Automatic Tuning" is explicitly science-fiction, written as a thought experiment for T-SQL Tuesday, and should not be cited as product capability [21].

### 1.6 Google AlloyDB AI Functions and Proxy Models

Google's AlloyDB represents the most aggressive in-database AI inference architecture as of mid-2026:

- **AI functions** (`ai.generate`, `ai.if`, `ai.rank`, `ai.forecast`, `ai.summarize`, `ai.agg_summarize`, `ai.analyze_sentiment`) are generally available on PostgreSQL 17 instances [15][35].
- **Smart Batching** groups multiple rows into a single LLM call; Google internally reports 2,400× throughput improvement over row-at-a-time, reaching 10,000 rows/second for `ai.if` and `ai.rank` [15][35].
- **Proxy model (optimized mode, Preview)**: PREPARE statement trains a lightweight local logistic regression model on ~1,000 labeled rows from the frontier LLM. EXECUTE runs queries with the local model, falling back to the frontier model when proxy confidence is low [15][20][35]. Internal tests report **100,000 rows/second (23,000×) and 6,000× cost reduction** for `ai.if` [15][35]. These figures are from internal Google testing and apply specifically to `ai.if` in preview; they should not be generalized [15].
- Across 10 benchmarks, the proxy model is reported at 90%–102% of direct large-model F1, with 116% on one Amazon reviews sentiment test [35].
- Runtime accuracy checks sample rows and fall back to the frontier LLM if the check fails [20].
- Requires enabling `google_ml_integration.enable_ai_function_acceleration` flag (off by default) [20][35].
- Google also announced at Next'26: Database Observability Agent (Preview) monitoring AlloyDB/Cloud SQL/Spanner for root cause and remediation [22]; managed MCP servers (GA) for AlloyDB and Cloud SQL [22]; Gemini-powered fleet analytics proactively surfacing optimization opportunities [22].
- Google claims "near-100% text-to-SQL accuracy" for Data Agent tools in AlloyDB, Spanner, and Cloud SQL [22] — this is an official marketing statement without independently verified methodology.

### 1.7 Snowflake Cortex AISQL

Snowflake's Cortex AISQL is the most technically detailed production AI-SQL engine with published optimization techniques [39][40]:

- **AI-aware predicate ordering**: The AISQL optimizer treats LLM inference cost as a first-class optimization objective; a naive plan triggering 110,000+ model calls was reduced to 330 calls (300× improvement) by reordering `AI_FILTER` relative to joins [39].
- **Adaptive model cascading**: Routes rows to a lightweight proxy (e.g., Claude Haiku 4.5); escalates low-confidence rows to an oracle model (e.g., Claude Sonnet 4.5). Uses importance sampling and concentration-inequality-based thresholds learned at query runtime. Reports mean 2.9× speedup (65.5% time reduction) at 95.7% oracle quality retention across six public benchmarks [39][40].
- **Semantic join rewriting**: Detects when an AI-based join is equivalent to multi-label classification (`AI_CLASSIFY`), reducing inference calls from quadratic to linear (24 to 4 calls in the example). Reports 15×–70× faster execution (mean 31×) across eight benchmarks, often with improved F1 [39][40].
- Overall optimization: 2×–8× more performant plans on synthetic datasets and customer-modeled workloads [39][40].
- Multi-table queries are ~40% of AISQL workloads and consume >50% of compute time [40].

### 1.8 Databricks, BigQuery, MotherDuck

Available evidence confirms Databricks AI Functions, BigQuery AI functions, and MotherDuck all support AI-SQL row-level LLM invocation [41]. Detailed optimization architectures for these platforms are not covered in available sources beyond this confirmation.

### 1.9 pg_stat_statements-Based Tools

`pg_stat_statements` is the foundational workload fingerprinting layer for PostgreSQL. A critical operational issue: **agentic AI development tools and LLM-driven query generators create high-cardinality workloads** that rapidly exhaust the `pg_stat_statements` hash table [44]. Key facts:

- AI-assisted development tools generate unique one-off queries that create disproportionate `pg_stat_statements` entries [44].
- PostgreSQL 18 normalizes IN lists to one statement, reducing cardinality dramatically (671 unique statements → 120 for the same workload on Bluebox load test) [44].
- Remediation: set `pg_stat_statements.max` higher, upgrade to PostgreSQL 18, and work with development teams on ORM/AI query patterns [44].

---

## Part 2: Research Systems Landscape

### 2.1 Taxonomy

The research systems divide cleanly into five approaches:

| Approach | Systems | Fine-Tunes? | Correctness Method |
|---|---|---|---|
| Learned plan selection (hints) | Bao, Balsa | RL (value net) | Hint = semantically neutral |
| Rule-based search with learned ordering | LearnedRewrite, LLM-R2 | Contrastive model (LLM-R2) | Rules proven; MCTS search |
| Rule discovery + formal verification | WeTune, QueryBooster | No | SMT/proof assistant |
| LLM rewrite + verification harness | R-Bot, GenRewrite, LITHE, QUITE, ReSequel | No (harness only) | Statistical + formal equivalence |
| LLM rewrite + RL fine-tuning | E3-Rewrite, SPA, ReViSQL | Yes (GRPO/RLVR) | Multi-stage equivalence rewards |

### 2.2 Bao and Balsa: Learned Plan Selection

**Bao** treats per-query hint selection as a contextual multi-armed bandit, using Thompson sampling with a tree convolutional neural network value model [1]. It does not rewrite SQL; it guides the existing optimizer by selecting hint sets (boolean flags), preserving semantic equivalence by assumption [1]. Training takes ~1 hour; Bao adds overhead by running the optimizer multiple times per query, making it best for tail-dominated workloads [1].

**Balsa** is an end-to-end RL optimizer that learns join ordering and plan selection from a lightweight simulator bootstrapped with real execution feedback [2]. On PostgreSQL JOB, Balsa achieves up to 3.34× training speedup and 2.25× test speedup with censored-observation training; on JOB-Complex, up to 14.85× training and 7.43× test [2]. On DuckDB, gains are smaller (1.29× test on JOB) because DuckDB's vectorized engine reduces the runtime gap between alternative join orders [2]. **Censored-observation training** — treating timed-out queries as censored rather than penalizing predictions above the timeout threshold — improves exploration stability [2].

Neither Bao nor Balsa rewrites SQL text; they operate at the plan/hint level.

### 2.3 WeTune and QueryBooster: Rule Discovery

**WeTune** automatically discovers query rewrite rules inspired by compiler superoptimization: it enumerates logical query plans up to a size bound and searches for equivalent but more efficient plans [3]. Rules are represented as triples (source template, target template, constraint set) and verified with an SMT-based verifier (or SPES). It discovered 1,106 promising rules; 35 optimized queries from 20 popular open-source apps, reducing latency up to 99% on 247 queries missed by existing systems [3]. Key finding: even the latest SQL Server fails to rewrite 54% of ORM-generated queries that WeTune can handle; PostgreSQL fails 82% [3].

**QueryBooster** (referenced but not in primary sources) is noted to depend on user-proposed rules in specialized syntax, limiting its applicability [10].

### 2.4 LearnedRewrite

LearnedRewrite frames rule-selection as a search problem over Calcite rewrite rules, using Monte Carlo Tree Search with a hybrid/self-attention cost estimator [11]. It uses a heuristic algorithm when matched rules rarely overlap, and a full MCTS policy tree otherwise [11]. It operates without database access via a learned cost estimator, addressing privacy constraints [11]. On real datasets (15 slow queries), it reduced latency in 12/15 cases with >25.3% total latency reduction [11]. **Correctness caveat**: some Calcite rules do not guarantee semantic equivalence; proof assistant verification is used for some but not all rules [11]. ReSequel reports LearnedRewrite requires 16 hours to rewrite the IMDB workload while execution itself takes only 11 hours — a scalability ceiling [36].

### 2.5 LLM-R2

LLM-R2 uses an LLM to *recommend Calcite rewrite rules* rather than generate SQL directly, guaranteeing executability and equivalence because all candidates come from proven rules [10]. It selects demonstrations via a contrastive query-representation model trained curriculum-style (easy to hard) [10]. Reported execution time: 52.5%, 56.0%, 39.8% of original on TPC-H, IMDB, DSB respectively [10]. Direct LLM SQL generation is cited as producing only 67.86% executable queries (fine-tuned Granite-20B on BIRD) [10]. LLM-R2 does not fine-tune the LLM.

### 2.6 R-Bot

R-Bot is an evidence-guided LLM rewrite system deployed at Huawei with real customers [7]. Its key design principle: **do not let the LLM rewrite SQL directly**. Instead, the LLM selects and orders rules from established optimization engines, guided by offline-prepared rewrite evidence (rule specifications, Q&As) retrieved with a hybrid structure-semantics retrieval method [7]. Directly using GPT-4 for SQL rewriting on DSB yielded only a 5.3% success rate, motivating the evidence approach [7]. R-Bot requires no training [7]. A reflection stage uses database cost comparison plus an LLM check of whether rewrite recipes are realized [7]. Learning-based methods struggle with unseen schemas without hundreds of new training examples [7].

### 2.7 GenRewrite

GenRewrite (SIGMOD 2026) is the first holistic LLM-based rewrite system that operates beyond traditional rules [5][50][54]. It introduces **Natural Language Rewrite Rules (NLR2s)** — schema-free rule descriptions that serve as LLM hints and enable knowledge transfer across queries and workloads [50]. A counterexample-guided iterative correction technique fixes syntactic and semantic errors without discarding incorrect rewrites, reducing LLM cost [5][50]. On TPC-DS at ≥2× speedup threshold, GenRewrite improves 25 queries — 1.35× more than LLM-driven baselines and 2.6× more than LLM-enhanced rule-based baselines [5][50]. GenRewrite does not fine-tune models; it relies on prompting with NLR2 hints plus iterative correction. Since NLR2s contain no schema information, they can be bootstrapped from a previously trained GenRewrite on another workload [50].

### 2.8 LITHE

LITHE (EDBT 2026) is a five-stage LLM rewrite pipeline that leaves the DBA in the loop [12][43]:

1. Prompt-based rewriting with syntax retry loop
2. Cost filtering: discards rewrites more expensive than original
3. Fast statistical semantic equivalence check (sampling-based)
4. Token-probability-driven MCTS: explores top-k token paths when LLM confidence < threshold θ, addressing hallucination
5. Final provable checks (QED/SQLSolver) + robustness heuristics to discard "brittle" rewrites

On TPC-DS with PostgreSQL, LITHE reports geometric mean runtime speedup of **13.2** over native optimizer versus 4.9 for SOTA [12][43]. A Cost Productive Rewrite (CPR) is defined as ≥1.5× optimizer-estimated cost improvement on a slow query (>10s), providing headroom against runtime regressions [12]. Ablation shows incremental CPR gains: basic ensemble 15 CPRs → +3 from redundancy rules → +7 from statistics-infused rules → 26 CPRs with MCTS [43]. Average rewrite time: 5 minutes per CPR query at ~$0.045 (18,427 tokens) [43]. Tested on two commercial databases, yielding 12 and 9 CPRs [43]. LITHE does not fine-tune models.

### 2.9 QUITE

QUITE is a training-free, feedback-aware LLM agent system controlled by a finite state machine with Reasoning, Verification, Decision, and Termination stages [13]. It uses a structured knowledge base (official docs + web forums), a hybrid SQL corrector for equivalence, and an agent memory buffer [13]. A novel hint injection technique (pg_hint_plan style) forces the optimizer to follow the LLM-recommended plan [13]. Reports up to 35.8% execution time reduction over SOTA and 24.1% additional rewrites [13]. Even the most powerful LLMs produce syntax/semantic errors in ~20% of cases on direct rewriting; DeepSeek-R1 still produced 13.0% nonequivalent outputs with minimal execution improvements [13]. QUITE requires no training.

### 2.10 ReSequel

ReSequel (2026) addresses scalability as a first-class concern by operating at the template level rather than individual query level [36]. Key mechanisms:

- **Templatization**: Masks literals while preserving join graphs, aggregation, predicates, outer joins, window functions, correlated subqueries. The IMDB workload has 13,646 queries but only 79 distinct templates [36].
- **Metadata-guided LLM prompting**: Uses catalog and statistical metadata to infer template-specific rules, guiding the LLM toward effective transformations [36].
- **Two-level cache**: Query Cache for rewritten instances; Template Cache for verified variants; parameter substitution on cache hit [36].
- **Validation on downsampled data**: Syntax and result-correctness verified; top-1 candidate selected by runtime [36].

Reports workload-level speedups of up to 16× over native DBMSs and 22× over LLM-based systems, with individual queries exceeding 600×, across eight benchmarks (JOB, TPC-H, Stats, Public BI, IMDB, DSB, StackOverflow) and three DBMSs (PostgreSQL, MySQL, DuckDB) [36]. Does not fine-tune models. Limitation: dialect-specific operator coverage incomplete; unrecognized constructs cannot be templatized [36].

### 2.11 E3-Rewrite

E3-Rewrite (2025/2026) is the most complete **RL fine-tuning** approach to SQL rewriting [6][8][27]:

- **Fine-tunes** Qwen3 and LLaMA4 families with GRPO reinforcement learning [6][8].
- **Three-part reward**: executability (EXPLAIN check), equivalence (QED-Solver → LLM semantic judgment → result-set comparison), efficiency (cost reduction) [8].
- **Staged curriculum**: Stage 1 = correctness only; Stage 2 = add efficiency reward with rehearsal mechanism to prevent correctness forgetting [6][8].
- **Execution plan context**: EXPLAIN output linearized into text prepended to the LLM prompt; EXPLAIN ANALYZE during training, EXPLAIN at inference [8].
- **Retrieval pool**: Hybrid AST edit-distance + dense embeddings; verified high-speedup rewrites added to pool (data flywheel) [8].
- **Results on TPC-H (PostgreSQL 14)**: Average latency reduced from 78.81s to 29.67s; p90 from 300s to 51.37s; 98%+ equivalence ratio; Qwen 32B: 210 improved queries, 99.6% equivalence [6][8].
- GPT-4o LLM-only baseline gave 74.92s average (vs. 29.67s for E3-Rewrite), showing raw LLM rewriting gives minimal gain [8].
- Ablation: removing RL collapses equivalence ratio; removing plan hints sharply increases latency [6].

### 2.12 SPA

SPA (June 2026) extends GRPO with a **plan-aware multi-objective reward** for query rewriting fine-tuning on PostgreSQL 16 [9][26]:

- Rewards: semantic equivalence + textual rewrite distance (anti-reward-hacking) + physical-plan divergence + runtime speedup [9][26].
- **Probability-Gated Adaptive Reward Shaping**: unlocks higher-level rewards only after the rollout group masters lower-level objectives [9][26].
- **Plan-divergence gating**: only proceeds to runtime measurement when non-trivial plan divergence is detected, avoiding expensive execution for rewrites that compile to the same plan [9].
- **On-policy self-improvement**: recycles slowdown rewrites as targeted training signals [9][26].
- **SFT data**: rewrites promoted only if semantically equivalent and speedup > 1.1 [9].
- Training environment: PostgreSQL 16 on EC2 m5d.2xlarge, 32GB shared_buffers, 256MB work_mem [9].
- Workload: TPC-DS, TPC-H, SQLStorm-synthesized queries [9].

SPA is notable as a **PostgreSQL 16 native training environment** — directly relevant to the hackathon target.

### 2.13 HarnessSQL

HarnessSQL (2026) addresses the train–deploy mismatch in SQL agents: models trained on static SQL generation transfer poorly to deployed interactive harnesses [14]:

- **Harness-native SFT**: Trains on complete multi-turn harness trajectories (2,512 verified oracle episodes) rather than turn-split training [14].
- **Execution-reward RL**: Sparse terminal execution-based reward after SFT cold start [14].
- Results: Qwen3-8B: 15.5% → 45.2% on Spider 2.0-SQLite; Qwen3-14B: 22.2% → 54.8% [14].
- Non-harness post-training transfers poorly to deployed harness (9.6% vs. 30.4%) [14].
- Applying RL directly to base model without SFT: only 20.0%, showing cold-start trajectory supervision matters [14].
- **Current limitation**: Focused on SQLite; PostgreSQL, Snowflake, BigQuery dialect performance for small models remains a gap [14].

### 2.14 SQL-RewriteBench

SQL-RewriteBench (2026) is the most rigorous available benchmark for SQL-to-SQL rewriting [38][48]:

- **180 executable instances** across EQUIV, PERF, ROBUST, and DIALECT pools [38][48].
- **Correctness-gated**: A faster rewrite receives zero optimization credit if it changes the validated result [38][48].
- **Full-denominator CGOQ** (Correctness-Gated Optimization Quality): all 7 evaluated systems show *negative* full-benchmark CGOQ [38][48] — every system fails before rewriting, fails result checks, or returns correct-but-slower/neutral rewrites on enough instances to drag the aggregate negative.
- **Equivalence verifier landscape**: SQLSolver proved 14/180 pairs equivalent, returned 115 UNKNOWN, timed out on 43; VeriEQL proved 51 equivalent but returned ERROR on 129 [38][48]. This directly limits the value of formal verification gates.
- **Identified gaps**: broader SQL front ends, cleaner rule-executor interfaces, result-aware validation, more selective abstention policies [38][48].

### 2.15 ReViSQL

ReViSQL (SIGMOD 2027 artifact) achieves human-level Text-to-SQL on BIRD via RLVR fine-tuning of Kimi-K2.6 on BIRD-Platinum (2,462 expert-verified instances, errors corrected in 52.1% of SQL queries) [53]. Adds VeriEQL formal equivalence check + evidence-supervision reward on top of result-based reward [53]. Training: CISPO algorithm, LoRA rank 32, batch 64, group 16, learning rate 5e-5 [53]. Critically, **training on uncorrected BIRD Train *reduces* accuracy by 7.0 points vs. +7.2 from verified data** [33] — showing data quality dominates dataset size for RLVR. However, ReViSQL is primarily a text-to-SQL (NL→SQL) system, not a SQL-to-SQL rewrite system. Its VeriEQL integration and false-positive reward analysis are highly relevant to rewrite system design.

### 2.16 Microsoft QO-Verify

Microsoft (CIDR 2026, VLDB 2026) published a production-oriented LLM query tuning tool using GPT-4o-mini and GPT-5, with QO-Verify — a technique that reuses the SQL Server query optimizer's memo structure to verify semantic equivalence [42][49]:

- Verifies **37% of 3,100+ candidate rewrites** with median equivalence checking time 0.03s and P90 5.4s [42].
- SMT-based equivalence checkers (QED/VLDB 2024) verified **zero** real-world LLM-generated rewrites due to limited aggregation/outer-join support [42][49].
- Median real-world query gets **29% elapsed-time improvement** using only verified rewrites [42].
- 17% of rewrites on REAL-1 improve by ≥1.5× [42].
- A StackOverflow example: 5 LLM calls + 5 QO-Verify checks + 2 plan executions → 98%+ improvement in 78 seconds [49].
- Prompts: GENERAL, CTE, SUBQ (remove redundant computation), QHINT (return query hints), up to 3 invocations per model [42][49].

This represents the most pragmatic production deployment pattern: **execution-based result equivalence as the primary gate, with QO-Verify as a fast formal check where available**.

---

## Part 3: Harness Patterns for Maximum Efficiency

### 3.1 Cascading: Cheap Rules → Small Model → Large Model

The canonical efficiency pattern layers verification at each stage:

1. **Deterministic rules** (e.g., implicit-to-explicit join, redundant predicate removal): zero LLM cost, provably correct. In one evaluation, deterministic rules contributed 8–11 promotions per run on IMDB/JOB workloads [29].
2. **Rule-guided LLM** (LLM-R2, R-Bot style): LLM selects from a proven rule set; no SQL hallucination risk; medium cost [7][10].
3. **Small LLM with EXPLAIN context**: E3-Rewrite 14B or similar; fast inference; ~94.8% equivalence [8].
4. **Large LLM with full context**: GPT-5/Qwen 32B for hard queries only; highest cost, highest coverage.
5. **Abstention**: If no candidate passes the correctness gate with meaningful speedup, return original.

AlloyDB's proxy model architecture (proxy → frontier LLM fallback on low confidence) directly implements this cascade pattern for AI function calls [15][20][35].

Snowflake AISQL's adaptive model cascade implements the same pattern at query execution time for AI operators [39][40].

### 3.2 Verification Gates

Verification is the single hardest problem. Available evidence on gate types, from cheapest to most reliable:

| Gate Type | Coverage | Cost | Notes |
|---|---|---|---|
| EXPLAIN cost filter | High | Near-zero | Brittle: optimizer estimates can mislead runtime [12] |
| Syntax check (EXPLAIN dry-run) | High | Near-zero | Necessary but not sufficient |
| Formal SMT/symbolic verifier | ~8–28% (37% with QO-Verify) | Low-moderate | Fails on aggregations, outer joins, nesting [42][49] |
| Statistical result-equivalence (sampling) | High coverage | Moderate | Not formal; misses edge cases in NULL handling, etc. [29][38] |
| LLM semantic judgment | Medium | Moderate | Fallback when formal verifier returns UNKNOWN [8] |
| Full execution result comparison | Highest | Expensive | Practical only for offline/template-level workloads [36] |
| QO-Verify (optimizer memo reuse) | 37% of candidates | Very low (0.03s median) | SQL Server only; PostgreSQL equivalent not published [42] |

**Key insight from SQL-RewriteBench**: Existing verifiers (SQLSolver, VeriEQL) fail on the majority of complex real-world rewrites [38][48]. The Microsoft CIDR/VLDB result using QO-Verify (optimizer-memo-based) is the most promising direction for PostgreSQL, but no PostgreSQL-native equivalent is published yet.

GenRewrite's counterexample-guided correction — generating counterexamples to detect non-equivalence and iteratively correcting the rewrite — is a practical middle path [5][50][54].

### 3.3 Retrieval of Verified Rewrites

Multiple systems demonstrate that a retrieval store of verified rewrites is a high-leverage pattern:

- **ReSequel**: Two-level cache (Query Cache + Template Cache); template-level amortization means IMDB's 13,646 queries reduce to 79 templates for rewriting [36]. Cache hits served by parameter substitution at minimal cost.
- **E3-Rewrite**: Hybrid AST edit-distance + dense embedding retrieval; verified high-speedup rewrites added to pool as data flywheel [8].
- **LLM-R2**: Demonstration pool of successful rewrites; contrastive model for retrieval [10].
- **GenRewrite**: NLR2 repository that accumulates schema-free rules across workloads [50].
- **OLAP Semantic Cache** [51]: LLM-based query canonicalization to an OLAP Intent Signature achieves 82% hit rate vs. 28% (text) and 56% (AST-based), with zero false hits on controlled workloads; reduces backend compute 85–90%.

### 3.4 Workload Fingerprinting from pg_stat_statements

The operational pipeline for a PostgreSQL 16 rewrite agent:

1. Query `pg_stat_statements` periodically (e.g., every 5 minutes) for `total_exec_time`, `calls`, `mean_exec_time`, `query` text.
2. Normalize and fingerprint queries (strip literals → templates). PostgreSQL 18 does IN-list normalization automatically; for PG16, apply custom normalization [44].
3. Rank by `total_exec_time` (highest first) — these are the highest-leverage rewrite targets.
4. Detect high-cardinality signals: if the hash table refills in <30 minutes after reset, or deallocation counter grows, the workload is agentic/high-churn [44].
5. Apply template-level caching (ReSequel pattern) to avoid re-rewriting the same template with different literals [36].

**Agentic SQL traffic warning**: LLM-driven development tools generate high-cardinality unique queries that rapidly evict useful statistics [44]. This is a direct operational threat to any pg_stat_statements-based tuning approach.

### 3.5 Caching

- **Semantic OLAP cache**: 82% hit rate with LLM canonicalization + zero false hits on controlled star-schema workloads [51]. Confidence gating at threshold 0.5 raises precision to 76.9% [51]. Restricting NL to read-only cache access prevents cache poisoning [51].
- **Quail's KV-aware scheduling**: Retains only KV reusable by later operators; evicts shortest documents first; prevents 40% redundant token processing on BIO-4 [34][41].
- **Template-level rewrite cache**: Highest-leverage caching for rewrite agents because real workloads are 85–90% templated (Amazon Redshift data) [37].

### 3.6 Abstention

Abstention is an underrated capability. SQL-RewriteBench treats No-Rewrite Decision as a "missed opportunity rather than a success" [48], but from a correctness standpoint, abstaining when no candidate passes the correctness gate is the only way to guarantee 0 incorrect rewrites.

SPA's plan-divergence gate effectively implements abstention: if a rewrite compiles to the same physical plan as the original, no execution budget is spent [9]. LITHE's cost-filter discards rewrites that don't beat the original optimizer estimate [12][43]. The feedback-driven lifecycle paper explicitly states: "A false positive activation can repeatedly route future executions to a slower or incorrect formulation. A false negative only misses a possible optimization opportunity" [29].

**Practical rule**: Abstain if ≥1 of: (a) no candidate passes the result-equivalence check, (b) no candidate beats the baseline plan cost by a margin ≥ θ (e.g., 1.5× per LITHE's CPR definition [12]), (c) candidate is flagged as "brittle" by regression heuristics.

### 3.7 Best-of-N vs. Repair

- **Best-of-N (GenRewrite, LITHE ensemble)**: Generate N rewrites from different prompts/rules, verify each independently, select the best passing candidate. GenRewrite's NLR2 ensemble across multiple rule hints; LITHE's rule-type-specific single-rule prompts [5][12][50].
- **Iterative repair (QUITE, E3-Rewrite)**: If a rewrite fails verification, feed the failure as context and retry. QUITE's FSM with Verification and Decision stages [13]; E3-Rewrite's counterexample-guided correction [8]. Risk: multiple iterations increase latency significantly [8].
- **Hybrid**: Best-of-N with cheap prompts first; repair only for promising-but-failing candidates. LITHE's staged pipeline implements this naturally [12][43].

### 3.8 Plan-Aware Rewards

SPA demonstrates that **physical-plan divergence as a reward signal** is essential for meaningful rewrite learning [9][26]:

- Semantic equivalence alone is insufficient: many valid rewrites compile to identical physical plans and yield no speedup.
- Plan divergence gating avoids wasting execution budget on semantically different but physically identical rewrites [9].
- Runtime speedup reward only activates when plan divergence exceeds a threshold — a conditional reward structure [9].
- E3-Rewrite achieves similar effect by injecting EXPLAIN plan context into the LLM prompt, making the model aware of bottlenecks before generating rewrites [6][8].

### 3.9 Quail Joint Planning

Quail (Modal + CMU Full Stack Data Lab) jointly optimizes query planning and LLM inference scheduling as a single cost model [23][34][41]:

- Treats AI-SQL as a prefill-only workload (for boolean `AI.IF`, a single output token suffices) [23].
- KV-aware join-order search: retains multiple candidate plans, prunes only Pareto-dominated plans on (tokens, attention pairs, cached tokens) [23].
- Applies predicate push-down, filter ordering by selectivity, System R-style join ordering via dynamic programming [23].
- Fuses kernels (add-RMSNorm + fp8 quantization, per-head query/key RMSNorm + RoPE) [23].
- Uses cascade attention for joins to avoid KV replication of shared anchors [23].
- **Results**: 1.84× geometric mean speedup over vLLM on QUAIL-B benchmark; 14× on BIO-4 query; 27.55× on medical report query ($27.03 → $1.93) [34][41]. Benchmark and results are self-reported by the authors.
- Weakness: cross-document prefix sharing in agent-trace workloads; vLLM outperforms Quail on AGENT queries [23][41].
- Future directions: multi-tier KV caching, cross-query caching, radix indexes, on-the-fly fine-tuning/compilation of smaller models [23].

---

## Part 4: Fine-Tuning vs. Harness — When Each Wins

### 4.1 When Fine-Tuning (SFT/DPO/RL-LoRA) Wins

**Evidence strongly supports fine-tuning when:**

1. **You have verified in-distribution training data**: ReViSQL shows that training on *verified* BIRD-Platinum (+7.2 points) vs. unverified BIRD Train (−7.0 points) — data quality dominates scale [33][47]. HarnessSQL shows verified oracle trajectories are essential cold-start data for RL [14].

2. **The workload is private and cannot leave the VPC**: LearnedRewrite explicitly addresses privacy by using a learned cost estimator without database access [11]. Fine-tuned small models (Qwen 4B–14B, LoRA rank 32) can run entirely on-prem. DBtune offers on-prem optimization with no internet connection for the same reason [19].

3. **You have a stable recurring workload with accumulated verified rewrites**: E3-Rewrite's data flywheel — adding verified high-speedup rewrites back into the retrieval pool — compounds over time [8]. SPA's SFT data is promoted only when speedup > 1.1 and semantic equivalence holds [9].

4. **You need to eliminate plan-equivalent rewrites**: SPA's plan-divergence reward teaches the model to generate rewrites that actually change the physical plan, not just the text [9][26]. A harness alone cannot teach this; it can only filter it.

5. **Tail latency is the target**: SPA reports "strong tail-latency gains" and substantially reduced harmful slowdown rewrites on OOD workloads [9][26]. E3-Rewrite reduced p90 from 300s to 51s [6].

**Risks of training on wrong SQL:**

- Training on result-based rewards alone has a **32.8% false positive rate** (semantically wrong SQL that matches results on the concrete training database) [33][47].
- Training on unverified data reduces accuracy [33][47].
- Reward hacking: models learn to generate near-identical SQL strings to exploit correctness rewards [9]. SPA's Levenshtein distance penalty (λ=0.01) addresses this [9].
- Empty-result queries: `SELECT 1 WHERE False` gets maximum reward on result-based RLVR — a known pathology [47].
- The model may "forget" correctness while chasing efficiency in Stage 2 RL [8] — requiring explicit rehearsal mechanisms.

### 4.2 When Harness Alone Wins

**Harness-only architectures win when:**

1. **Fast iteration and zero training cost matter**: R-Bot deploys at Huawei with no training; LITHE and QUITE deploy via prompting [7][12][13]. This is the right starting point for any hackathon or MVP.

2. **The LLM backbone changes frequently**: EnumGRPO's in-context RL "distills planning heuristics into the prompt, without gradient updates" [4][31]. Natural-language heuristics transfer across model generations; fine-tuned weights require retraining on every model upgrade [4][31].

3. **The workload is highly heterogeneous (OOD)**: R-Bot notes that learned rewrite methods "struggle to adapt to unseen schemas without additional training on hundreds of new examples" [7]. ReSequel's template-level approach works across 8 benchmarks and 3 DBMSs without fine-tuning [36].

4. **You cannot afford the equivalence verification failures that corrupt training data**: If you cannot verify rewrites reliably, training on unverified data actively harms performance [33][47].

5. **Latency SLA is tight**: Multi-iteration RL inference at training time adds significant overhead. QUITE notes that "iterative correction frameworks may require multiple inference rounds to converge, significantly increasing execution time" [8].

### 4.3 The Optimal Architecture: Harness-Native Training

HarnessSQL's key finding is that the *gap* between training and deployment is the primary cause of performance collapse [14]. The solution is not harness OR fine-tuning, but **fine-tuning that preserves full harness interaction structure**:

- Train on complete multi-turn harness trajectories (full context, not turn-split) [14].
- Use oracle-verified teacher trajectories for SFT cold start before RL [14].
- Apply sparse execution-based terminal rewards for RL [14].
- This pattern is applicable to a PostgreSQL 16 rewrite agent: train with the same verification harness used at deployment, on verified accepted rewrites from production.

### 4.4 The Data Flywheel for Private Workloads

For private workloads that cannot leave the VPC, the operational flywheel is:

```
pg_stat_statements → fingerprint → template → 
harness rewrite attempt → verification gate (result-equivalence on downsampled data) → 
if accepted: add to retrieval pool + SFT data queue → 
periodic LoRA fine-tune on verified pool → 
deploy fine-tuned model → repeat
```

This mirrors E3-Rewrite's continual retrieval pool update [8] combined with HarnessSQL's verified trajectory SFT [14]. The key property: **only verified-equivalent, speedup-positive rewrites enter training data**, preventing reward corruption.

---

## Part 5: PostgreSQL 16 Rewrite Agent — "Crazy but Practical" Upgrades

### Design Constraints
- **0 incorrect rewrites**: Every rewrite that reaches a user must pass a correctness gate.
- **Beat frontier raw baseline on fixed evals**: The baseline is "ask GPT-5/Claude directly to rewrite SQL" — which achieves ~5.3% success on DSB [7] and shows minimal improvement over original on TPC-H without execution context [8].
- **PostgreSQL 16 specifically**: SPA trains on PG16 [9]; E3-Rewrite on PG14 [8]; LITHE tested on PG16 (TPC-DS 100GB) [43].

### Upgrade 1: Correctness-Gated Multi-Stage Verification (Highest Priority)

Implement a staged gate that mirrors the best available practice:

1. **EXPLAIN dry-run** (syntactic validity): reject immediately if EXPLAIN fails.
2. **Cost filter**: reject if rewrite cost estimate > original × 0.9 (preserve buffer for estimate noise).
3. **Statistical result-equivalence on downsampled data**: Run both original and rewrite on a sample (1,000–10,000 rows or a schema-representative subset). Flag LIMIT-without-ORDER, volatile functions, and NULL-sensitive outer joins as inconclusive rather than equivalent [29].
4. **Paired runtime benchmark**: At least 30 paired executions; median improvement ≥ 2%; one-sided paired t-test p ≤ 0.05; regression guard [29].
5. **Abstain if not all gates pass**.

This produces **zero incorrect rewrites by construction**, at the cost of coverage. SQL-RewriteBench shows this is the right tradeoff: negative CGOQ for all seven evaluated systems means coverage without correctness gates is worse than abstaining [38][48].

### Upgrade 2: Template-Level Workload Fingerprinting + Cache (Second Priority)

- Deploy ReSequel's two-level cache architecture [36] on top of pg_stat_statements fingerprints [44].
- Templates amortize rewrite cost across repeated query shapes (85–90% of real workloads are templated [37]).
- On a cache hit: substitute parameters, run EXPLAIN cost check (cheap gate), return cached rewrite.
- On a cache miss: invoke full harness, add verified result to both caches.

**Expected impact**: 85–90% of queries served from cache after warm-up; full harness cost amortized over the template's occurrence frequency.

### Upgrade 3: EXPLAIN Plan Context in LLM Prompt (Third Priority)

Use EXPLAIN (FORMAT JSON) output, parsed into:
- Cardinality-flow hints (which operations process the most rows)
- Categorized, ranked operator summaries (SPA's Plan Parser format [9])
- Linearized text prepended to the prompt (E3-Rewrite format [8])

Switch to EXPLAIN (not EXPLAIN ANALYZE) at inference to reduce latency while preserving structural patterns [8]. This alone converts GPT-4o from ~5% rewrite success [7] to >25% on relevant workloads [8].

### Upgrade 4: SPA-Style Plan-Divergence Pre-Filter

Before executing a candidate rewrite for benchmarking, compare the EXPLAIN JSON plan of original and rewrite:

- If plans are structurally identical (same operator tree, same join order), **discard without execution** [9].
- Only execute pairs with non-trivial plan divergence.

This eliminates the largest source of wasted execution budget: semantically valid but plan-equivalent rewrites.

### Upgrade 5: NLR2 Rule Repository (GenRewrite Pattern)

Maintain a growing repository of Natural Language Rewrite Rules [5][50]:

- Initialize with rules derived from successful rewrites on public benchmarks (TPC-DS, JOB).
- Since NLR2s contain no schema information, they are safe to share across workloads and organizations [50].
- Each LLM call includes top-k retrieved NLR2s as few-shot hints.
- On a new verified rewrite: extract a candidate NLR2 (ask the LLM to describe the transformation in natural language), add to repository.

This creates a schema-safe knowledge base that compounds across the deployment lifetime.

### Upgrade 6: Cascading Model Routing (FinOps Priority)

```
Query complexity score (from template + EXPLAIN) 
→ LOW: 4B model (Qwen3 4B FP8, local/on-prem) 
→ MEDIUM: 14B model (Qwen3 14B FP8) 
→ HIGH: 32B model or GPT-5 API
```

ReSequel shows template-level metadata provides sufficient signal to route [36]. LOTUS's model cascade with recall/precision targets provides the statistical framework for routing thresholds [32]. This can cut 50–75% of LLM API spend on medium-complexity queries.

### Upgrade 7: Harness-Native LoRA Fine-Tuning on Verified Accepts (Private Workload Flywheel)

Once the cache accumulates ~500–2,000 verified (original, rewrite) pairs from production:

- Apply SFT on verified pairs using LoRA rank 32 (ReViSQL training config [53]).
- Use GRPO/CISPO RL with the full harness (SPA [9], HarnessSQL [14]) and reward structure: equivalence → plan divergence → speedup.
- Fine-tune on Qwen3 4B–14B; the resulting model serves most queries locally without API calls.
- Use SQL-RewriteBench (180 instances, four pools) as the fixed eval to verify no regression [38][48].

**VPC containment**: All training happens on-prem; no SQL leaves the cluster. The LLM API is only called during the initial rule generation and for high-complexity queries until the fine-tuned model reaches sufficient coverage.

### Upgrade 8: Semantic Cache for Agentic SQL Traffic (Agentic Boom Defense)

For agentic SQL traffic (LLM agents generating high-cardinality unique queries [44]):

- Deploy the OLAP Semantic Cache [51] with LLM canonicalization for dashboard/OLAP queries (star-schema compatible workloads).
- 82% cache hit rate on compatible workloads, zero false hits on controlled workloads [51].
- Restrict NL-to-cache-hit to SQL-seeded reuse only (no NL writes to cache) to prevent poisoning [51].
- For non-OLAP agentic queries, increase `pg_stat_statements.max` and upgrade to PostgreSQL 18 for IN-list normalization [44].

---

## Part 6: Production FinOps for Agentic SQL Traffic

### 6.1 The Cost Stack

For agentic SQL workloads, costs accumulate across five layers:

| Layer | Cost Driver | Mitigation |
|---|---|---|
| LLM API calls per row | $0.10–$50/M tokens; output 3–8× input [25] | Proxy models, batch processing, caching |
| Context accumulation | Step 10 of agent loop costs ~10× step 1 [24] | Context window management, summarization |
| Reasoning model hidden tokens | Billed as output, invisible in response [25] | Cap max_tokens; prefer instruct over reasoning models for SQL rewrite |
| Repeated system prompt | 100K-token system prompt on every call [24] | Prompt caching (50–90% input cost reduction at 90% discount on cache reads [25]) |
| GPU/compute for self-hosted | Fixed hourly; calculate crossover volume [24] | At high volume, on-prem Qwen3 4B FP8 |

### 6.2 Documented FinOps Wins

| Technique | Reported Savings | Source | Caveats |
|---|---|---|---|
| AlloyDB proxy model (ai.if) | 6,000× cost vs. frontier LLM | [15][35] | Internal test; preview; ai.if only |
| AlloyDB Smart Batching | 2,400× throughput | [15][35] | Internal test; ai.if and ai.rank |
| Cortex AISQL AI-aware predicate ordering | 300× fewer LLM calls | [39] | Synthetic/customer-modeled; specific query pattern |
| Cortex AISQL model cascade | 2.9× speedup, 65.5% time reduction | [39][40] | Mean across 6 benchmarks; 4.3 F1 point drop |
| Cortex AISQL semantic join rewrite | 15×–70× (mean 31×) speedup | [39][40] | Mean across 8 benchmarks |
| Quail joint query-inference planning | 1.84× geomean; 27.55× on BIO-4 | [34][41] | Self-reported; research system |
| EnumGRPO in-context RL | 317× cost reduction vs. hybrid baseline | [4][31] | SWAN benchmark; $0.011/query |
| LOTUS model cascade | Up to 1,000× acceleration | [32] | Specific operator types; statistical guarantees |
| Semantic OLAP cache | 85–90% compute reduction | [51] | Star-schema/OLAP queries; controlled workloads |
| Template-level rewrite cache (ReSequel) | 79 templates for 13,646 IMDB queries | [36] | Template workloads only |
| Model routing to smaller models | 50%+ cost reduction | [25] | Quality-dependent |
| Prompt caching (API providers) | 50–90% input cost reduction | [25] | Cache hit rate dependent |
| Batch processing | 50% off at OpenAI/Anthropic/Google/Mistral | [25] | Non-time-sensitive only |

### 6.3 The Agentic SQL Call Boom

The FinOps risk from agentic SQL traffic is qualitatively different from traditional workloads:

- **Exponential context growth**: Each agent turn adds tool outputs and history; step 10 costs ~10× step 1 [24].
- **Untagged LLM calls**: Agent frameworks don't propagate organizational metadata; bills arrive 24–48 hours after consumption [24]. A recursive agent can exhaust a monthly budget before dashboards reflect it [24].
- **High cardinality disrupts pg_stat_statements**: Agentic query patterns evict legitimate workload statistics [44].
- **98% of FinOps practitioners now manage AI spend** (up from 31% in 2024) per FinOps Foundation 2026 survey [24][25].

**Recommended governance architecture**:
1. Tag every LLM call with feature/user/workload metadata at the SDK level.
2. Set hard `max_tokens` caps per query class.
3. Route classification/filter tasks (AI.IF equivalents) to proxy models or small on-prem models.
4. Implement circuit breakers: if per-hour token spend exceeds a threshold, fall back to non-AI paths.
5. Use PostgreSQL 18 IN-list normalization or custom normalization middleware to control pg_stat_statements cardinality from agentic workloads [44].

---

## Part 7: Prioritized Recommendations for Hackathon/Product Pitch

### Priority 1: Correctness-Gated Harness with EXPLAIN Context (Build First, Day 1)

**Why**: Beats the frontier raw baseline immediately. GPT-5 asking "rewrite this SQL" fails ~95% on DSB [7] and gives minimal speedup without execution context [8]. Adding EXPLAIN JSON context + cost filter + result-equivalence gate produces a demonstrably correct and faster system from day 1.

**What to build**:
- Parse pg_stat_statements for top queries by total_exec_time.
- Fingerprint → template → check template cache (hit → return).
- Miss → call LLM with EXPLAIN JSON plan context + NLR2 hints.
- Gate with: EXPLAIN syntax check → cost filter (1.5× CPR threshold) → result-equivalence on downsampled data.
- If passes: add to template cache, return rewrite. If fails: return original.

**Correctness guarantee**: By construction, every returned rewrite has passed execution-based result equivalence on representative data. This is the same mechanism used by Microsoft's production tool [42][49] and the feedback-driven lifecycle paper [29].

### Priority 2: Template-Level Cache + NLR2 Repository (Build Second, Day 1–2)

**Why**: Amortizes LLM cost across repeated queries (85–90% of workloads) [37] and builds a compounding knowledge asset.

**What to build**:
- Two-level cache: Query Cache + Template Cache (ReSequel pattern [36]).
- NLR2 repository: Extract schema-free rule descriptions from verified rewrites; inject top-k at inference [5][50].
- Template-level retrieval: Hybrid AST edit-distance + embedding similarity (E3-Rewrite pattern [8]).

### Priority 3: Model Cascade Routing (Day 2)

**Why**: 50%–75% LLM API cost reduction [25] with minimal quality impact if routing is based on template complexity.

**What to build**:
- Score template complexity (join count, subquery depth, window function presence, cardinality estimates from EXPLAIN).
- Route LOW → Qwen3 4B local; MEDIUM → Qwen3 14B; HIGH → GPT-5/Claude API.
- Verify each tier's rewrite with the same correctness gate; escalate to larger model only on gate failure.

### Priority 4: SPA/E3-Rewrite Style LoRA Fine-Tuning on Verified Pool (Private Workload, Week 2+)

**Why**: Private workloads cannot use APIs; fine-tuned small models match or exceed large API models on in-distribution patterns with 7–8× lower inference cost [47].

**What to build**:
- Accumulate 500–2,000 verified (original, rewrite) pairs from production harness.
- Apply LoRA rank 32 SFT on Qwen3 4B or 14B using GRPO with the correctness gate as reward [9][53].
- Use SQL-RewriteBench (180 instances) as fixed eval to prevent regression [38][48].
- Deploy fine-tuned model as the MEDIUM tier in the cascade; reduce API calls further.

### Priority 5: Semantic OLAP Cache for Agentic SQL Traffic (Agentic Boom Defense, Week 3+)

**Why**: Agentic SQL generates high-cardinality unique queries that destroy pg_stat_statements utility [44]. Semantic caching intercepts 82% of compatible OLAP queries before they hit the database [51].

**What to build**:
- Canonicalize SQL (and NL queries from AI agents) to an OLAP Intent Signature [51].
- SQL-seeded reuse only; NL restricted to cache reads [51].
- Confidence gate at 0.5 for NL canonicalization (76.9% precision at 36.5% coverage) [51].
- Monitor pg_stat_statements deallocation counter as a high-cardinality alarm [44].

---

## Confidence and Uncertainty Notes

**High confidence**: Verification gate patterns, pg_stat_statements fingerprinting mechanics, AlloyDB smart batching architecture, Cortex AISQL predicate ordering, SPA training on PostgreSQL 16, SQL-RewriteBench negative CGOQ finding for all evaluated systems.

**Medium confidence**: Reported speedup figures (ReSequel 16×, LITHE 13.2×, E3-Rewrite 3×, Quail 27×) — all are self-reported by system authors on specific benchmarks; independent replication is sparse or absent.

**Low confidence / should verify**: AlloyDB proxy model 6,000×/23,000× figures (internal Google testing, preview only, ai.if only) [15][35]; DBtune 50% cloud cost reduction headline claim (not substantiated in body text) [16]; Quail 317× claim from a secondary source [34] that partially attributes results to UC Berkeley rather than CMU/Modal.

**Missing evidence**: EverSQL's technical rewrite architecture post-Aiven acquisition; Amazon Q Developer's specific database rewrite features; QueryBooster's current technical design; BIRD benchmark coverage for PostgreSQL 16-specific SQL features; any independent validation of Balsa or SPA results by third parties.

---

*This synthesis covers research and products as documented in primary and secondary sources retrieved as of November 2026. All speedup and cost-reduction claims reflect authors' or vendors' own evaluations unless noted; treat as directional signals for system design prioritization rather than guaranteed production outcomes.*

---
Source: https://agent.tinyfish.ai/playground/research/share/01a19dd5-bba8-7471-8c77-8657d273bae7
