export type SystemIconName = "barrel" | "gauge" | "truck" | "network" | "lock" | "database" | "check" | "arrow";

export function SystemIcon({ name, size = 24 }: { name: SystemIconName; size?: number }) {
  const paths: Record<SystemIconName, React.ReactNode> = {
    barrel: <><path d="M7 4c0-1.1 2.2-2 5-2s5 .9 5 2v16c0 1.1-2.2 2-5 2s-5-.9-5-2V4Z"/><path d="M7 7c0 1.1 2.2 2 5 2s5-.9 5-2M7 17c0-1.1 2.2-2 5-2s5 .9 5 2"/></>,
    gauge: <><path d="M4.6 18a9 9 0 1 1 14.8 0"/><path d="m12 14 4-5"/><circle cx="12" cy="14" r="1.5"/></>,
    truck: <><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></>,
    network: <><circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="6" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="m7.3 10.9 9.4-3.8M7.3 13.1l9.4 3.8"/></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>
  };
  return <svg className="sm-icon" aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
