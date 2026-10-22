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
    const expected = new Map([
      ["Total nonfarm payroll employment", ["CES0000000001", "https://data.bls.gov/timeseries/CES0000000001"]],
      ["U-3 unemployment rate", ["LNS14000000", "https://data.bls.gov/timeseries/LNS14000000"]],
      ["Labor-force participation rate", ["LNS11300000", "https://data.bls.gov/timeseries/LNS11300000"]],
      ["Initial unemployment-insurance claims", ["DOL-UI-SA-INITIAL", "https://www.dol.gov/ui/data.pdf"]],
      ["Job openings", ["JTS000000000000000JOL", "https://data.bls.gov/timeseries/JTS000000000000000JOL"]],
      ["Hires", ["JTS000000000000000HIL", "https://data.bls.gov/timeseries/JTS000000000000000HIL"]]
    ]);
    for (const [label, [seriesId, evidenceUrl]] of expected) {
      const row = within(records).getByRole("row", { name: new RegExp(label) });
      expect(within(row).getByText(seriesId)).toBeTruthy();
      expect(within(row).getByRole("link", { name: "Open original evidence" }).getAttribute("href")).toBe(evidenceUrl);
    }
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
