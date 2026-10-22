import { createRoot } from "react-dom/client";
import { SnapshotProvider } from "./app/SnapshotContext";
import { SystemsMonitorApp } from "./app/SystemsMonitorApp";
import "./styles.css";

const root = document.getElementById("systems-monitor-root");
if (!root) throw new Error("Systems Monitor root was not found");

root.dataset.auxProduct = "systems-monitor";
createRoot(root).render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
