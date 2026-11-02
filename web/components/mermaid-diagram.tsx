"use client";

import { useEffect, useId, useRef, useState } from "react";

let mermaidReady: Promise<typeof import("mermaid").default> | null = null;
let renderChain: Promise<void> = Promise.resolve();

async function getMermaid() {
  if (!mermaidReady) {
    mermaidReady = import("mermaid").then((mod) => {
      const mermaid = mod.default;
      mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        securityLevel: "loose",
        fontFamily: "Public Sans, sans-serif",
        flowchart: { curve: "basis", padding: 10, htmlLabels: true, useMaxWidth: true },
        sequence: { useMaxWidth: true, actorMargin: 28, messageMargin: 28 },
        themeVariables: {
          darkMode: true,
          background: "#131315",
          primaryColor: "#1d242d",
          primaryTextColor: "#eeeff2",
          primaryBorderColor: "#7eb4ec",
          secondaryColor: "#202024",
          tertiaryColor: "#171719",
          lineColor: "#646975",
          textColor: "#eeeff2",
          mainBkg: "#1d242d",
          nodeBorder: "#494b53",
          clusterBkg: "#171719",
          clusterBorder: "#2c2d32",
          titleColor: "#eeeff2",
          edgeLabelBackground: "#131315",
          actorBkg: "#1d242d",
          actorBorder: "#7eb4ec",
          actorTextColor: "#eeeff2",
          signalColor: "#a8a9b1",
          signalTextColor: "#eeeff2",
          labelBoxBkgColor: "#1d242d",
          labelBoxBorderColor: "#494b53",
          labelTextColor: "#eeeff2",
          noteBkgColor: "#202024",
          noteTextColor: "#eeeff2",
          noteBorderColor: "#494b53",
        },
      });
      return mermaid;
    });
  }
  return mermaidReady;
}

export function MermaidDiagram({ chart, className = "" }: { chart: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const mermaid = await getMermaid();
        const id = `mmd${reactId}${Date.now().toString(36)}`;
        const { svg } = await mermaid.render(id, chart.trim());
        if (cancelled || !ref.current) return;
        ref.current.innerHTML = svg;
        const svgEl = ref.current.querySelector("svg");
        if (svgEl) {
          svgEl.removeAttribute("height");
          svgEl.style.width = "100%";
          svgEl.style.height = "auto";
          svgEl.style.maxWidth = "100%";
        }
        setError("");
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Diagram failed");
      }
    };
    renderChain = renderChain.then(run, run);
    return () => {
      cancelled = true;
    };
  }, [chart, reactId]);

  if (error) return <p className="r-caption">Diagram error: {error}</p>;
  return <div className={`r-mermaid ${className}`} ref={ref} />;
}
