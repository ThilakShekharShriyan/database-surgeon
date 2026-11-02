"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { ResearchSnapshot } from "@/lib/research-types";
import { ArchitectureDiagram } from "./research-diagrams";
import { ProductShell } from "./product-shell";
import { pickTopRewrites } from "./rewrite-gallery";
import { money, percent, seconds } from "./research-charts";

function pLabel(v: number | null | undefined) {
  if (v == null) return "—";
  return v < 0.0001 ? v.toExponential(1) : v.toFixed(3);
}

export function HomePitch({ data }: { data: ResearchSnapshot | null }) {
  const systems = data?.splits.dev.systems || [];
  const harness = systems.find((s) => s.system === "open-harness");
  const raw = systems.find((s) => s.system === "open-raw");
  const frontier = systems.find((s) => s.system === "frontier-raw");
  const rules = systems.find((s) => s.system === "rules-only");
  const fastH = systems.find((s) => s.system === "fw-fast-harness");
  const cases = data?.splits.dev.cases || [];
  const featured = useMemo(
    () => (harness ? pickTopRewrites(cases, harness.records, 1)[0] : null),
    [cases, harness],
  );
  const vsRaw = data?.paired_stats?.comparisons?.find(
    (c) => c.system === "open-harness" && c.baseline === "open-raw",
  );
  const vsFrontier = data?.paired_stats?.comparisons?.find(
    (c) => c.system === "open-harness" && c.baseline === "frontier-raw",
  );
  const vsRules = data?.paired_stats?.comparisons?.find(
    (c) => c.system === "open-harness" && c.baseline === "rules-only",
  );

  const acceptH = harness ? percent(harness.accepted_rate) : "62.2%";
  const acceptR = raw ? percent(raw.accepted_rate) : "46.9%";
  const acceptF = frontier ? percent(frontier.accepted_rate) : "56.1%";
  const wrongR = raw?.incorrect_returned_count ?? 11;
  const gapRaw = vsRaw ? (vsRaw.bootstrap_accept_gap.mean * 100).toFixed(1) : "15.4";
  const ciRaw = vsRaw
    ? `[${(vsRaw.bootstrap_accept_gap.ci95[0] * 100).toFixed(1)}, ${(vsRaw.bootstrap_accept_gap.ci95[1] * 100).toFixed(1)}]`
    : "[5.1, 26.8]";

  return (
    <ProductShell ctaHref="/research" ctaLabel="Scoreboard charts">
      <main className="ps-home ps-research ps-forge">
        <header className="ps-paper-head">
          <p className="ps-kicker">FORGE SUBMISSION · NOV 2, 2026 · FIREWORKS × NVIDIA</p>
          <h1>Database Surgeon</h1>
          <p className="ps-abstract">
            I built a verify-or-abstain PostgreSQL rewrite system on Fireworks. Open models propose
            faster SQL; the harness accepts only when sealed fixtures (incl. null/skew) match{" "}
            <em>and</em> median SQL runtime improves by ≥20% — otherwise it returns the original. On
            locked eval_v2 (98 dev), Fireworks <code>gpt-oss-120b</code> raw accepts {acceptR} but
            returns <strong className="bad">{wrongR} wrong</strong>; the same model under the harness
            accepts <strong className="good">{acceptH} with 0 wrong</strong>
            {vsRaw ? ` (+${gapRaw} pp; bootstrap CI ${ciRaw})` : ""}. Versus closed frontier-raw:{" "}
            {acceptH} / 0 wrong / {harness ? money(harness.cost_per_case_usd, 4) : "$0.0020"} /{" "}
            {harness ? seconds(harness.latency_p50_ms) : "2.9s"} p50 against {acceptF} / 0 /{" "}
            {frontier ? money(frontier.cost_per_case_usd, 4) : "$0.0027"} /{" "}
            {frontier ? seconds(frontier.latency_p50_ms) : "3.8s"}. Two statistical tests agree the
            harness-vs-raw gains are real.
          </p>
          <p className="ps-links-inline">
            <Link href="/research">Multi-stat scoreboard</Link>
            <Link href="/demo">Live surgery</Link>
            <a href="/research/FORGE_RESEARCH.md" target="_blank" rel="noreferrer">
              Full write-up
            </a>
          </p>
          <p className="ps-note">
            Disclosure: built during the hackathon. Material use of a Cursor agent. Pre-existing work:
            none.
          </p>
        </header>

        <section className="ps-block">
          <h2><span>01</span> Find a task worth doing</h2>
          <div className="ps-prose">
            <p>
              Agentic apps emit floods of <code>SELECT</code>s. Platform DBAs need faster SQL without
              corrupted answers. Soft confidence scores fail on null semantics; a sealed bench with
              the same judge for every system does not.
            </p>
          </div>
          <div className="ps-table-wrap">
            <table className="ps-table">
              <thead>
                <tr>
                  <th />
                  <th>SQL rewrite (this project)</th>
                  <th>Knob / index tuning</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>The job</td>
                  <td>Faster equivalent SQL, or abstain</td>
                  <td>Change configs / indexes</td>
                </tr>
                <tr>
                  <td>Who feels it</td>
                  <td>DBAs under agent traffic</td>
                  <td>Same + capacity planning</td>
                </tr>
                <tr>
                  <td>Why GPT alone fails</td>
                  <td>Open raw: {wrongR}/{data?.splits.dev.expected_cases ?? 98} incorrect here</td>
                  <td>Different failure mode</td>
                </tr>
                <tr>
                  <td>The data</td>
                  <td>eval_v2 · 98 / 73 · 8 fixtures</td>
                  <td>
                    <code>pg_stat_statements</code>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="ps-note">
            Value sketch (assumptions written out): 10k slow SELECTs/day × 30s × $0.02/query-minute ×
            20% cut ≈ <strong>$1.2k/day</strong> infra — replace with your FinOps numbers.
          </p>
        </section>

        <section className="ps-block">
          <h2><span>02</span> Run a baseline on an open model</h2>
          <div className="ps-prose">
            <p>
              Required baseline: Fireworks <code>gpt-oss-120b</code> as <code>open-raw</code> — catalog
              + guide + EXPLAIN, <em>no</em> verify. Frontier-raw is optional context.
            </p>
          </div>
          <div className="ps-table-wrap">
            <table className="ps-table">
              <thead>
                <tr>
                  <th>System</th>
                  <th>Accept</th>
                  <th>Wrong</th>
                  <th>$/case</th>
                  <th>Opt p50</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { s: raw, name: "open-raw (baseline)", hl: false },
                  { s: frontier, name: "frontier-raw (optional)", hl: false },
                  { s: rules, name: "rules-only ($0)", hl: false },
                ].map(({ s, name }) =>
                  s ? (
                    <tr key={s.system}>
                      <td>{name}</td>
                      <td>{percent(s.accepted_rate)}</td>
                      <td className={s.incorrect_returned_count ? "bad" : ""}>
                        {s.incorrect_returned_count}
                      </td>
                      <td>{money(s.cost_per_case_usd, 4)}</td>
                      <td>{seconds(s.latency_p50_ms)}</td>
                    </tr>
                  ) : null,
                )}
              </tbody>
            </table>
          </div>
          <p className="ps-note">
            Lock first: <code>benchmarks/eval_v2/cases.jsonl</code> · one row per case in{" "}
            <code>dev_t0.jsonl</code>. Keep the baseline fair — never weaken raw to flatter the harness.
          </p>
        </section>

        <section className="ps-block">
          <h2><span>03</span> Ideate on the system</h2>
          <div className="ps-table-wrap">
            <table className="ps-table">
              <thead>
                <tr>
                  <th>Idea</th>
                  <th>Guess about the failure</th>
                  <th>Extra cost</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Rules-only</td>
                  <td>Many wins are mechanical</td>
                  <td>$0</td>
                </tr>
                <tr>
                  <td>Verify + repair harness</td>
                  <td>Useful proposals, corrupted nulls</td>
                  <td>LLM × best_of / repair</td>
                </tr>
                <tr>
                  <td>Cascade flash → Nemotron</td>
                  <td>Spend Ultra only on escalate</td>
                  <td>Intermediate</td>
                </tr>
                <tr>
                  <td>Fingerprint cache</td>
                  <td>Agent shapes repeat</td>
                  <td>$0 on hit</td>
                </tr>
                <tr>
                  <td>Fine-tune (optional)</td>
                  <td>Private dialect after verified wins</td>
                  <td>Train + deploy</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="ps-note">
            Raw mistakes were semantic — nulls, DISTINCT, EXISTS — so we built a gate, not a longer
            prompt.
          </p>
        </section>

        <section className="ps-block">
          <h2><span>04</span> Build it</h2>
          <ol className="ps-steps">
            <li>
              <strong>Context.</strong> SQL + catalog + join graph + EXPLAIN into the cascade.
            </li>
            <li>
              <strong>Propose.</strong> Rules first, then Fireworks <code>glm-5p3-flash</code> →{" "}
              <code>gpt-oss-120b</code>, escalate to <code>nemotron-3-ultra-nvfp4</code> when needed.
            </li>
            <li>
              <strong>Verify.</strong> Full <code>EVAL_SCHEMAS</code> (null/skew) — same contract as the
              judge. Equivalence ∥ timing.
            </li>
            <li>
              <strong>Time.</strong> Paired EXPLAIN ANALYZE; ≥1.25× SQL speedup or abstain.
            </li>
            <li>
              <strong>Cache.</strong> Positive fingerprints only (negatives poisoned families — removed).
            </li>
          </ol>
          <div className="ps-diagram">
            <ArchitectureDiagram />
          </div>
        </section>

        <section className="ps-block">
          <h2><span>05</span> Run everything on the sealed set</h2>
          <div className="ps-table-wrap">
            <table className="ps-table">
              <thead>
                <tr>
                  <th>System</th>
                  <th>Accept</th>
                  <th>Wrong</th>
                  <th>SQL geo↑</th>
                  <th>$/case</th>
                  <th>Opt p50</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { s: harness, name: "Ours · open-harness", hl: true },
                  { s: frontier, name: "Frontier · raw", hl: false },
                  { s: fastH, name: "fw-fast-harness", hl: false },
                  { s: raw, name: "open-raw (baseline)", hl: false },
                  { s: rules, name: "rules-only", hl: false },
                ].map(({ s, name, hl }) =>
                  s ? (
                    <tr key={s.system} className={hl ? "hl" : undefined}>
                      <td>{name}</td>
                      <td>{percent(s.accepted_rate)}</td>
                      <td className={s.incorrect_returned_count ? "bad" : ""}>
                        {s.incorrect_returned_count}
                      </td>
                      <td>{s.geomean_speedup.toFixed(2)}×</td>
                      <td>{money(s.cost_per_case_usd, 4)}</td>
                      <td>{seconds(s.latency_p50_ms)}</td>
                    </tr>
                  ) : null,
                )}
              </tbody>
            </table>
          </div>
          <ul className="ps-findings">
            <li>
              <strong>Safety cliff.</strong> Wrong returned {wrongR} → 0. McNemar on incorrects p ≈{" "}
              {pLabel(vsRaw?.mcnemar_incorrect.p_value)}.
            </li>
            <li>
              <strong>Accept vs raw.</strong> +{gapRaw} pp mean; CI {ciRaw} excludes 0. Discordant{" "}
              {vsRaw?.mcnemar_accepted.a_only ?? 18} vs {vsRaw?.mcnemar_accepted.baseline_only ?? 3}, p ≈{" "}
              {pLabel(vsRaw?.mcnemar_accepted.p_value)}.
            </li>
            <li>
              <strong>vs frontier.</strong> Point estimate{" "}
              {vsFrontier
                ? `${(vsFrontier.bootstrap_accept_gap.mean * 100).toFixed(1)} pp`
                : "+6.0 pp"}
              ; CI includes 0 (McNemar p ≈ {pLabel(vsFrontier?.mcnemar_accepted.p_value)}) — claim board
              lead + cost/latency win, not a sealed accept p-value.
            </li>
            <li>
              <strong>What lost.</strong> Rules-only safe but low (
              {rules ? percent(rules.accepted_rate) : "14.3%"}). Raw cheap and unsafe. Negative cache
              collisions — fixed.
            </li>
          </ul>
        </section>

        <section className="ps-block">
          <h2><span>06</span> Prove the gain is real</h2>
          <div className="ps-prose">
            <p>
              Luck moves a 98-case score. Same playbook as the Forge sample: McNemar on disagreements +
              template-cluster bootstrap (5,000 resamples).
            </p>
          </div>
          <div className="ps-table-wrap">
            <table className="ps-table">
              <thead>
                <tr>
                  <th>Comparison</th>
                  <th>Mean gap</th>
                  <th>95% CI</th>
                  <th>McNemar p</th>
                </tr>
              </thead>
              <tbody>
                {vsRaw ? (
                  <tr className="hl">
                    <td>open-harness − open-raw</td>
                    <td>+{(vsRaw.bootstrap_accept_gap.mean * 100).toFixed(1)} pp</td>
                    <td>
                      [{(vsRaw.bootstrap_accept_gap.ci95[0] * 100).toFixed(1)},{" "}
                      {(vsRaw.bootstrap_accept_gap.ci95[1] * 100).toFixed(1)}]
                    </td>
                    <td>{pLabel(vsRaw.mcnemar_accepted.p_value)}</td>
                  </tr>
                ) : null}
                {vsRules ? (
                  <tr>
                    <td>open-harness − rules-only</td>
                    <td>+{(vsRules.bootstrap_accept_gap.mean * 100).toFixed(1)} pp</td>
                    <td>
                      [{(vsRules.bootstrap_accept_gap.ci95[0] * 100).toFixed(1)},{" "}
                      {(vsRules.bootstrap_accept_gap.ci95[1] * 100).toFixed(1)}]
                    </td>
                    <td>{pLabel(vsRules.mcnemar_accepted.p_value)}</td>
                  </tr>
                ) : null}
                {vsFrontier ? (
                  <tr>
                    <td>open-harness − frontier-raw</td>
                    <td>+{(vsFrontier.bootstrap_accept_gap.mean * 100).toFixed(1)} pp</td>
                    <td>
                      [{(vsFrontier.bootstrap_accept_gap.ci95[0] * 100).toFixed(1)},{" "}
                      {(vsFrontier.bootstrap_accept_gap.ci95[1] * 100).toFixed(1)}]
                    </td>
                    <td>{pLabel(vsFrontier.mcnemar_accepted.p_value)}</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <p className="ps-note">
            Call a gain real only when both tests agree. Harness vs raw: both agree. vs frontier accept:
            CI includes 0 — honest.
          </p>
        </section>

        <section className="ps-block">
          <h2><span>07</span> Worked example</h2>
          {featured ? (
            <>
              <div className="ps-rewrite">
                <div className="ps-rewrite-col">
                  <span>ORIGINAL · {featured.case.family} · {featured.case.id}</span>
                  <pre>{featured.case.sql}</pre>
                </div>
                <div className="ps-rewrite-col">
                  <span>REWRITE · {featured.record.speedup?.toFixed(2)}× SQL</span>
                  <pre>{featured.record.result_sql}</pre>
                </div>
              </div>
              <div className="ps-rewrite-meta">
                <div>
                  <span>Original</span>
                  <strong>
                    {(featured.record.verdict?.original_ms ?? featured.case.original_ms).toFixed(2)} ms
                  </strong>
                </div>
                <div>
                  <span>Rewrite</span>
                  <strong>{featured.record.verdict?.candidate_ms?.toFixed(3) ?? "—"} ms</strong>
                </div>
                <div>
                  <span>API $</span>
                  <strong>{money(featured.record.cost_usd, 4)}</strong>
                </div>
                <div>
                  <span>Optimizer</span>
                  <strong>{seconds(featured.record.latency_ms)}</strong>
                </div>
              </div>
            </>
          ) : (
            <p className="ps-note">Snapshot missing accepted traces.</p>
          )}
        </section>

        <section className="ps-block ps-block-last">
          <h2><span>08</span> Reproduce</h2>
          <pre className="ps-code">{`.venv/bin/python scripts/compute_paired_stats.py
.venv/bin/python scripts/export_research.py
.venv/bin/python -m surgeon.eval run open-harness --split dev`}</pre>
          <p className="ps-note">
            Write-up: <code>docs/FORGE_RESEARCH.md</code> · traces:{" "}
            <code>benchmarks/eval_v2/runs/&lt;system&gt;/dev_t0.jsonl</code>
          </p>
        </section>

        <footer className="ps-footer">
          <span>
            sealed eval_v2 · {data?.splits.dev.expected_cases ?? 98} +{" "}
            {data?.splits.heldout.expected_cases ?? 73} · trial 0
          </span>
          <span>{data ? new Date(data.generated_at).toISOString().slice(0, 16) + "Z" : "no snapshot"}</span>
        </footer>
      </main>
    </ProductShell>
  );
}
