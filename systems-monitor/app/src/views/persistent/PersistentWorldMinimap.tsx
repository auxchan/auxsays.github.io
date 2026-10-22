import { persistentWorldPath, type PersistentWorldReadModel } from "../../data/persistentWorldModel";

interface Props {
  model: PersistentWorldReadModel;
  selectedPlacementId: string | null;
  onSelect: (placementId: string | null) => void;
}

const SIZE = 156;
const PADDING = 14;

export function PersistentWorldMinimap({ model, selectedPlacementId, onSelect }: Props) {
  const levelOne = model.childrenByPlacement[model.outcomePlacementId].map((id) => model.placements[id]);
  const all = [model.placements[model.outcomePlacementId], ...levelOne];
  const extent = Math.max(...all.flatMap((item) => [Math.abs(item.x), Math.abs(item.y)]), 1);
  const scale = (SIZE / 2 - PADDING) / extent;
  const point = (x: number, y: number) => ({ x: SIZE / 2 + x * scale, y: SIZE / 2 + y * scale });
  const route = new Set(persistentWorldPath(model, selectedPlacementId).map((item) => item.id));
  const selected = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
  const activeSector = selected?.depth ? selected.sector : -1;
  const activeLevelOne = activeSector >= 0 ? levelOne[activeSector] : undefined;
  const activePoint = activeLevelOne ? point(activeLevelOne.x, activeLevelOne.y) : point(0, 0);
  const depthRatio = selected?.depth === 1 ? 1 : selected?.depth === 2 ? .76 : selected?.depth === 3 ? .9 : 0;
  const current = activeLevelOne
    ? { x: SIZE / 2 + (activePoint.x - SIZE / 2) * depthRatio, y: SIZE / 2 + (activePoint.y - SIZE / 2) * depthRatio }
    : point(0, 0);

  return <aside className="sm-pw-minimap" aria-label="World location">
    <header><span>World position</span><strong>Level {(selected?.depth ?? 0) + 1} of 4</strong></header>
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
      <circle className="sm-pw-minimap__orbit" cx={SIZE / 2} cy={SIZE / 2} r={SIZE / 2 - PADDING} />
      <circle className="sm-pw-minimap__depth" cx={SIZE / 2} cy={SIZE / 2} r={(SIZE / 2 - PADDING) * .76} />
      <circle className="sm-pw-minimap__depth" cx={SIZE / 2} cy={SIZE / 2} r={(SIZE / 2 - PADDING) * .9} />
      {levelOne.map((placement) => {
        const parent = point(0, 0); const child = point(placement.x, placement.y); const active = placement.sector === activeSector;
        return <g key={placement.id} data-active={active} data-route={route.has(placement.id)}>
          <line x1={parent.x} y1={parent.y} x2={child.x} y2={child.y} />
          <circle cx={child.x} cy={child.y} r={active ? 5 : 3.4} />
        </g>;
      })}
      <circle className="sm-pw-minimap__root" cx={SIZE / 2} cy={SIZE / 2} r="5" />
      <circle className="sm-pw-minimap__current" cx={Math.max(7, Math.min(SIZE - 7, current.x))} cy={Math.max(7, Math.min(SIZE - 7, current.y))} r="7" />
    </svg>
    <div className="sm-pw-minimap__jumps" aria-label="Jump to a system">
      <button type="button" onClick={() => onSelect(null)}>Outcome</button>
      {levelOne.map((placement) => <button type="button" key={placement.id} aria-current={placement.sector === activeSector ? "location" : undefined} onClick={() => onSelect(placement.id)}>{placement.order}</button>)}
    </div>
    <p>{activeSector >= 0 ? model.factors[levelOne[activeSector].canonicalFactorId].label : "Employment overview"}</p>
  </aside>;
}
