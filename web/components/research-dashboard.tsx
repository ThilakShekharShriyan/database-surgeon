"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Database, FlaskConical, Maximize2, RefreshCw } from "lucide-react";
import type { ResearchSnapshot, ResearchSystem } from "@/lib/research-types";
import { label, money, percent, seconds } from "./research-charts";
import { GroupedBars, OutcomePie, StatBars, systemOutcomeSlices } from "./research-viz";
import "../app/research.css";

const OURS = "open-harness";
const FRONTIER = "frontier-raw";
const RAW = "open-raw";
const OURS_COLOR = "#7eb4ec";
const FRONTIER_COLOR = "#c8ccd4";
const RAW_COLOR = "#f08494";

function pick(systems: ResearchSystem[], name: string) {
  return systems.find((r) => r.system === name);
}

function pvalue(v: number | null | undefined) {
  if (v == null) return "—";
  return v < 0.0001 ? v.toExponential(2) : v.toFixed(4);
}

function deltaPp(a: number, b: number) {
  const d = (a - b) * 100;
  return `${d >= 0 ? "+" : ""}${d.toFixed(1)} pp`;
}

function deltaRatio(a: number, b: number, digits = 2) {
  if (!b) return "—";
  const r = a / b;
  return `${r >= 1 ? "" : ""}${r.toFixed(digits)}×`;
}

export function ResearchDashboard({
  embedded = false,
  initialData = null,
}: {
  embedded?: boolean;
  initialData?: ResearchSnapshot | null;
}) {
  const [data, setData] = useState<ResearchSnapshot | null>(initialData);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [split, setSplit] = useState<"dev" | "heldout">("dev");
  const [presenting, setPresenting] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await fetch("/api/research", { cache: "no-store" });
      const value = await response.json();
      if (!response.ok) throw Error(value.error || "Could not load research snapshot.");
      setData(value);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load research snapshot.");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const current = data?.splits[split];
  const systems = current?.systems || [];
  const ours = pick(systems, OURS);
  const frontier = pick(systems, FRONTIER);
  const raw = pick(systems, RAW);
  const comparison = current?.comparisons[FRONTIER]?.[OURS];
  const accept = comparison?.mcnemar.accepted;

  const vsFrontier = useMemo(
    () =>
      data?.paired_stats?.comparisons?.find(
        (c) => c.system === OURS && c.baseline === FRONTIER && c.split === "dev",
      ) ||
      data?.paired_stats?.comparisons?.find((c) => c.system === OURS && c.baseline === FRONTIER),
    [data],
  );
  const vsRaw = useMemo(
    () =>
      data?.paired_stats?.comparisons?.find(
        (c) => c.system === OURS && c.baseline === RAW && c.split === "dev",
      ) || data?.paired_stats?.comparisons?.find((c) => c.system === OURS && c.baseline === RAW),
    [data],
  );

  const acceptBars = useMemo(() => {
    if (!ours || !frontier) return null;
    const bars = [
      { key: "ours", label: "Ours", value: ours.accepted_rate, tone: "good" as const },
      { key: "frontier", label: "Frontier", value: frontier.accepted_rate, tone: "neutral" as const },
    ];
    if (raw) bars.push({ key: "raw", label: "Open-raw", value: raw.accepted_rate, tone: "bad" as const });
    return <StatBars mode="v" unit="%" bars={bars} height={220} />;
  }, [ours, frontier, raw]);

  const wrongBars = useMemo(() => {
    if (!ours || !frontier) return null;
    const bars = [
      { key: "ours", label: "Ours", value: ours.incorrect_returned_count, tone: "good" as const },
      { key: "frontier", label: "Frontier", value: frontier.incorrect_returned_count, tone: "neutral" as const },
    ];
    if (raw) bars.push({ key: "raw", label: "Open-raw", value: raw.incorrect_returned_count, tone: "bad" as const });
    return <StatBars mode="v" bars={bars} height={220} max={Math.max(12, ...bars.map((b) => b.value))} />;
  }, [ours, frontier, raw]);

  const latencyBars = useMemo(() => {
    if (!ours || !frontier) return null;
    return (
      <GroupedBars
        categories={[
          { key: "opt", label: "Opt p50 (s)" },
          { key: "p95", label: "Opt p95 (s)" },
        ]}
        series={[
          {
            key: "ours",
            label: "Ours",
            color: OURS_COLOR,
            values: [ours.latency_p50_ms / 1000, ours.latency_p95_ms / 1000],
          },
          {
            key: "frontier",
            label: "Frontier",
            color: FRONTIER_COLOR,
            values: [frontier.latency_p50_ms / 1000, frontier.latency_p95_ms / 1000],
          },
        ]}
      />
    );
  }, [ours, frontier]);

  const costSpeedBars = useMemo(() => {
    if (!ours || !frontier) return null;
    return (
      <GroupedBars
        categories={[
          { key: "cost", label: "$/case ×1000" },
          { key: "sql", label: "SQL geo×" },
        ]}
        series={[
          {
            key: "ours",
            label: "Ours",
            color: OURS_COLOR,
            values: [(ours.cost_per_case_usd ?? 0) * 1000, ours.geomean_speedup],
          },
          {
            key: "frontier",
            label: "Frontier",
            color: FRONTIER_COLOR,
            values: [(frontier.cost_per_case_usd ?? 0) * 1000, frontier.geomean_speedup],
          },
        ]}
      />
    );
  }, [ours, frontier]);

  const frontierVerdict = useMemo(() => {
    if (!vsFrontier || !ours || !frontier) return null;
    const gap = vsFrontier.bootstrap_accept_gap.mean;
    const [lo, hi] = vsFrontier.bootstrap_accept_gap.ci95;
    const ciIncludes0 = lo < 0 && hi > 0;
    if (gap > 0.03 && !ciIncludes0) {
      return "Accept lift over frontier is significant on this sealed split.";
    }
    if (gap > 0 && ciIncludes0) {
      return "Point estimate beats frontier on accept; CI still includes 0 — claim a lead on the board, not a sealed statistical win.";
    }
    if (Math.abs(gap) < 0.03 && ciIncludes0) {
      return "Accept parity with frontier on an open stack; safety matches (0 wrong).";
    }
    return "See CI and McNemar before claiming a win.";
  }, [vsFrontier, ours, frontier]);

  return (
    <div className={`research r-duel ${presenting ? "r-presenting" : ""} ${embedded ? "r-embedded" : ""}`}>
      {!embedded && (
        <aside className="r-rail" aria-label="Research navigation">
          <a href="/" className="r-mark" aria-label="Home">
            <Database size={23} />
          </a>
          <nav>
            <a className="active" href="/research" title="Scoreboard" aria-label="Scoreboard">
              <Database size={19} />
              <span>Board</span>
            </a>
          </nav>
          <a className="r-rail-demo" href="/demo" title="Live surgery" aria-label="Live surgery">
            <FlaskConical size={19} />
            <span>Demo</span>
          </a>
        </aside>
      )}
      <div className="r-workspace">
        <header className="r-topbar">
          <a href="/" className="r-brand">
            Database Surgeon <span>/</span>
            <b>Research scoreboard</b>
          </a>
          <div>
            <a href="/">Home</a>
            <a href="/demo">
              Live surgery <ArrowUpRight size={13} />
            </a>
            <button onClick={() => setPresenting((v) => !v)} aria-pressed={presenting}>
              <Maximize2 size={15} />
              <span>{presenting ? "Exit" : "Present"}</span>
            </button>
          </div>
        </header>

        <main className="r-main">
          <div className="r-title">
            <div>
              <div className="r-breadcrumb">Research · sealed eval_v2</div>
              <h1>Agents ask “make it faster.” Measure what ships.</h1>
              <p>
                Blind open-raw “optimizes” SQL with no gate — and returns wrong answers. Open-harness
                verify-or-abstain vs frontier-raw and open-raw on the same{" "}
                {current?.expected_cases ?? 98} locked cases: accept · wrong · latency · cost · tokens.
              </p>
            </div>
            <div className="r-title-actions">
              <button className="r-button" onClick={() => void refresh()} disabled={refreshing} aria-label="Refresh">
                <RefreshCw size={14} className={refreshing ? "r-spinning" : ""} />
                {refreshing ? "Loading" : "Refresh"}
              </button>
            </div>
          </div>

          {error && (
            <div className="r-error" role="alert">
              {error}
              <button onClick={() => void refresh()}>Try again</button>
            </div>
          )}
          {!data && !error && <div className="r-loading">Loading evidence…</div>}

          {data && (
            <>
              <div className="r-controls">
                <div className="r-split">
                  <button className={split === "dev" ? "active" : ""} onClick={() => setSplit("dev")}>
                    Development <span>{data.splits.dev.expected_cases}</span>
                  </button>
                  <button className={split === "heldout" ? "active" : ""} onClick={() => setSplit("heldout")}>
                    Held-out <span>{data.splits.heldout.expected_cases}</span>
                  </button>
                </div>
                <div className="r-duel-legend">
                  <span>
                    <i style={{ background: OURS_COLOR }} /> Ours
                  </span>
                  <span>
                    <i style={{ background: FRONTIER_COLOR }} /> Frontier
                  </span>
                  <span>
                    <i style={{ background: RAW_COLOR }} /> Open-raw
                  </span>
                </div>
              </div>

              {!ours || !frontier ? (
                <div className="r-empty">
                  Missing {!ours ? "open-harness" : "frontier-raw"} on this split.
                </div>
              ) : (
                <>
                  <div className="r-kpis r-multi-kpis" aria-label="Headline metrics">
                    <div>
                      <span>Accept</span>
                      <strong>
                        {percent(ours.accepted_rate)}
                        <i>/</i>
                        <em>{percent(frontier.accepted_rate)}</em>
                      </strong>
                      <small>
                        Ours / frontier · {deltaPp(ours.accepted_rate, frontier.accepted_rate)}
                        {raw ? ` · raw ${percent(raw.accepted_rate)}` : ""}
                      </small>
                    </div>
                    <div>
                      <span>Wrong returned</span>
                      <strong>
                        {ours.incorrect_returned_count}
                        <i>/</i>
                        <em>{frontier.incorrect_returned_count}</em>
                      </strong>
                      <small>
                        Ours / frontier
                        {raw ? (
                          <>
                            {" "}
                            · raw <span className="r-negative">{raw.incorrect_returned_count}</span>
                          </>
                        ) : null}
                      </small>
                    </div>
                    <div>
                      <span>Optimizer p50</span>
                      <strong>
                        {seconds(ours.latency_p50_ms)}
                        <i>/</i>
                        <em>{seconds(frontier.latency_p50_ms)}</em>
                      </strong>
                      <small>
                        Ours / frontier ·{" "}
                        {deltaRatio(ours.latency_p50_ms, frontier.latency_p50_ms)} of frontier
                      </small>
                    </div>
                    <div>
                      <span>$ / case</span>
                      <strong>
                        {money(ours.cost_per_case_usd, 4)}
                        <i>/</i>
                        <em>{money(frontier.cost_per_case_usd, 4)}</em>
                      </strong>
                      <small>
                        Ours / frontier
                        {ours.cost_per_case_usd != null && frontier.cost_per_case_usd
                          ? ` · ${deltaRatio(ours.cost_per_case_usd, frontier.cost_per_case_usd)}`
                          : ""}
                      </small>
                    </div>
                  </div>

                  <div className="r-duel-verdict">
                    {vsRaw || vsFrontier ? (
                      <p>
                        {vsRaw ? (
                          <>
                            <strong>vs open-raw</strong> accept{" "}
                            {(vsRaw.bootstrap_accept_gap.mean * 100).toFixed(1)} pp · CI [
                            {(vsRaw.bootstrap_accept_gap.ci95[0] * 100).toFixed(1)},{" "}
                            {(vsRaw.bootstrap_accept_gap.ci95[1] * 100).toFixed(1)}] · wrongs{" "}
                            {vsRaw.incorrect_count_a}→{vsRaw.incorrect_count_b === 0 ? 0 : vsRaw.incorrect_count_b}{" "}
                            (McNemar incorrect p = {pvalue(vsRaw.mcnemar_incorrect.p_value)})
                            {" · "}
                          </>
                        ) : null}
                        {vsFrontier ? (
                          <>
                            <strong>vs frontier</strong> accept gap{" "}
                            {(vsFrontier.bootstrap_accept_gap.mean * 100).toFixed(1)} pp · CI [
                            {(vsFrontier.bootstrap_accept_gap.ci95[0] * 100).toFixed(1)},{" "}
                            {(vsFrontier.bootstrap_accept_gap.ci95[1] * 100).toFixed(1)}] · McNemar p ={" "}
                            {pvalue(vsFrontier.mcnemar_accepted.p_value)}
                            {" — "}
                            {frontierVerdict}
                          </>
                        ) : null}
                      </p>
                    ) : (
                      <p>Paired stats unavailable — showing per-system aggregates.</p>
                    )}
                  </div>

                  <div className="r-duel-cards">
                    <article className="r-duel-card ours">
                      <header>Ours · open-harness</header>
                      <strong>{percent(ours.accepted_rate)}</strong>
                      <span>accept · 0-wrong SLA</span>
                      <dl>
                        <div>
                          <dt>Wrong</dt>
                          <dd className={ours.incorrect_returned_count ? "r-negative" : ""}>
                            {ours.incorrect_returned_count}
                          </dd>
                        </div>
                        <div>
                          <dt>SQL geo↑</dt>
                          <dd>{ours.geomean_speedup.toFixed(2)}×</dd>
                        </div>
                        <div>
                          <dt>$/case</dt>
                          <dd>{money(ours.cost_per_case_usd, 4)}</dd>
                        </div>
                        <div>
                          <dt>Opt p50</dt>
                          <dd>{seconds(ours.latency_p50_ms)}</dd>
                        </div>
                        <div>
                          <dt>Opt p95</dt>
                          <dd>{seconds(ours.latency_p95_ms)}</dd>
                        </div>
                        <div>
                          <dt>Calls/case</dt>
                          <dd>{ours.calls_per_case.toFixed(1)}</dd>
                        </div>
                      </dl>
                      <small>
                        {ours.cases}/{current?.expected_cases} cases
                        {!ours.complete ? " · partial" : ""}
                      </small>
                    </article>
                    <article className="r-duel-card frontier">
                      <header>Frontier · raw</header>
                      <strong>{percent(frontier.accepted_rate)}</strong>
                      <span>accept · closed baseline</span>
                      <dl>
                        <div>
                          <dt>Wrong</dt>
                          <dd className={frontier.incorrect_returned_count ? "r-negative" : ""}>
                            {frontier.incorrect_returned_count}
                          </dd>
                        </div>
                        <div>
                          <dt>SQL geo↑</dt>
                          <dd>{frontier.geomean_speedup.toFixed(2)}×</dd>
                        </div>
                        <div>
                          <dt>$/case</dt>
                          <dd>{money(frontier.cost_per_case_usd, 4)}</dd>
                        </div>
                        <div>
                          <dt>Opt p50</dt>
                          <dd>{seconds(frontier.latency_p50_ms)}</dd>
                        </div>
                        <div>
                          <dt>Opt p95</dt>
                          <dd>{seconds(frontier.latency_p95_ms)}</dd>
                        </div>
                        <div>
                          <dt>Calls/case</dt>
                          <dd>{frontier.calls_per_case.toFixed(1)}</dd>
                        </div>
                      </dl>
                      <small>
                        {frontier.cases}/{current?.expected_cases} cases
                        {!frontier.complete ? " · partial" : ""}
                      </small>
                    </article>
                    {raw ? (
                      <article className="r-duel-card raw">
                        <header>Open-raw · no gate</header>
                        <strong className="r-negative">{percent(raw.accepted_rate)}</strong>
                        <span>accept · unsafe baseline</span>
                        <dl>
                          <div>
                            <dt>Wrong</dt>
                            <dd className="r-negative">{raw.incorrect_returned_count}</dd>
                          </div>
                          <div>
                            <dt>SQL geo↑</dt>
                            <dd>{raw.geomean_speedup.toFixed(2)}×</dd>
                          </div>
                          <div>
                            <dt>$/case</dt>
                            <dd>{money(raw.cost_per_case_usd, 4)}</dd>
                          </div>
                          <div>
                            <dt>Opt p50</dt>
                            <dd>{seconds(raw.latency_p50_ms)}</dd>
                          </div>
                          <div>
                            <dt>Opt p95</dt>
                            <dd>{seconds(raw.latency_p95_ms)}</dd>
                          </div>
                          <div>
                            <dt>Calls/case</dt>
                            <dd>{raw.calls_per_case.toFixed(1)}</dd>
                          </div>
                        </dl>
                        <small>
                          {raw.cases}/{current?.expected_cases} cases · why the harness exists
                        </small>
                      </article>
                    ) : null}
                  </div>

                  <div className="r-chart-grid">
                    <section className="r-panel">
                      <header>
                        <div>
                          <h2>Accept rate</h2>
                          <p>Share of cases with a verified ≥20% faster rewrite.</p>
                        </div>
                      </header>
                      <div className="r-svg-scroll">{acceptBars}</div>
                    </section>
                    <section className="r-panel">
                      <header>
                        <div>
                          <h2>Wrong returned</h2>
                          <p>Incorrect SQL shipped — the safety cliff.</p>
                        </div>
                      </header>
                      <div className="r-svg-scroll">{wrongBars}</div>
                    </section>
                  </div>

                  <div className="r-chart-grid">
                    <section className="r-panel">
                      <header>
                        <div>
                          <h2>Optimizer latency</h2>
                          <p>Wall time to decide accept/abstain (p50 / p95).</p>
                        </div>
                      </header>
                      <div className="r-svg-scroll">{latencyBars}</div>
                    </section>
                    <section className="r-panel">
                      <header>
                        <div>
                          <h2>Cost & SQL speedup</h2>
                          <p>API $/case (×1000) and delivered SQL geomean speedup.</p>
                        </div>
                      </header>
                      <div className="r-svg-scroll">{costSpeedBars}</div>
                    </section>
                  </div>

                  <div className="r-chart-grid">
                    <section className="r-panel">
                      <header>
                        <div>
                          <h2>Outcome mix</h2>
                          <p>Trial 0 case outcomes — ours vs frontier.</p>
                        </div>
                      </header>
                      <div className="r-duel-pies">
                        <div>
                          <h3>Ours</h3>
                          <OutcomePie slices={systemOutcomeSlices(ours)} />
                        </div>
                        <div>
                          <h3>Frontier</h3>
                          <OutcomePie slices={systemOutcomeSlices(frontier)} />
                        </div>
                      </div>
                    </section>
                    {accept?.table ? (
                      <section className="r-panel">
                        <header>
                          <div>
                            <h2>Paired accept table</h2>
                            <p>Same cases · discordant cells enter McNemar.</p>
                          </div>
                        </header>
                        <div className="r-contingency">
                          <div />
                          <div>Frontier not</div>
                          <div>Frontier yes</div>
                          <div>Ours not</div>
                          <strong>{accept.table[0][0]}</strong>
                          <strong className="r-discordant">
                            {accept.table[0][1]}
                            <small>Frontier alone</small>
                          </strong>
                          <div>Ours yes</div>
                          <strong className="r-discordant">
                            {accept.table[1][0]}
                            <small>Ours alone</small>
                          </strong>
                          <strong>{accept.table[1][1]}</strong>
                        </div>
                      </section>
                    ) : (
                      <section className="r-panel">
                        <header>
                          <div>
                            <h2>Open-raw outcomes</h2>
                            <p>Blind baseline without verify-or-abstain.</p>
                          </div>
                        </header>
                        {raw ? <OutcomePie slices={systemOutcomeSlices(raw)} /> : <p className="r-empty">No open-raw run.</p>}
                      </section>
                    )}
                  </div>
                </>
              )}

              <footer className="r-footer">
                <span>
                  <Database size={13} /> {label(OURS)} · {split} · {data.generated_at.slice(0, 16)}Z
                </span>
                <span>
                  <a href="/demo">
                    Live surgery <ArrowUpRight size={12} />
                  </a>
                </span>
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
