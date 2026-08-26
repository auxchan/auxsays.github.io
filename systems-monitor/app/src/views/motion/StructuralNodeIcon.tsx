import type { StructuralNodeSymbol } from "./structuralVisualLanguage";

export function StructuralNodeIcon({ symbol }: { symbol: StructuralNodeSymbol }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const
  };

  return <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
    {symbol === "drop" && <path d="M12 3c4.5 5 6 7.7 6 10.3A6 6 0 0 1 6 13.3C6 10.7 7.5 8 12 3Z" />}
    {symbol === "refinery" && <><path d="M4 20V9h5v11M13 20V4h5v16M2 20h20" /><path d="M4 12h5M13 8h5" /></>}
    {symbol === "tank" && <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v14c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 18c0-1.7 3.1-3 7-3s7 1.3 7 3" /></>}
    {symbol === "bolt" && <path d="m14 2-8 12h6l-2 8 8-12h-6l2-8Z" />}
    {symbol === "flame" && <path d="M13 2c5 5 5 9 2 12 0-3-2-5-4-6 1 4-4 5-2 10 1 2 3 3 5 3a7 7 0 0 0 5-11c-1-2-3-5-6-8Z" />}
    {symbol === "split" && <><path d="M3 12h6M9 12l7-7M9 12l7 7" /><path d="M16 5h4v4M16 19h4v-4" /></>}
    {symbol === "freight" && <><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7z" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>}
    {symbol === "factory" && <path d="M3 21V9l6 4V9l6 4V4h6v17H3Zm4-3h2m3 0h2" />}
    {symbol === "people" && <><circle cx="8" cy="7" r="3" /><circle cx="17" cy="8" r="2.5" /><path d="M2.5 21c0-5 2-8 5.5-8s5.5 3 5.5 8M13 15c1-2 5-2 6.5 0 1 1.5 1.5 3.5 1.5 6" /></>}
    {symbol === "labor-market" && <><circle cx="12" cy="12" r="3" /><circle cx="5" cy="6" r="2" /><circle cx="19" cy="6" r="2" /><circle cx="12" cy="21" r="2" /><path d="m7 7.7 3 2.6m7-2.6-3 2.6m-2 4.7v4" /></>}
    {symbol === "system" && <><circle cx="12" cy="12" r="8" /><path d="M4 12h16M12 4v16" /></>}
    {symbol === "briefcase" && <><rect x="3" y="7" width="18" height="12" rx="2" /><path d="M8 7V5h8v2M3 12h18M10 12v2h4v-2" /></>}
    {symbol === "unemployment" && <><circle cx="9" cy="7" r="3" /><path d="M3 20c0-5 2-8 6-8 2.1 0 3.7.8 4.7 2.2M16 17h5M18.5 14.5v5" /></>}
    {symbol === "participation" && <><circle cx="6" cy="6" r="2" /><circle cx="12" cy="5" r="2" /><circle cx="18" cy="6" r="2" /><path d="M6 10v8M12 9v10M18 10v8M3 13h6M9 12h6M15 13h6M4 21h16" /></>}
    {symbol === "claims" && <><path d="M6 3h9l3 3v15H6zM15 3v4h4" /><path d="M9 11h6M9 15h5" /></>}
    {symbol === "openings" && <><path d="M5 3h12v18H5zM17 12h3" /><circle cx="14" cy="12" r=".7" fill="currentColor" stroke="none" /></>}
    {symbol === "hire" && <><circle cx="9" cy="7" r="3" /><path d="M3 20c0-5 2-8 6-8s6 3 6 8M18 9v6M15 12h6" /></>}
    {symbol === "clock" && <><circle cx="12" cy="12" r="9" /><path d="M12 7v6l4 2" /></>}
    {symbol === "earnings" && <><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5c-.8-1-2-1.5-3.5-1.5-2 0-3.5 1-3.5 2.5 0 3.8 7 1.2 7 5 0 1.5-1.5 2.5-3.5 2.5-1.6 0-3-.6-3.8-1.8M12 5v14" /></>}
    {symbol === "separations" && <><path d="M3 12h7M14 12h7M10 12l4-5M10 12l4 5" /><path d="M18 4l3 3-3 3M18 14l3 3-3 3" /></>}
    {symbol === "ratio" && <><circle cx="7" cy="7" r="2.5" /><circle cx="17" cy="17" r="2.5" /><path d="M6 18 18 6" /></>}
  </svg>;
}
