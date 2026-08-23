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
    {symbol === "system" && <><circle cx="12" cy="12" r="8" /><path d="M4 12h16M12 4v16" /></>}
  </svg>;
}
