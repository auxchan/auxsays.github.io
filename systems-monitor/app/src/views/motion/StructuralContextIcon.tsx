export function StructuralContextIcon({ factorId }: { factorId: string }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const
  };

  return <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
    {factorId === "context-domestic-output" && <><path d="M3 20V9l5 3V9l5 3V5h6v15H3Z" /><path d="M6 17h2m3 0h2m3 0h2" /></>}
    {factorId === "context-import-flow" && <><path d="M4 7h10m-3-3 3 3-3 3M20 17H10m3-3-3 3 3 3" /></>}
    {factorId === "context-utilization" && <><path d="M5 17a8 8 0 1 1 14 0" /><path d="m12 13 4-4M8 19h8" /></>}
    {factorId === "context-maintenance" && <><circle cx="12" cy="12" r="3" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2" /></>}
    {factorId === "context-inventory" && <><path d="M4 7h16v13H4zM3 4h18v3H3z" /><path d="M9 11h6" /></>}
    {factorId === "context-headroom" && <><path d="M5 4h14v16H5zM8 15h8" /><path d="m12 7-3 3m3-3 3 3" /></>}
    {factorId === "context-power-cost" && <><path d="m14 2-7 11h5l-2 9 7-12h-5l2-8Z" /><path d="M19 5h2m-1-1v2" /></>}
    {factorId === "context-grid-reliability" && <><circle cx="12" cy="12" r="8" /><path d="m8 12 2.5 2.5L16 9" /></>}
    {factorId === "context-output-mix" && <><circle cx="8" cy="8" r="3" /><rect x="13" y="5" width="6" height="6" rx="1" /><path d="m8 14-4 6h8l-4-6Zm8 0-3 6h6l-3-6Z" /></>}
    {factorId === "context-product-stocks" && <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>}
    {factorId === "context-terminal-flow" && <><path d="M3 12h14m-4-4 4 4-4 4" /><path d="M20 5v14" /></>}
    {factorId === "context-pipeline-room" && <><path d="M3 8h6v8H3m18-8h-6v8h6M9 12h6" /><path d="m11 10-2 2 2 2m2-4 2 2-2 2" /></>}
    {factorId === "context-rail-throughput" && <><path d="M6 3h12v13H6zM8 6h8M8 11h8" /><circle cx="9" cy="19" r="2" /><circle cx="15" cy="19" r="2" /></>}
    {factorId === "context-truck-capacity" && <><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7z" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>}
    {factorId === "context-new-orders" && <><path d="M6 3h12v18H6zM9 8h6m-6 4h6m-6 4h3" /><path d="M3 6h3m12 0h3" /></>}
    {factorId === "context-capacity-use" && <><path d="M4 20V9h4v11m4 0V4h4v16m4 0V12h-4" /><path d="M2 20h20" /></>}
    {factorId === "context-hours-worked" && <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></>}
    {factorId === "context-hiring-demand" && <><circle cx="9" cy="8" r="3" /><path d="M3 20c0-5 2-8 6-8s6 3 6 8M18 9v6m-3-3h6" /></>}
  </svg>;
}
