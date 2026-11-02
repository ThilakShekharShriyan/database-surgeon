"use client";

import { MermaidDiagram } from "./mermaid-diagram";

/** Three-set positioning: Safe / Fast / Cheap — where each system sits. */
export function SystemVennDiagram({
  harnessAccept = "57.1%",
  harnessWrong = "0",
  rawAccept = "46.9%",
  rawWrong = "11",
  frontierAccept = "56.1%",
  frontierWrong = "0",
}: {
  harnessAccept?: string;
  harnessWrong?: string;
  rawAccept?: string;
  rawWrong?: string;
  frontierAccept?: string;
  frontierWrong?: string;
}) {
  const chart = `
flowchart TB
  subgraph Safe["Safe: 0 incorrect"]
    H["open-harness ${harnessAccept} / ${harnessWrong} wrong"]
    F["frontier-raw ${frontierAccept} / ${frontierWrong} wrong"]
  end
  subgraph Fast["Fast SQL: geq 1.25x"]
    H2["open-harness delivered ~3.9x"]
    R["open-raw ${rawAccept} / ${rawWrong} wrong"]
    F2["frontier-raw delivered ~3.9x"]
  end
  subgraph Cheap["Cheap API $/case"]
    R2["open-raw ~$0.0004"]
    Rules["rules-only $0"]
  end
  H --> H2
  F --> F2
  R --> R2
  H2 --> Target["Target: Safe and Fast on open stack"]
  F2 --> Target
`;
  return <MermaidDiagram chart={chart} className="r-mermaid-venn" />;
}

/** Actor / user journey for who feels the rewrite. */
export function UserJourneyDiagram() {
  const chart = `
sequenceDiagram
  actor Agent as Coding agent
  participant App as App backend
  participant PG as PostgreSQL
  participant DS as Database Surgeon
  Agent->>App: slow SELECT
  App->>PG: run original
  PG-->>App: correct but expensive
  App->>DS: optimize
  DS->>DS: cascade then verify
  alt accept
    DS-->>App: rewritten SQL
    App->>PG: run rewrite
    PG-->>App: same rows faster
  else abstain
    DS-->>App: keep original
  end
`;
  return <MermaidDiagram chart={chart} />;
}

/** System architecture: propose → verify → measure → return. */
export function ArchitectureDiagram() {
  const chart = `
flowchart LR
  SQL[Agent SQL] --> Ctx[Context catalog EXPLAIN]
  Ctx --> Cascade[Cascade rules flash oss Nemotron]
  Cascade --> Cand[Candidate SQL]
  Cand --> Verify[Verify fixtures]
  Verify -->|fail| Abstain[Abstain original]
  Verify -->|pass| Time[Time EXPLAIN ANALYZE]
  Time -->|under 1.25x| Abstain
  Time -->|geq 1.25x| Accept[Accept rewrite]
  Accept --> Cache[Fingerprint cache]
  Abstain --> Out[Response]
  Accept --> Out
  Cache --> Out
`;
  return <MermaidDiagram chart={chart} />;
}

/** Compact SVG Venn for Safe / Fast / Cheap (true overlap). */
export function ClaimVennSvg() {
  return (
    <svg viewBox="0 0 420 260" role="img" aria-label="Venn diagram of Safe, Fast SQL, and Cheap API" className="r-venn-svg">
      <circle cx="160" cy="120" r="88" fill="#7eb4ec" fillOpacity="0.18" stroke="#7eb4ec" strokeWidth="1.5" />
      <circle cx="260" cy="120" r="88" fill="#e1e3e9" fillOpacity="0.12" stroke="#e1e3e9" strokeWidth="1.5" />
      <circle cx="210" cy="175" r="88" fill="#f0c674" fillOpacity="0.12" stroke="#f0c674" strokeWidth="1.5" />
      <text x="105" y="95" fill="#7eb4ec" fontSize="13" fontFamily="Public Sans, sans-serif">Safe</text>
      <text x="95" y="112" fill="#a8a9b1" fontSize="10" fontFamily="IBM Plex Mono, monospace">0 wrong</text>
      <text x="285" y="95" fill="#e1e3e9" fontSize="13" fontFamily="Public Sans, sans-serif">Fast SQL</text>
      <text x="275" y="112" fill="#a8a9b1" fontSize="10" fontFamily="IBM Plex Mono, monospace">≥1.25×</text>
      <text x="185" y="230" fill="#f0c674" fontSize="13" fontFamily="Public Sans, sans-serif">Cheap API</text>
      <text x="168" y="246" fill="#a8a9b1" fontSize="10" fontFamily="IBM Plex Mono, monospace">$/case</text>
      <text x="188" y="118" fill="#eeeff2" fontSize="11" fontFamily="Public Sans, sans-serif" fontWeight="500">harness</text>
      <text x="178" y="134" fill="#a8a9b1" fontSize="10" fontFamily="IBM Plex Mono, monospace">≈ frontier</text>
      <text x="118" y="168" fill="#a8a9b1" fontSize="10" fontFamily="IBM Plex Mono, monospace">frontier</text>
      <text x="268" y="168" fill="#a8a9b1" fontSize="10" fontFamily="IBM Plex Mono, monospace">raw*</text>
      <text x="198" y="188" fill="#a8a9b1" fontSize="9" fontFamily="IBM Plex Mono, monospace">rules $0</text>
    </svg>
  );
}
