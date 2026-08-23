import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { MotionQaNode, MotionQaReadModel } from "../../data/motionQaReadModel";
import { StructuralNodeIcon } from "./StructuralNodeIcon";
import { resolveStructuralNodeVisual } from "./structuralVisualLanguage";

const stateLabels: Record<string, string> = {
  SIGNAL_READY: "Ready",
  IDLE: "Watching",
  ACTIVE: "Active",
  TRANSMITTING: "Moving",
  DELAYING: "Waiting",
  AMPLIFYING: "Strengthening",
  BLOCKING: "Constrained",
  ABSORBING: "Absorbing",
  RESOLVED: "Settled"
};

export function NodeInsightPanel({ model, node, state, onClose }: { model: MotionQaReadModel; node: MotionQaNode | null; state: string; onClose: () => void }) {
  const panelRef = useRef<HTMLElement>(null);
  const [displayNode, setDisplayNode] = useState<MotionQaNode | null>(node);
  useEffect(() => {
    if (node) { setDisplayNode(node); return; }
    const timer = window.setTimeout(() => setDisplayNode(null), 430);
    return () => window.clearTimeout(timer);
  }, [node]);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const containScroll = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      panel.scrollTop += event.deltaY;
    };
    panel.addEventListener("wheel", containScroll, { passive: false });
    return () => panel.removeEventListener("wheel", containScroll);
  }, []);

  const copy = displayNode?.insight ?? null;
  const visual = displayNode ? resolveStructuralNodeVisual(displayNode) : null;
  const relationships = displayNode ? model.relationships.filter((edge) => edge.from === displayNode.id || edge.to === displayNode.id) : [];

  return <aside ref={panelRef} className={`sm-node-guide ${node ? "is-open" : ""}`} aria-label="Selected factor guide" aria-hidden={!node} data-selected-node-id={displayNode?.id ?? ""} data-connected-count={relationships.length} style={visual ? { "--guide-accent": visual.accent, "--guide-fill": visual.fill } as CSSProperties : undefined}>
    {displayNode && copy && visual && <div className="sm-node-guide__inner" key={displayNode.id}>
      <header className="sm-node-guide__header">
        <div><small>{visual.role.replaceAll("_", " ")} · {stateLabels[state] ?? "Watching"}</small><h2>{displayNode.detailLabel}</h2></div>
        <button type="button" aria-label="Close factor guide" onClick={onClose}>×</button>
      </header>

      <div className="sm-node-guide__portrait" data-factor-portrait={visual.symbol}>
        <span className="sm-node-guide__orbit sm-node-guide__orbit--outer" aria-hidden="true" />
        <span className="sm-node-guide__orbit sm-node-guide__orbit--inner" aria-hidden="true" />
        <span className="sm-node-guide__portrait-symbol"><StructuralNodeIcon symbol={visual.symbol} /></span>
        <span className="sm-node-guide__portrait-label"><small>Selected factor</small><strong>{relationships.length} direct connections</strong></span>
      </div>

      <p className="sm-node-guide__definition">{copy.definition}</p>

      <section><h3>What it tracks</h3><p>{copy.tracks}</p></section>
      <section><h3>Why it matters</h3><p>{copy.impact}</p></section>

      <section className="sm-node-guide__connections">
        <div><h3>Why these {relationships.length} connections are here</h3><span>Only direct links shown</span></div>
        <ol>{relationships.map((edge) => {
          const incoming = edge.to === displayNode.id;
          const other = model.nodes.find((candidate) => candidate.id === (incoming ? edge.from : edge.to));
          return <li key={edge.id}><span>{incoming ? "Influences this factor" : "This factor can influence"}</span><strong>{other?.detailLabel ?? "Connected factor"}</strong><p>{edge.plainLanguage}</p></li>;
        })}</ol>
      </section>

      <footer>Prototype explanation · synthetic relationships only</footer>
    </div>}
  </aside>;
}
