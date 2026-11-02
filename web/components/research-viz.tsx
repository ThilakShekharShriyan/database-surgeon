"use client";

import type { ResearchSystem } from "@/lib/research-types";
import { label, percent } from "./research-charts";

const INK = "#eeeff2";
const MUTED = "#a8a9b1";
const GRID = "#2c2d33";
const ACCENT = "#7eb4ec";
const BAD = "#f08494";
const GOOD = "#78c3a5";
const SERIES = ["#7eb4ec", "#e1e3e9", "#78c3a5", "#d9b870", "#c4a8e8", "#f08494"];

type Bar = { key: string; label: string; value: number; tone?: "good" | "bad" | "neutral" };

/** Horizontal or vertical bar chart for rates / counts. */
export function StatBars({
  bars,
  max,
  unit = "",
  height,
  mode = "h",
}: {
  bars: Bar[];
  max?: number;
  unit?: string;
  height?: number;
  mode?: "h" | "v";
}) {
  const m = max ?? Math.max(0.01, ...bars.map((b) => b.value));
  if (mode === "v") {
    const W = 640, H = height ?? 240, L = 40, R = 16, T = 16, B = 56;
    const PX = W - L - R, PY = H - T - B;
    const gap = 8;
    const bw = (PX - gap * (bars.length - 1)) / Math.max(1, bars.length);
    return (
      <svg viewBox={`0 0 ${W} ${H}`} role="img" className="r-viz">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={T + PY * (1 - t)} y2={T + PY * (1 - t)} stroke={GRID} />
            <text x={L - 8} y={T + PY * (1 - t) + 4} textAnchor="end" fill={MUTED} fontSize={11} fontFamily="IBM Plex Mono, monospace">
              {unit === "%" ? `${Math.round(m * t * 100)}` : (m * t).toFixed(m >= 10 ? 0 : 1)}
            </text>
          </g>
        ))}
        {bars.map((b, i) => {
          const h = (b.value / m) * PY;
          const x = L + i * (bw + gap);
          const fill = b.tone === "bad" ? BAD : b.tone === "good" ? GOOD : SERIES[i % SERIES.length];
          return (
            <g key={b.key}>
              <rect x={x} y={T + PY - h} width={bw} height={Math.max(1, h)} fill={fill} rx={2} />
              <text x={x + bw / 2} y={H - 28} textAnchor="middle" fill={MUTED} fontSize={10}>
                {b.label.length > 14 ? b.label.slice(0, 12) + "…" : b.label}
              </text>
              <text x={x + bw / 2} y={T + PY - h - 6} textAnchor="middle" fill={INK} fontSize={11} fontFamily="IBM Plex Mono, monospace">
                {unit === "%" ? `${(b.value * 100).toFixed(0)}%` : b.value.toFixed(b.value >= 10 ? 1 : 2)}
                {unit && unit !== "%" ? unit : ""}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }
  const rowH = 34;
  const H = bars.length * rowH + 8;
  const left = 150, width = 420;
  return (
    <svg viewBox={`0 0 640 ${H}`} role="img" className="r-viz">
      {bars.map((b, i) => {
        const y = 10 + i * rowH;
        const fill = b.tone === "bad" ? BAD : b.tone === "good" ? GOOD : ACCENT;
        return (
          <g key={b.key}>
            <text x={left - 12} y={y + 5} textAnchor="end" fill={INK} fontSize={12}>{b.label}</text>
            <rect x={left} y={y - 7} width={width} height={14} fill="#282a30" rx={2} />
            <rect x={left} y={y - 7} width={Math.max(2, (b.value / m) * width)} height={14} fill={fill} rx={2} />
            <text x={left + width + 10} y={y + 5} fill={MUTED} fontSize={11} fontFamily="IBM Plex Mono, monospace">
              {unit === "%" ? percent(b.value) : `${b.value.toFixed(2)}${unit}`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** Grouped bars: e.g. Accept vs Wrong across systems. */
export function GroupedBars({
  categories,
  series,
}: {
  categories: { key: string; label: string }[];
  series: { key: string; label: string; color: string; values: number[] }[];
}) {
  const W = 640, H = 260, L = 44, R = 20, T = 24, B = 52;
  const PX = W - L - R, PY = H - T - B;
  const max = Math.max(0.01, ...series.flatMap((s) => s.values));
  const groupW = PX / categories.length;
  const barW = (groupW - 16) / series.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" className="r-viz" aria-label="Grouped comparison">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <line key={t} x1={L} x2={W - R} y1={T + PY * (1 - t)} y2={T + PY * (1 - t)} stroke={GRID} />
      ))}
      {categories.map((c, i) => {
        const gx = L + i * groupW + 8;
        return (
          <g key={c.key}>
            {series.map((s, j) => {
              const v = s.values[i] ?? 0;
              const h = (v / max) * PY;
              return (
                <rect
                  key={s.key}
                  x={gx + j * barW}
                  y={T + PY - h}
                  width={Math.max(2, barW - 3)}
                  height={Math.max(1, h)}
                  fill={s.color}
                  rx={2}
                >
                  <title>{`${c.label} · ${s.label}: ${v.toFixed(3)}`}</title>
                </rect>
              );
            })}
            <text x={gx + (series.length * barW) / 2} y={H - 28} textAnchor="middle" fill={MUTED} fontSize={10}>
              {c.label.length > 12 ? c.label.slice(0, 11) + "…" : c.label}
            </text>
          </g>
        );
      })}
      <g transform={`translate(${L}, 8)`}>
        {series.map((s, i) => (
          <g key={s.key} transform={`translate(${i * 120}, 0)`}>
            <rect width={10} height={10} fill={s.color} rx={1} />
            <text x={14} y={9} fill={MUTED} fontSize={11}>{s.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

/** Simple line chart — e.g. family accept rates or env comparison. */
export function LineSeries({
  points,
  yMax = 1,
  yLabel = "",
}: {
  points: { x: string; series: { key: string; y: number }[] }[];
  yMax?: number;
  yLabel?: string;
}) {
  const W = 640, H = 240, L = 48, R = 20, T = 20, B = 48;
  const PX = W - L - R, PY = H - T - B;
  const keys = points[0]?.series.map((s) => s.key) || [];
  const xAt = (i: number) => L + (points.length <= 1 ? PX / 2 : (i / (points.length - 1)) * PX);
  const yAt = (v: number) => T + (1 - v / yMax) * PY;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" className="r-viz">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={yAt(yMax * t)} y2={yAt(yMax * t)} stroke={GRID} />
          <text x={L - 8} y={yAt(yMax * t) + 4} textAnchor="end" fill={MUTED} fontSize={11} fontFamily="IBM Plex Mono, monospace">
            {yLabel === "%" ? `${Math.round(yMax * t * 100)}` : (yMax * t).toFixed(1)}
          </text>
        </g>
      ))}
      {keys.map((key, ki) => {
        const d = points
          .map((p, i) => {
            const y = p.series.find((s) => s.key === key)?.y ?? 0;
            return `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(y)}`;
          })
          .join(" ");
        return <path key={key} d={d} fill="none" stroke={SERIES[ki % SERIES.length]} strokeWidth={2} />;
      })}
      {points.map((p, i) => (
        <text key={p.x} x={xAt(i)} y={H - 18} textAnchor="middle" fill={MUTED} fontSize={10}>
          {p.x.length > 10 ? p.x.slice(0, 9) + "…" : p.x}
        </text>
      ))}
      <g transform={`translate(${L}, 6)`}>
        {keys.map((k, i) => (
          <g key={k} transform={`translate(${i * 110}, 0)`}>
            <rect width={10} height={3} y={4} fill={SERIES[i % SERIES.length]} />
            <text x={14} y={9} fill={MUTED} fontSize={11}>{label(k)}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

/** Donut / pie for outcome mix. */
export function OutcomePie({
  slices,
}: {
  slices: { key: string; label: string; value: number; color: string }[];
}) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  const cx = 120, cy = 120, r = 78, ir = 44;
  let angle = -Math.PI / 2;
  const arcs = slices.filter((s) => s.value > 0).map((s) => {
    const a = (s.value / total) * Math.PI * 2;
    const start = angle;
    const end = angle + a;
    angle = end;
    const large = a > Math.PI ? 1 : 0;
    const x0 = cx + r * Math.cos(start), y0 = cy + r * Math.sin(start);
    const x1 = cx + r * Math.cos(end), y1 = cy + r * Math.sin(end);
    const ix0 = cx + ir * Math.cos(end), iy0 = cy + ir * Math.sin(end);
    const ix1 = cx + ir * Math.cos(start), iy1 = cy + ir * Math.sin(start);
    const d = `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} L ${ix0} ${iy0} A ${ir} ${ir} 0 ${large} 0 ${ix1} ${iy1} Z`;
    return { ...s, d };
  });
  return (
    <svg viewBox="0 0 420 240" role="img" className="r-viz">
      {arcs.map((a) => (
        <path key={a.key} d={a.d} fill={a.color}>
          <title>{`${a.label}: ${a.value} (${((a.value / total) * 100).toFixed(0)}%)`}</title>
        </path>
      ))}
      <text x={cx} y={cy - 4} textAnchor="middle" fill={INK} fontSize={18} fontFamily="IBM Plex Mono, monospace">{total}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill={MUTED} fontSize={11}>cases</text>
      {slices.map((s, i) => (
        <g key={s.key} transform={`translate(250, ${28 + i * 28})`}>
          <rect width={10} height={10} fill={s.color} rx={1} />
          <text x={18} y={9} fill={MUTED} fontSize={12}>{s.label}</text>
          <text x={150} y={9} fill={INK} fontSize={12} fontFamily="IBM Plex Mono, monospace" textAnchor="end">
            {s.value} · {((s.value / total) * 100).toFixed(0)}%
          </text>
        </g>
      ))}
    </svg>
  );
}

/** Environment comparison: same systems on two splits. */
export function EnvCompareBars({
  systems,
  envA,
  envB,
  metric,
}: {
  systems: string[];
  envA: ResearchSystem[];
  envB: ResearchSystem[];
  metric: "accept" | "wrong" | "cost" | "speedup";
}) {
  const pick = (rows: ResearchSystem[], name: string) => rows.find((r) => r.system === name);
  const val = (r?: ResearchSystem) => {
    if (!r) return 0;
    if (metric === "accept") return r.accepted_rate;
    if (metric === "wrong") return r.incorrect_returned_count;
    if (metric === "cost") return r.cost_per_case_usd ?? 0;
    return r.geomean_speedup;
  };
  return (
    <GroupedBars
      categories={systems.map((s) => ({ key: s, label: label(s) }))}
      series={[
        { key: "dev", label: "Development", color: ACCENT, values: systems.map((s) => val(pick(envA, s))) },
        { key: "heldout", label: "Held-out", color: "#959aa5", values: systems.map((s) => val(pick(envB, s))) },
      ]}
    />
  );
}

export function systemOutcomeSlices(system: ResearchSystem) {
  const counts: Record<string, number> = {};
  for (const r of system.records) {
    const k = ["accepted", "no_change", "not_faster"].includes(r.outcome) ? r.outcome : "failure";
    counts[k] = (counts[k] || 0) + 1;
  }
  return [
    { key: "accepted", label: "Accepted", value: counts.accepted || 0, color: ACCENT },
    { key: "no_change", label: "Unchanged", value: counts.no_change || 0, color: "#71747e" },
    { key: "not_faster", label: "Not faster", value: counts.not_faster || 0, color: "#aeb1bb" },
    { key: "failure", label: "Wrong / fail", value: counts.failure || 0, color: BAD },
  ];
}
