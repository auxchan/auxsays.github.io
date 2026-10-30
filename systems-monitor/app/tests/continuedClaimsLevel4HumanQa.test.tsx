import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { ContinuedClaimsLevel4QaView } from "../src/views/layoffs-qa/ContinuedClaimsLevel4QaView";

const exactTen = [
  "Initial Claims",
  "Hires Rate",
  "Job Openings Rate",
  "Total Nonfarm Payroll Change",
  "Temporary Help Employment",
  "Average Weekly Hours",
  "Business Formations Within 4 Quarters",
  "Real GDP Growth",
  "Real Personal Consumption Expenditures Growth",
  "State-Level Payroll Growth Breadth",
] as const;

describe("Continued Claims Level-4 Human QA surface", () => {
  it("keeps the two parent observations distinct", () => {
    const { container } = render(<ContinuedClaimsLevel4QaView />);
    const parent = container.querySelector<HTMLElement>(".sm-l4qa-parent")!;
    expect(within(parent).getByRole("heading", { name: "Two observations, never one scalar" })).toBeTruthy();
    expect(within(parent).getByRole("heading", { name: "Continued unemployment-insurance claims" })).toBeTruthy();
    expect(within(parent).getByRole("heading", { name: "Insured unemployment rate" })).toBeTruthy();
    expect(within(parent).getByText("DOL-UI-SA-CONTINUED · ContinuedClaims/SA")).toBeTruthy();
    expect(within(parent).getByText("DOL-UI-SA-IUR · IUR/SA")).toBeTruthy();
    expect(within(parent).getByText("claims")).toBeTruthy();
    expect(within(parent).getByText("percent")).toBeTruthy();
  });

  it("exposes exactly ten governed child placements, the approved 114-record baseline, and current append-only histories", () => {
    const { container } = render(<ContinuedClaimsLevel4QaView />);
    expect(container.querySelectorAll(".sm-l4qa-factor")).toHaveLength(10);
    exactTen.forEach((label) => expect(screen.getByRole("heading", { name: label })).toBeTruthy());
    expect(screen.queryByRole("heading", { name: "Payroll Growth" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Regional Employment Growth" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Business Formations" })).toBeNull();
    expect(container.querySelectorAll('[data-disposition="ACCEPTED_OBSERVATION"]')).toHaveLength(5);
    expect(container.querySelector(".sm-l4qa")?.getAttribute("data-human-qa")).toBe("PENDING");
    expect(container.querySelector(".sm-l4qa")?.getAttribute("data-unexplained-renderer-fixtures")).toBe("0");
    expect(screen.getByText("114")).toBeTruthy();

    const claims = screen.getByRole("heading", { name: "Initial Claims" }).closest("section")!;
    const claimsRecords = within(claims).getByText("Accepted records").parentElement?.querySelector("dd")?.childNodes[0].textContent ?? "0";
    expect(Number(claimsRecords)).toBeGreaterThanOrEqual(36);
    const hires = screen.getByRole("heading", { name: "Hires Rate" }).closest("section")!;
    const hiresRecords = within(hires).getByText("Accepted records").parentElement?.querySelector("dd")?.childNodes[0].textContent ?? "0";
    expect(Number(hiresRecords)).toBeGreaterThanOrEqual(19);
  });

  it("makes every unresolved child state and decision explicit", () => {
    render(<ContinuedClaimsLevel4QaView />);
    const payroll = screen.getByRole("heading", { name: "Total Nonfarm Payroll Change" }).closest("section")!;
    expect(within(payroll).getAllByText(/GOVERNED CALC METHOD APPROVED OUTPUT ACCEPTANCE PENDING/).length).toBeGreaterThan(0);
    expect(within(payroll).getByText(/CALC_CANDIDATE_PENDING_ACCEPTANCE/i)).toBeTruthy();

    const business = screen.getByRole("heading", { name: "Business Formations Within 4 Quarters" }).closest("section")!;
    expect(within(business).getAllByText(/SOURCE IDENTIFIED PENDING ACCEPTANCE/).length).toBeGreaterThan(0);
    expect(within(business).getByText(/BF_BF4Q is resolved as the direct/i)).toBeTruthy();

    const regional = screen.getByRole("heading", { name: "State-Level Payroll Growth Breadth" }).closest("section")!;
    expect(within(regional).getAllByText(/GOVERNED CALC METHOD APPROVED INPUT HISTORY PENDING/).length).toBeGreaterThan(0);
    expect(within(regional).getByText(/fixed 50-state-plus-DC method/i)).toBeTruthy();

    const gdp = screen.getByRole("heading", { name: "Real GDP Growth" }).closest("section")!;
    expect(within(gdp).getAllByText(/BLOCKED CREDENTIAL/).length).toBeGreaterThan(0);
    expect(within(gdp).getByText(/AUXSAYS_BEA_USER_ID is missing/)).toBeTruthy();
  });

  it("keeps causal, materiality, destination-impact, prediction, and fixture claims off child cards", () => {
    const { container } = render(<ContinuedClaimsLevel4QaView />);
    const cards = container.querySelector(".sm-l4qa-grid")?.textContent?.toLowerCase() ?? "";
    expect(cards).not.toContain("causality");
    expect(cards).not.toContain("materiality");
    expect(cards).not.toContain("destination impact");
    expect(cards).not.toContain("prediction");
    expect(cards).not.toContain("renderer fixture");
  });

  it("routes the compact pending Human QA surface through the shared shell", async () => {
    window.location.hash = "#continued-claims-level4-qa";
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByText("Continued Claims / Insured Unemployment · exact ten")).toBeTruthy();
    expect(await screen.findByText("LOCAL HUMAN QA — PENDING")).toBeTruthy();
  });
});
