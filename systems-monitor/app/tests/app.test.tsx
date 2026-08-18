import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";

function renderApp(search = "") {
  window.history.replaceState(null, "", `/systems-monitor/${search}`);
  return render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
}

describe("Systems Monitor shell", () => {
  it("exposes exactly three primary views and persistent disclosure", async () => {
    renderApp();
    const nav = await screen.findByRole("navigation", { name: "Systems Monitor views" });
    expect(within(nav).getAllByRole("button")).toHaveLength(3);
    expect(screen.getAllByText("SYNTHETIC TEST DATA").length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: /SYNTHETIC TEST SYSTEM 01/ })).toBeTruthy();
  });

  it("navigates views and writes URL state", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Outlook/ }));
    expect(await screen.findByRole("heading", { name: /Ranges, evidence/ })).toBeTruthy();
    expect(window.location.search).toBe("?view=outlook");
    fireEvent.click(screen.getByRole("button", { name: /Next Year/ }));
    expect(window.location.search).toContain("horizon=next-year");
    fireEvent.click(screen.getByRole("button", { name: /Open bounded Trace/ }));
    expect(await screen.findByRole("heading", { name: "Synthetic relationship path" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /SYNTHETIC TEST/ }).length).toBeGreaterThanOrEqual(6);
  });

  it("drills through ranked hierarchy and supports browser history", async () => {
    renderApp();
    const drill = await screen.findByRole("button", { name: /Drill in SYNTHETIC TEST DRIVER 01/ });
    fireEvent.click(drill);
    expect(window.location.search).toContain("path=fixture-driver-1");
    expect(await screen.findByRole("heading", { name: "SYNTHETIC TEST DRIVER 01" })).toBeTruthy();
    window.history.back();
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("searches across entity types and routes to evidence", async () => {
    renderApp();
    const search = screen.getByRole("searchbox", { name: "Explore synthetic entities" });
    fireEvent.change(search, { target: { value: "facility alpha" } });
    const result = await screen.findByRole("button", { name: /SYNTHETIC TEST FACILITY ALPHA/ });
    fireEvent.click(result);
    expect(await screen.findByRole("heading", { name: /Observed and calculated fixture evidence/ })).toBeTruthy();
    expect(window.location.search).toBe("?view=verified");
  });

  it("renders every explicit degraded fixture state without a substitute conclusion", async () => {
    renderApp("?view=outlook");
    const lab = await screen.findByLabelText("Fixture state lab");
    fireEvent.change(lab, { target: { value: "insufficient-evidence" } });
    expect(screen.getByText("Insufficient evidence")).toBeTruthy();
    fireEvent.change(lab, { target: { value: "forecast-unavailable" } });
    expect(screen.getAllByText("Forecast unavailable").length).toBeGreaterThan(0);
    expect(await screen.findByText(/No range or conclusion is substituted/)).toBeTruthy();
  });

  it("exposes View All, near-cutoff context, full hierarchy, and breadcrumbs", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /View All 11/ }));
    expect(screen.getByText("SYNTHETIC TEST DRIVER 11")).toBeTruthy();
    expect(screen.getByText(/Prior #11 · Near tie · Near cutoff/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Drill in SYNTHETIC TEST DRIVER 01/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Drill in SYNTHETIC TEST FACTOR 01/ }));
    expect(await screen.findByRole("heading", { name: "SYNTHETIC TEST FACTOR 01" })).toBeTruthy();
    const breadcrumbs = screen.getByRole("navigation", { name: "Selected hierarchy" });
    expect(within(breadcrumbs).getByRole("button", { name: "DRIVER 01" })).toBeTruthy();
  });

  it("provides material chart point controls and a table alternative", async () => {
    renderApp();
    const chart = await screen.findByRole("region", { name: "Synthetic state trajectory" });
    expect(within(chart).getAllByRole("button", { name: /Synthetic period/ })).toHaveLength(6);
    fireEvent.click(within(chart).getByText("View accessible data table"));
    expect(within(chart).getByRole("table", { name: /synthetic fixture values/ })).toBeTruthy();
  });

  it("shows all three dynamic horizons and evidence semantics", async () => {
    renderApp("?view=outlook");
    expect(await screen.findByRole("button", { name: /Current Year/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Next Year/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /\+3 Years/ })).toBeTruthy();
    expect(screen.getByText("What would change our mind?", { exact: false })).toBeTruthy();
    expect(screen.getAllByText(/expected-opening units/).length).toBeGreaterThan(0);
  });

  it("provides native collapsible context and mobile evidence-sheet controls", async () => {
    renderApp("?view=verified");
    const context = await screen.findByText("System context details");
    const contextDetails = context.closest("details") as HTMLDetailsElement;
    expect(contextDetails.open).toBe(true);
    fireEvent.click(context);
    expect(contextDetails.open).toBe(false);
    const sheetSummary = screen.getByText("Source inspector", { selector: "summary" });
    const sheet = sheetSummary.closest("details") as HTMLDetailsElement;
    expect(sheet.open).toBe(false);
    fireEvent.click(sheetSummary);
    expect(sheet.open).toBe(true);
  });

  it.each([
    ["delayed", "Source delayed"],
    ["stale", "Source stale"],
    ["high-disagreement", "High model disagreement"],
    ["partial-payload", "Partial payload"]
  ])("renders %s without hiding the shell", async (variant, message) => {
    renderApp();
    fireEvent.change(await screen.findByLabelText("Fixture state lab"), { target: { value: variant } });
    expect(screen.getByText(message)).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Systems Monitor views" })).toBeTruthy();
  });

  it("renders terminal loading and snapshot-unavailable states explicitly", async () => {
    const first = renderApp();
    fireEvent.change(await screen.findByLabelText("Fixture state lab"), { target: { value: "loading" } });
    expect(screen.getByRole("status")).toBeTruthy();
    first.unmount();
    const second = renderApp();
    fireEvent.change(await screen.findByLabelText("Fixture state lab"), { target: { value: "snapshot-unavailable" } });
    expect(screen.getByRole("alert")).toBeTruthy();
    second.unmount();
  });
});
