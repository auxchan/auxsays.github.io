import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { MotionQaNode, MotionQaReadModel } from "../../data/motionQaReadModel";
import { StructuralContextIcon } from "./StructuralContextIcon";
import { StructuralNodeIcon } from "./StructuralNodeIcon";
import { contextFactorsForNode, type StructuralContextFactor } from "./structuralContextFactors";
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

export function NodeInsightPanel({ model, node, contextFactor, state, onClose, onSelectParent }: { model: MotionQaReadModel; node: MotionQaNode | null; contextFactor: StructuralContextFactor | null; state: string; onClose: () => void; onSelectParent: () => void }) {
  const panelRef = useRef<HTMLElement>(null);
  const [displayNode, setDisplayNode] = useState<MotionQaNode | null>(node);
  const [displayContextFactor, setDisplayContextFactor] = useState<StructuralContextFactor | null>(contextFactor);
  useEffect(() => {
    if (node) { setDisplayNode(node); setDisplayContextFactor(contextFactor); return; }
    const timer = window.setTimeout(() => { setDisplayNode(null); setDisplayContextFactor(null); }, 430);
    return () => window.clearTimeout(timer);
  }, [node, contextFactor]);

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

  const copy = displayContextFactor?.insight ?? displayNode?.insight ?? null;
  const visual = displayNode ? resolveStructuralNodeVisual(displayNode) : null;
  const relationships = displayNode ? model.relationships.filter((edge) => edge.from === displayNode.id || edge.to === displayNode.id) : [];
  const underlyingFactors = displayNode ? contextFactorsForNode(displayNode.id) : [];

  return <aside ref={panelRef} className={`sm-node-guide ${node ? "is-open" : ""} ${displayContextFactor ? "is-context-factor" : ""}`} aria-label="Selected factor guide" aria-hidden={!node} data-selected-node-id={displayNode?.id ?? ""} data-selected-context-factor-id={displayContextFactor?.id ?? ""} data-connected-count={relationships.length} style={visual ? { "--guide-accent": visual.accent, "--guide-fill": visual.fill } as CSSProperties : undefined}>
    {displayNode && copy && visual && <div className="sm-node-guide__inner" key={`${displayNode.id}-${displayContextFactor?.id ?? "core"}`}>
      <header className="sm-node-guide__header">
        <div><small>{displayContextFactor ? `Underlying factor · inside ${displayNode.overviewLabel}` : `${visual.role.replaceAll("_", " ")} · ${stateLabels[state] ?? "Watching"}`}</small><h2>{displayContextFactor?.label ?? displayNode.detailLabel}</h2></div>
        <button type="button" aria-label="Close factor guide" onClick={onClose}>×</button>
      </header>

      <div className={`sm-node-guide__portrait ${displayContextFactor ? "is-context-factor" : ""}`} data-factor-portrait={visual.symbol} data-has-photo="true">
        <span className="sm-node-guide__photo" role="img" aria-label={displayNode.portrait.alt} style={{ "--guide-photo": `url(${displayNode.portrait.imageUrl})` } as CSSProperties} />
        <span className="sm-node-guide__orbit sm-node-guide__orbit--outer" aria-hidden="true" />
        <span className="sm-node-guide__orbit sm-node-guide__orbit--inner" aria-hidden="true" />
        <span className="sm-node-guide__portrait-symbol">{displayContextFactor ? <StructuralContextIcon factorId={displayContextFactor.id} /> : <StructuralNodeIcon symbol={visual.symbol} />}</span>
        <span className="sm-node-guide__portrait-label"><small>{displayContextFactor ? "Selected sublayer" : "Selected factor"}</small><strong>{displayContextFactor ? `Inside ${displayNode.overviewLabel}` : `${relationships.length} direct connections`}</strong></span>
      </div>

      <p className="sm-node-guide__definition">{copy.definition}</p>

      <section><h3>What it tracks</h3><p>{copy.tracks}</p></section>
      <section><h3>Why it matters</h3><p>{copy.impact}</p></section>

      {displayContextFactor ? <section className="sm-node-guide__context-relation"><h3>How it connects to {displayNode.overviewLabel}</h3><p>{displayContextFactor.insight.relation}</p><button type="button" onClick={onSelectParent}>View the parent factor</button></section> : <section className="sm-node-guide__underlying"><h3>Underlying factors</h3><ul>{underlyingFactors.map((factor) => <li key={factor.id}>{factor.label}</li>)}</ul></section>}

      {!displayContextFactor && <section className="sm-node-guide__connections">
        <div><h3>Why these {relationships.length} connections are here</h3><span>Only direct links shown</span></div>
        <ol>{relationships.map((edge) => {
          const incoming = edge.to === displayNode.id;
          const other = model.nodes.find((candidate) => candidate.id === (incoming ? edge.from : edge.to));
          return <li key={edge.id}><span>{incoming ? "Influences this factor" : "This factor can influence"}</span><strong>{other?.detailLabel ?? "Connected factor"}</strong><p>{edge.plainLanguage}</p></li>;
        })}</ol>
      </section>}

      <footer>
        <span>Prototype explanation · synthetic factors and relationships only</span>
        <a href={displayNode.portrait.sourcePage} target="_blank" rel="noreferrer">Photo: {displayNode.portrait.credit} · {displayNode.portrait.license === "CC0_1_0" ? "CC0 1.0" : "Public domain"}</a>
      </footer>
    </div>}
  </aside>;
}
