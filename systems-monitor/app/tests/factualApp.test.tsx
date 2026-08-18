import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { candidate } from "./factualCandidate.test";

describe("local factual UI mode", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/systems-monitor/");
    window.localStorage.clear();
    window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__ = candidate();
  });

  afterEach(() => {
    cleanup();
    delete window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__;
    window.localStorage.clear();
  });

  it("renders six factual observations without fixture disclosure", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: "U.S. labor observations" })).toBeTruthy();
    expect(screen.getAllByText("LOCAL FACTUAL CANDIDATE").length).toBeGreaterThan(0);
    expect(screen.queryByText("SYNTHETIC TEST DATA")).toBeNull();
    expect(within(screen.getByRole("region", { name: "Factual labor observations" })).getAllByRole("row")).toHaveLength(7);
  });

  it("shows no synthetic forecast in factual Outlook", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "U.S. labor observations" });
    fireEvent.click(screen.getByRole("button", { name: "Outlook" }));
    expect(await screen.findAllByRole("heading", { name: "Forecast unavailable / not yet supported" })).toHaveLength(2);
    expect(document.body.textContent).not.toContain("Synthetic ranges");
    expect(document.body.textContent).not.toContain("Scenario alpha");
  });
});
