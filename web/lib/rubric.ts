/** Judge-facing constants for the Fireworks hackathon rubric (40/25/20/10/5). */

export const BENCHMARK = {
  total: 171,
  dev: 98,
  heldout: 73,
  note: "Fixed eval_v2 case set; actual run coverage is reported separately. Configuration freeze hashes do not fully pin code, caches or database state.",
};

/** Progression versions — map to registry system names used in JSONL runs. */
export const VERSIONS = [
  {
    id: "v0",
    title: "Frontier baseline (raw)",
    system: "frontier-raw",
    model: "openai:gpt-6.1-sol",
    harness: "one model sample with schema and EXPLAIN; no system-side verify",
    blurb: "Closed-model baseline. Returned SQL is independently evaluated on the same fixtures.",
  },
  {
    id: "v1",
    title: "Open model off-the-shelf (raw)",
    system: "open-raw",
    model: "fireworks:accounts/fireworks/models/gpt-oss-120b",
    harness: "one model sample with catalog, guide and EXPLAIN; no system-side verify",
    blurb: "The complete Fireworks development run exposes the cost, latency and correctness tradeoff.",
  },
  {
    id: "v2",
    title: "+ Surgical harness",
    system: "open-harness",
    model: "Fireworks configured open model + harness (default gpt-oss-120b)",
    harness: "rules · catalog+guide · retrieval=3 · best_of=3 · repair=2 · precheck · verify",
    blurb: "Compare observed incorrect returns and beneficial coverage against open-raw, alongside verification overhead.",
  },
  {
    id: "v3",
    title: "+ Cascade router",
    system: "cascade-surgeon",
    model: "sqlglot → Fireworks GLM Flash → NVIDIA Nemotron; local fallback when Fireworks is unconfigured",
    harness: "Stage-0 AST ($0) then harnessed open models",
    blurb: "Rules can skip model calls on easy cases. Overall quality, cost and latency depend on actual stage coverage.",
  },
] as const;

export const LEDGER = [
  {
    version: "v0",
    config: { rules: false, catalog: false, guide: false, retrieval: 0, best_of: 1, repair: 0, verify: false },
    reproduce: ".venv/bin/python -m surgeon.eval run frontier-raw --split dev --trials 3",
  },
  {
    version: "v1",
    config: { rules: false, catalog: true, guide: true, retrieval: 0, best_of: 1, repair: 0, verify: false },
    reproduce: ".venv/bin/python -m surgeon.eval run open-raw --split dev --trials 1",
  },
  {
    version: "v2",
    config: { rules: true, catalog: true, guide: true, retrieval: 3, best_of: 3, repair: 2, verify: true, precheck: true },
    reproduce: ".venv/bin/python -m surgeon.eval run open-harness --split dev --trials 1",
  },
  {
    version: "v3",
    config: { cascade: "rules-only → open/nemotron harness", verify: true },
    reproduce: ".venv/bin/python -m surgeon.eval run cascade-surgeon --split dev --trials 1",
  },
] as const;

/** Product context; customer economics require measured workload frequencies. */
export const FINOPS = {
  user: "Platform DBAs + FinOps on PostgreSQL (RDS / Cloud SQL / AlloyDB), and the agentic layer above them (coding agents, text-to-SQL, ORM codegen).",
  problem:
    "Repeated filters and correlated subqueries can waste database time. Model-generated rewrites can change results, so candidate quality must be evaluated alongside optimization overhead and expected reuse.",
  privacyLoop:
    "Local recipe scoring and trace curation can produce specialist training examples. Hosted inference or training sends supplied SQL and context to the provider. Local serving and training require a separately configured local model; development examples used for training cannot establish unseen-case generalization.",
};
