import { useEffect, useId, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import type { MetricPoint, StateType } from "../data/publicSnapshotTypes";
import { DataStateLabel } from "./Semantic";

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!media) return;
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

interface ChartFrameProps {
  title: string;
  description: string;
  stateType: StateType;
  data: MetricPoint[];
  unit: string;
  pressures?: { positive: string; offsetting: string };
}

export function ChartFrame({ title, description, stateType, data, unit, pressures }: ChartFrameProps) {
  const id = useId().replaceAll(":", "");
  const reducedMotion = useReducedMotion();
  const [selected, setSelected] = useState(data.at(-1) ?? data[0]);
  const chartData = useMemo(() => data.map((point) => ({
    ...point,
    range: point.rangeLow === undefined || point.rangeHigh === undefined ? undefined : [point.rangeLow, point.rangeHigh]
  })), [data]);

  return (
    <section className="sm-chart-frame" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}>
      <div className="sm-section-heading">
        <div><span className="sm-eyebrow">Primary analytical view</span><h3 id={`${id}-title`}>{title}</h3></div>
        <DataStateLabel state={stateType} />
      </div>
      <p id={`${id}-description`} className="sm-sr-only">{description}</p>
      <p className="sm-chart-selection" aria-live="polite"><strong>{selected?.displayPeriod}</strong> · {selected?.value} {unit}</p>
      <div className="sm-chart-visual">
        <ComposedChart
          data={chartData}
          accessibilityLayer
          responsive
          title={title}
          desc={description}
          style={{ width: "100%", height: "18rem" }}
          margin={{ top: 18, right: 20, bottom: 16, left: 0 }}
          onClick={(event: unknown) => {
            const payload = (event as { activePayload?: Array<{ payload?: MetricPoint }> } | undefined)?.activePayload?.[0]?.payload;
            if (payload) setSelected(payload);
          }}
        >
          <CartesianGrid stroke="var(--aux-sm-line-grid)" strokeDasharray="3 6" vertical={false} />
          <XAxis dataKey="displayPeriod" tick={{ fill: "var(--aux-sm-text-muted)", fontSize: 13 }} tickLine={false} axisLine={{ stroke: "var(--aux-sm-line)" }} />
          <YAxis tick={{ fill: "var(--aux-sm-text-muted)", fontSize: 13 }} tickLine={false} axisLine={false} width={42} />
          <Tooltip contentStyle={{ background: "#101a2a", border: "1px solid #2d445d", borderRadius: 0, fontSize: 14 }} labelStyle={{ color: "#e8f4f6" }} />
          {chartData.some((point) => point.range) && <Area dataKey="range" stroke="none" fill="var(--aux-sm-chart-range)" fillOpacity={0.32} isAnimationActive={!reducedMotion} />}
          <ReferenceLine x={chartData.at(-1)?.displayPeriod} stroke="var(--aux-sm-line-reference)" strokeDasharray="2 4" label={{ value: "Current fixture", fill: "var(--aux-sm-text-muted)", fontSize: 12 }} />
          <Line dataKey="value" type="monotone" stroke="var(--aux-sm-chart-primary)" strokeWidth={3} dot={{ r: 4, fill: "var(--aux-sm-canvas)", strokeWidth: 2 }} activeDot={{ r: 6 }} isAnimationActive={!reducedMotion} />
        </ComposedChart>
      </div>
      <div className="sm-chart-point-controls" aria-label={`${title} data-point controls`}>
        {data.map((point) => <button key={point.period} type="button" className={selected?.period === point.period ? "is-selected" : ""} onClick={() => setSelected(point)}>{point.displayPeriod}<span>{point.value}</span></button>)}
      </div>
      {pressures && <p className="sm-chart-pressure"><strong>Strongest positive:</strong> {pressures.positive} <span aria-hidden="true">·</span> <strong>Strongest offset:</strong> {pressures.offsetting}</p>}
      <details className="sm-data-table">
        <summary>Data table</summary>
        <div className="sm-table-scroll" role="region" aria-label={`${title} table`} tabIndex={0}>
          <table><caption>{title} — synthetic fixture values</caption><thead><tr><th>Period</th><th>State</th><th>Value</th><th>Range</th></tr></thead><tbody>{data.map((point) => <tr key={point.period}><th scope="row">{point.displayPeriod}</th><td><DataStateLabel state={stateType} /></td><td>{point.value} {unit}</td><td>{point.rangeLow === undefined ? "Not applicable" : `${point.rangeLow}–${point.rangeHigh} ${unit}`}</td></tr>)}</tbody></table>
        </div>
      </details>
    </section>
  );
}
