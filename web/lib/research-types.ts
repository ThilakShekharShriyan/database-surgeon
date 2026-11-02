export type ResearchRecord = {
  case: string; outcome: string; latency_ms: number; cost_usd: number | null;
  calls: number; verify_ms: number | null; llm_ms: number | null;
  speedup: number | null; result_sql: string; errors: number;
  input_tokens: number; output_tokens: number;
  verdict: { original_ms?: number; candidate_ms?: number; reduction?: number;
    reason?: string; schema?: string; counterexample?: unknown };
};
export type ResearchSystem = {
  system: string; cases: number; trials: number; expected_cases: number; complete: boolean;
  accepted_rate: number; accepted_ci95: [number, number]; incorrect_returned_count: number;
  incorrect_returned_rate: number; wrong_candidates_caught: number; outcomes: Record<string, number>;
  geomean_speedup: number; cost_per_case_usd: number | null;
  latency_p50_ms: number; latency_p95_ms: number; calls_per_case: number;
  output_tokens_per_case: number; accepted_by_family: Record<string, number>;
  records: ResearchRecord[]; simulated: boolean;
};
export type McNemar = {
  table: number[][]; pairs: number; a_only: number; baseline_only: number;
  p_value: number | null; rate_difference_a_minus_baseline?: number;
  difference_ci95_template_bootstrap?: [number, number] | null;
  template_sensitivity?: McNemar & { definition: string };
};
export type PairedMetric = {
  pairs: number; excluded_pairs: number; mean_a: number | null; mean_baseline: number | null;
  mean_difference: number | null; difference_ci95_template_bootstrap: [number, number] | null;
  ratio_of_means_a_over_baseline: number | null; lower_is_better: boolean;
};
export type Comparison = {
  trial: number; pairs: number; expected_cases: number; complete: boolean;
  warnings: string[]; mcnemar: Record<string, McNemar>; paired_metrics: Record<string, PairedMetric>;
};
export type ResearchCase = {
  id: string; template: string; family: string; kind: string; sql: string;
  original_ms: number; source: string; headroom: boolean | null;
};
export type ResearchSplit = {
  cases_sha256: string; expected_cases: number; templates: number;
  systems: ResearchSystem[]; cases: ResearchCase[];
  comparisons: Record<string, Record<string, Comparison>>;
};
export type ResearchSnapshot = {
  generated_at: string; comparison_trial: number; source: string; warnings: string[];
  splits: Record<"dev" | "heldout", ResearchSplit>;
};
