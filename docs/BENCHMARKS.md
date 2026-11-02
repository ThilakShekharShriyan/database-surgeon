# Database Surgeon: repository data and benchmark protocol

Prepared November 1, 2026 PT. Status: inspected source artifacts and proposed benchmark protocol.
Companions: [research](RESEARCH.md), [architecture](ARCHITECTURE.md), [unfrozen manifest template](../benchmarks/manifest.template.json).

> Implementation update: six source-pinned public inputs now run on synthetic microfixtures in a 14-case development lab. See [WORKBENCH.md](WORKBENCH.md) for measured results. The full-scale public datasets and ordered-query track below remain future work.

## 1. What this document establishes

We inspected actual repository query files, query directories, schema files and data-setup instructions. This expands the earlier README-level research.

No public benchmark database was downloaded/loaded and no new provider benchmark was executed for this planning request. The current measured results remain the three-case pilot in [results/report.md](../results/report.md). The public workloads below require data admission, checker support and source pinning before measurement. This document is not a benchmark result.

Our current DB/evaluator is tied to the five pilot schemas and CASES. Importing a SQL file alone does not make it runnable through the existing CLI.

## 2. Which data the repositories use

| Repository | Data and query evidence | Scale/version evidence | What we should benchmark |
| --- | --- | --- | --- |
| [R-Bot](https://github.com/curtis-sun/LLM4Rewrite) | TPC-H orders/parts/suppliers; DSB retail; Calcite semantic/rule tests; actual SQL directories inspected | README lists TPC-H and DSB 10x/50x and Calcite 40M-row uniform/Zipfian instances; PG14.13 | Begin with a small reproducible cohort; preserve template lineage and uniform/skew tracks |
| [QUITE](https://github.com/Yuyang-Song/QUITE/tree/main/dataset/queries) | JSON query collections for TPC-H, DSB, Calcite, StackOverflow | PG14.13 in README; actual TPC-H file has repeated parameterizations | Group repeated template instances; test ordered top-k support |
| [LLM-R2](https://github.com/DAMO-NLP-SG/LLM-R2/tree/main/data/data_llmr2) | Queries, schemas and pools; README links TPC-H and DSB | PG14.4; demonstration-selector training | Identify whether a file contains prompts, gold rewrites or selector examples before using it |
| [ReSequel](https://github.com/CoDS-GCS/ReSequel) | Workloads under Experiments/workload/{DBMS}; originals, templates and selected rewrites are separate | Reports eight workloads including JOB, TPC-H, DSB, StackOverflow and Public BI; PG17.1/MySQL8/DuckDB | Use original PostgreSQL queries and metadata; do not mistake selected output folders for evaluation inputs |
| [SQL-RewriteBench](https://github.com/SQL-RewriteBench/benchmark) | 180 input packages, matching public reference bundle; TPC-DS/DSB physical data | Dataset instructions specify tpcds_sf10 and DSB; large data external to GitHub | Strong public reproduction/stress track, explicitly not a sealed final set |
| [Microsoft DSB](https://github.com/microsoft/dsb) | TPC-DS-derived retail with correlated tables, configurable distributions and query templates | Templates tested on PostgreSQL13 and SQL Server2019; README specifies correlated generation order | Parameter/selectivity and distribution-drift track; load tables coherently |
| [JOB](https://github.com/gregrahn/join-order-benchmark) | IMDb-derived joins with selective predicates and aggregate outputs | README describes an older IMDb snapshot and schema/import procedure | Join-heavy track after provenance/data access checks; small sampled data is a different benchmark |
| [SQLStorm](https://github.com/SQL-Storm/SQLStorm) | LLM-generated analytical SQL on TPC-H, TPC-DS, JOB and StackOverflow schemas | v1.0 describes PG17/Umbra/DuckDB compatibility filtering; driver examples include 1GB and much larger data | Complexity/robustness track on a pinned release; rerun using our paired timing protocol |

Dataset/schema reuse and data licensing must be checked separately from the optimizer repository's code license. Do not label DSB results official TPC-DS results; its own README explicitly distinguishes them.

## 3. Actual queries inspected and resulting requirements

### 3.1 R-Bot TPC-H Q17: correlated aggregation

Sources: [query17_0.sql](https://github.com/curtis-sun/LLM4Rewrite/blob/main/tpch/query17/query17_0.sql), [query17_1.sql](https://github.com/curtis-sun/LLM4Rewrite/blob/main/tpch/query17/query17_1.sql), [schema](https://github.com/curtis-sun/LLM4Rewrite/blob/main/tpch/create_tables.sql).

- Joins lineitem to part, filters brand/container, computes an aggregate price output.
- Uses a correlated AVG-based quantity threshold and scalar aggregate.
- The two files change parameter values/seeds. They are not an original/optimized pair.
- Both belong to one structural lineage group, not two independent train/test examples.
- The inspected DDL declares many NOT NULL fields but does not declare all key constraints one might assume from textbook TPC-H. Use actual loaded constraints when validating transformations.

Opportunity: decorrelation or repeated aggregate elimination, subject to duplicate/type/empty-input semantics. No speedup assumed in advance.

### 3.2 R-Bot DSB Q001: CTE, correlated aggregate, ordered result

Source: [query001_0.sql](https://github.com/curtis-sun/LLM4Rewrite/blob/main/dsb/query001/query001_0.sql).

- Aggregates store returns joined with date_dim.
- Joins customer/store/demographic dimensions and filters attributes.
- Compares grouped returns against a correlated average.
- Orders customer IDs and limits the result.

Requirements: appropriate DSB schema/data, numeric and division behavior, correlated CTE semantics, output ordering and LIMIT. The current bag checker is insufficient to claim full result-contract preservation.

### 3.3 Calcite tests: semantic stress rather than realistic business traffic

Sources: [calcite.jsonl](https://github.com/curtis-sun/LLM4Rewrite/blob/main/calcite/calcite.jsonl), [schema](https://github.com/curtis-sun/LLM4Rewrite/blob/main/calcite/create_tables.sql).

Inspected records include VALUES-based empty queries, UNION ALL/EXCEPT, windows, DISTINCT aggregates, EXISTS and correlated NOT IN. The file contains both input_sql and named rewrites.

- Send only input_sql and permitted metadata to a model.
- Keep reference rewrites evaluator-only.
- EMP and EMPNULLABLES have different nullability. Do not infer one table's constraints from the other.
- Some inputs are valid semantic edge cases but poor latency benchmarks.
- Reference transformations still need validation on the exact PostgreSQL contract.
- Keep this stress cohort separate from workload-frequency business-value estimates.

### 3.4 QUITE TPC-H collection: query IDs are not template IDs

Source: [tpch_queries.json](https://github.com/Yuyang-Song/QUITE/blob/main/dataset/queries/tpch_queries.json).

Inspected IDs 1-3 repeat the aggregate TPC-H Q1 shape with different date parameters. IDs 4-6 repeat the correlated minimum-cost Q2 shape with different constants. Subsequent records include joins, revenue grouping and ordered top-k results.

Assign template IDs from AST/lineage, not from each JSON id. A random row split would leak near-identical templates. Reuse of these known queries across repositories also requires cross-repository deduplication.

### 3.5 SQL-RewriteBench EQUIV-001

Sources: [input](https://github.com/SQL-RewriteBench/benchmark/blob/main/benchmark/benchmark_inputs%20packages/cases/EQUIV-001/sql/benchmark_input.sql), [schema profile](https://github.com/SQL-RewriteBench/benchmark/blob/main/benchmark/benchmark_inputs%20packages/cases/EQUIV-001/schema/schema_profile.yaml).

Inspected input joins store_sales, date_dim and item, aggregates sales by year/brand, and orders/limits the output. The schema profile names database tpcds_sf10 and contains column types, nullability, estimates and sample rows.

The profile is metadata, not a database dump. Its estimates and examples cannot replace actual loaded data fingerprints.

### 3.6 SQL-RewriteBench PERF-001: explicit degradation

Source: [input](https://github.com/SQL-RewriteBench/benchmark/blob/main/benchmark/benchmark_inputs%20packages/cases/PERF-001/sql/benchmark_input.sql).

The inspected file adds eight materialized count scans over catalog_sales, cross joins scalar count outputs, and retains a nested analytical aggregate. This is intentionally exposed repeated-work removal.

Report it as a synthetic/degraded opportunity, separate from naturally occurring inefficient SQL. A large win here does not establish typical customer savings. The original SQL remains the semantic reference; do not infer a preferred rewrite by copying its public reference.

### 3.7 SQL-RewriteBench ROBUST-001: nested wrappers and suspicious constants

Source: [input](https://github.com/SQL-RewriteBench/benchmark/blob/main/benchmark/benchmark_inputs%20packages/cases/ROBUST-001/sql/benchmark_input.sql).

The inspected query wraps a returns/customer query in nested CTE/projection layers. It also contains a template-looking string constant used as an equality filter.

Check result activity on the intended database and preserve the given SQL's semantics. Do not silently repair presumed generator intent. Add nonempty distinguishing fixtures if supported; an empty result on one database is weak semantic evidence.

### 3.8 SQL-RewriteBench PG-AWARE-001: dialect-aware syntax

Source: [input](https://github.com/SQL-RewriteBench/benchmark/blob/main/benchmark/benchmark_inputs%20packages/cases/PG-AWARE-001/sql/benchmark_input.sql).

The file uses PostgreSQL casts, SUBSTRING ... FROM ... FOR, INTERSECT, grouped aggregates, a long literal list and NULLS LAST ordering with LIMIT.

Our existing conservative keyword guard rejects FOR even in a legitimate SUBSTRING expression. Count that as a source-acceptance limitation. Replace the coarse check only through tested AST-aware policy; do not simply remove mutation/locking protection. A new benchmark must not silently drop cases the guard rejects.

### 3.9 SQLStorm TPC-H 100: windows and outer-join semantics

Source: [100.sql](https://github.com/SQL-Storm/SQLStorm/blob/master/v1.0/tpch/queries/100.sql).

Inspected structure includes supplier aggregation, customer left joins/counts, RANK, CTEs and a FULL OUTER JOIN with an ordered final output. Join multiplicity and NULL-generated rows matter.

This is a useful hard robustness case. LLM-generated analytical SQL is not necessarily a validated business question; preserve the input SQL, not a guessed business interpretation.

### 3.10 JOB 1a: selective multiway joins

Source: [1a.sql](https://github.com/gregrahn/join-order-benchmark/blob/master/1a.sql).

Joins five IMDb-related tables with LIKE/NOT LIKE and disjunctive filters, then computes MIN outputs. This tests join cardinalities, predicate handling and planning. It is not automatically a text-rewrite opportunity; keeping the original may be the right decision.

## 4. Reproduction contract and resource tiers

### Tier 0: existing pilot

Run the existing local checks and preserve results as smoke/development evidence. The 50k-order fixture remains useful for regression checks, not external workload comparison.

### Tier 1: laptop admission and semantic checks

Import a small number of licensed query/schema artifacts, pin their commits, and generate small constraint-respecting fixtures. Use these for syntax/support/counterexample testing.

Label synthetic tables based on TPC-H/DSB schemas as synthetic microfixtures, not official benchmark data. The local Docker allocation observed earlier was about 7.75 GiB RAM, so plan a modest workload and bounded disk use first.

### Tier 2: public reproduction

Use the generator-supported small scale and correct load procedure, then a second supported larger scale if resources permit. Record exact scale; performance on reduced/sampled data is not reproduction of a published full-scale result.

SQL-RewriteBench's setup names TPC-DS SF10 and DSB and says combined external data exceeds 10 GB. R-Bot's documented performance instances are larger still. Inspect disk/memory/time requirements before downloading or generating.

### Tier 3: production-like/sealed evaluation

New schema/template groups and independently generated instances, including parameter/skew changes and already-efficient queries. No held-out inputs or references enter training, retrieval, route selection or reward collection.

Choose a feasible pilot size from the budget. An illustrative first cohort is 40 public cases balanced across performance, semantics and robustness, plus 20 independently prepared cases. This is a pilot, not a promise that a tight noninferiority interval can be established.

## 5. Dataset admission checklist

Before any model call:

1. Record repository, commit, exact relative path and raw-file SHA-256. Browser-rendered markdown is not the original byte stream and must not be hashed as the canonical SQL.
2. Inspect license/third-party notices and record provenance.
3. Distinguish inputs, parameter variants, rewritten outputs, public reference targets, training demonstrations and published result logs.
4. Assign source lineage, structural template group, schema family, semantic tags and split.
5. Record actual table definitions/constraints, indexes, session settings and PostgreSQL version.
6. Load/generate data using reviewed narrow steps; never run a repository-wide setup script blindly.
7. Fingerprint row counts, content/manifest hashes, generator commit/flags/seeds and distributions.
8. Check original executability, required result contract, result activity, runtime/timeout, and supported oracle.
9. Estimate experiment API/DB costs and enforce caps.
10. Freeze input/split manifests, then execute the matched systems.

ReSequel's README says its all-in-one script deletes results and that database loaders may drop/recreate databases. Its scripts are references to inspect, not commands to run against our existing database.

## 6. Splits and leakage controls

Maintain three distinct collections:

- Training: own synthetic schemas/templates and reviewed public examples intentionally admitted for learning.
- Development/reproduction: public benchmark inputs used to tune prompts, rules, routers and data generators.
- Sealed final: new template/schema/instance groups unavailable to the learning loop.

All parameterizations and structural derivatives of one template stay in one group. Track cross-repository overlap: R-Bot, QUITE and LLM-R2 may include the same TPC-H/DSB query families.

The SQL-RewriteBench README explicitly calls its public release a development/reproduction split because reference rewrites are public. It is not a blind leaderboard dataset. New parameter values alone do not erase public-template familiarity.

If a source public query is used for training, none of its related variants can establish clean unseen-template generalization. Publish separate known-template/unseen-parameter and unseen-template/schema results.

## 7. Synthetic data with useful failure modes

Own training generator should vary multiple independent factors:

- Cardinality and join fan-out; unique versus duplicate keys.
- Nullability/NULL rates, all-NULL groups and NULL-free instances.
- Empty relations, unmatched outer-join rows and empty aggregate inputs.
- Uniform versus skewed distributions and correlated predicates.
- Numeric precision, zero values and arithmetic boundaries.
- AD/BC or restricted temporal domain, day boundaries, timezone/collation where admitted.
- Filter selectivity, index presence and already-optimal plans.
- Different schemas, names, constraints and query structures.

Generate constraints and data coherently. Do not inject NULLs into a NOT NULL TPC-H column and call it the same benchmark contract. That may be a separate robustness task on a different declared schema.

Use counterexample generation for correctness; use a separate larger representative instance for performance. Avoid a training corpus dominated by deliberately wasteful queries that are trivial to simplify.

DSB's README requires correlated table generation in the intended order and recommends generating all related tables together. The checked workload_config.json uses SQL Server paths/dialect; PostgreSQL generation requires an explicit adapted configuration, not running the example unchanged.

## 8. Running and scoring the systems

Freeze exact inputs, permitted context, indexes, database snapshots, result oracle, timeout, retry policy, model settings and budgets for all systems.

For each case:

1. Validate the original and capture context/plan.
2. Generate candidates only from permitted inputs.
3. Record no-op, unsupported, invalid, timed-out and erroneous outcomes.
4. Check full result semantics on the correctness instances.
5. Measure paired performance on the designated performance instance.
6. Confirm promising selections on fresh timing samples.
7. Record inference + validation + timing + any serving overhead.
8. Retain the original when no candidate passes.
9. Aggregate by template group, pool, schema, scale and traffic track.

The SQLStorm driver described in its README uses one execution/query in its sample setup. Our comparative measurements need our own repeated paired protocol; copying historical CSV times is not a new model evaluation.

Metrics must include full-denominator beneficial coverage, source acceptance, correctness mismatches, abstentions, runtime regressions, workload-weighted delivered time, optimizer latency and all-in cost. Timing-only geometric means on successes are supplementary.

Do not score supported ordered cases with our unordered bag oracle. Tie-sensitive LIMIT needs a valid contract or explicit unsupported status. Return-type checks, large-output limits and consistent snapshots are implementation requirements.

## 9. What blocks public benchmark execution today

- Public database data are not loaded.
- External artifact commits, raw hashes, licenses and physical configurations are not frozen.
- Current schemas/CASES are hardcoded to the pilot.
- The result oracle lacks the ordered/type-level contract needed by many inspected queries.
- The coarse SQL guard rejects legitimate PostgreSQL syntax in some cases.
- Model selection, Fireworks endpoint smoke tests, pricing and experiment budgets remain to be set.
- Final evaluation inputs have not been prepared independently of development.

These blockers are implementation tasks in [ARCHITECTURE.md](ARCHITECTURE.md). They must be resolved before claiming public-benchmark results.

## 10. Ready-to-use planning artifact

[manifest.template.json](../benchmarks/manifest.template.json) lists inspected representative sources, lineage groups, semantics and known prerequisites. It is intentionally marked NOT_FROZEN and NOT_EXECUTABLE; it contains no fabricated commit hashes, data readiness or performance results.

Next deliverable is an importer/preflight that replaces those unknowns with verified raw artifacts and loaded-instance evidence. Only a frozen, admitted manifest may drive a paid evaluation.
