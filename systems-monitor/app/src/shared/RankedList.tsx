import { useState } from "react";
import type { NavigationNode, RankedHumanCapitalItem } from "../data/publicSnapshotTypes";

type RankedItem = NavigationNode | RankedHumanCapitalItem;

function itemValue(item: RankedItem) {
  return "displayValue" in item ? item.displayValue : `${item.stateSummaryRefs.length} synthetic state references`;
}

export function RankedList({
  title,
  items,
  onSelect,
  selectionLabel = "Explore"
}: {
  title: string;
  items: RankedItem[];
  onSelect?: (item: RankedItem) => void;
  selectionLabel?: string;
}) {
  const [viewAll, setViewAll] = useState(false);
  const visible = viewAll ? items : items.slice(0, 10);
  return (
    <section className="sm-ranked" aria-labelledby={`${title.replaceAll(" ", "-")}-title`}>
      <div className="sm-section-heading"><h3 id={`${title.replaceAll(" ", "-")}-title`}>{title}</h3><span>{viewAll ? `All ${items.length}` : `Top ${Math.min(10, items.length)}`}</span></div>
      <ol>
        {visible.map((item) => (
          <li key={item.id} className={item.nearTie ? "is-near-tie" : ""}>
            <div className="sm-rank-number">#{item.rank}</div>
            <div className="sm-rank-copy"><strong>{item.label}</strong><span>{itemValue(item)}</span><small>Prior #{item.priorRank ?? "—"}{item.nearTie ? " · Near tie" : ""}{item.nearCutoff ? " · Near cutoff" : ""} · Fixture evidence</small></div>
            {onSelect && <button type="button" onClick={() => onSelect(item)} aria-label={`${selectionLabel} ${item.label}`}>{selectionLabel}</button>}
          </li>
        ))}
      </ol>
      {items.length > 10 && <button className="sm-view-all" type="button" onClick={() => setViewAll((value) => !value)}>{viewAll ? "Show Top 10" : `View All ${items.length}`}<span>Ranks 10 and 11 are supplied as effectively tied in this fixture.</span></button>}
    </section>
  );
}
