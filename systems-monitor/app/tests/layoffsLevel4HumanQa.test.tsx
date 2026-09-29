import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LayoffsLevel4QaView } from "../src/views/layoffs-qa/LayoffsLevel4QaView";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { SnapshotProvider } from "../src/app/SnapshotContext";

const exactTen = [
  "Layoffs & Discharges",
  "Temporary Layoffs",
  "Permanent Job Losers",
  "Payroll Contraction Breadth",
  "Gross Job Losses",
  "Jobs Lost at Establishment Deaths",
  "Business Bankruptcy Filings, 12-Month Total",
  "Real Output Growth",
  "Real Personal Consumption Expenditures Growth",
  "FEMA Disaster Declaration",
] as const;

describe("Initial UI Claims Level-4 Human QA surface", () => {
  it("exposes exactly the ten governed production placements", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    expect(container.querySelectorAll(".sm-l4qa-factor")).toHaveLength(10);
    expect(container.querySelectorAll(".sm-l4qa-series")).toHaveLength(11);
    exactTen.forEach((label) => expect(screen.getByRole("heading", { name: label })).toBeTruthy());
    expect(container.querySelectorAll('[data-disposition="ACCEPTED_OBSERVATION"]')).toHaveLength(5);
    expect(container.querySelector(".sm-l4qa")?.getAttribute("data-human-qa")).toBe("PENDING");
    expect(container.querySelector(".sm-l4qa")?.getAttribute("data-unexplained-renderer-fixtures")).toBe("0");
  });

  it("reuses accepted evidence while keeping pending and blocked reasons explicit", () => {
    render(<LayoffsLevel4QaView />);
    const layoffs = screen.getByRole("heading", { name: "Layoffs & Discharges" }).closest("section")!;
    expect(within(layoffs).getByText("JTS000000000000000LDL")).toBeTruthy();
    expect(within(layoffs).getByText("JTS000000000000000LDR")).toBeTruthy();

    const deaths = screen.getByRole("heading", { name: "Jobs Lost at Establishment Deaths" }).closest("section")!;
    expect(within(deaths).getByText("Accepted history · 1 period")).toBeTruthy();
    expect(within(deaths).getByText("Not yet available")).toBeTruthy();
    expect(within(deaths).getByText("Layoffs & Job Destruction › Firm Death / Shutdown Stress › Jobs Lost at Establishment Deaths")).toBeTruthy();

    const breadth = screen.getByRole("heading", { name: "Payroll Contraction Breadth" }).closest("section")!;
    expect(within(breadth).getAllByText(/GOVERNED CALC PENDING METHODOLOGY CALIBRATION/).length).toBeGreaterThan(0);
    expect(within(breadth).getByText(/has not approved the final CES universe/)).toBeTruthy();

    const output = screen.getByRole("heading", { name: "Real Output Growth" }).closest("section")!;
    expect(within(output).getAllByText(/BLOCKED CREDENTIAL/).length).toBeGreaterThan(0);
    expect(within(output).getByText(/AUXSAYS_BEA_USER_ID is missing/)).toBeTruthy();
  });

  it("presents FEMA as an event with no scalar or directional UI", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    const fema = screen.getByRole("heading", { name: "FEMA Disaster Declaration" }).closest("section")!;
    expect(within(fema).getByText(/official declaration event with geography and time context/i)).toBeTruthy();
    expect(within(fema).getByText(/not a scalar reading/i)).toBeTruthy();
    expect(fema.textContent).not.toMatch(/[↑↓]/);
    expect(fema.textContent?.toLowerCase()).not.toContain("materiality");
    expect(fema.textContent?.toLowerCase()).not.toContain("economic impact");
    expect(fema.textContent?.toLowerCase()).not.toContain("claims impact");
    expect(container.querySelectorAll('[data-source-state="event"]')).toHaveLength(1);
  });

  it("keeps causal, materiality, prediction, and fixture claims off the placement cards", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    const cards = container.querySelector(".sm-l4qa-grid")?.textContent?.toLowerCase() ?? "";
    expect(cards).not.toContain("materiality");
    expect(cards).not.toContain("destination impact");
    expect(cards).not.toContain("supportive");
    expect(cards).not.toContain("adverse");
    expect(cards).not.toContain("causality");
    expect(cards).not.toContain("prediction");
    expect(cards).not.toContain("renderer fixture");
  });

  it("shows the exact-ten placement count in the shared QA shell", async () => {
    window.location.hash = "#layoffs-level4-qa";
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByText("10 placements")).toBeTruthy();
    expect(screen.queryByText("12 factors")).toBeNull();
  });
});
