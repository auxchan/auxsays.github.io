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
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("SYNTHETIC TEST DATA");
    expect(text).not.toContain("Synthetic ranges");
    expect(text).not.toContain("Scenario alpha");
    expect(text).not.toContain("FCST");
    expect(text).not.toContain("SCEN");
    expect(text).not.toContain("Trace");
    expect(text).not.toContain("Industries requiring most human capital");
  });

  it("makes each official series and original evidence reachable without conflating methodology", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "U.S. labor observations" });
    fireEvent.click(screen.getByRole("button", { name: "Verified Data" }));
    await screen.findByRole("heading", { name: "Observed factual evidence — local review candidate" });
    const records = screen.getByRole("region", { name: "Factual observation records" });
    for (const seriesId of ["CES0000000001", "LNS14000000", "LNS11300000", "DOL-UI-SA-INITIAL", "JTS000000000000000JOL", "JTS000000000000000HIL"]) {
      expect(within(records).getByText(seriesId)).toBeTruthy();
    }
    const evidenceLinks = within(records).getAllByRole("link", { name: "Open original evidence" });
    expect(evidenceLinks).toHaveLength(6);
    expect(evidenceLinks.map((link) => link.getAttribute("href"))).toContain("https://www.dol.gov/ui/data.pdf");
    expect(screen.getAllByText("Source / data evidence").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Methodology").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Open official methodology", hidden: true }).length).toBeGreaterThan(0);
  });

  it("exposes the factual DOL revision and replay proof with both releases", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "U.S. labor observations" });
    fireEvent.click(screen.getByRole("button", { name: "Verified Data" }));
    const proof = await screen.findByRole("region", { name: "DOL revision and replay evidence" });
    fireEvent.click(within(proof).getByText("DOL revision and replay example"));
    expect(within(proof).getAllByText("217,000 claims").length).toBeGreaterThanOrEqual(2);
    expect(within(proof).getAllByText("210,000 claims").length).toBeGreaterThanOrEqual(2);
    expect(within(proof).getByText("As known March 10")).toBeTruthy();
    expect(within(proof).getByText("Latest revised truth")).toBeTruthy();
    const releaseLinks = within(proof).getAllByRole("link", { name: "Open original DOL release" });
    expect(releaseLinks).toHaveLength(2);
    expect(releaseLinks[0].getAttribute("href")).toContain("20240471.pdf");
    expect(releaseLinks[1].getAttribute("href")).toContain("20240527.pdf");
  });
});
