import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LayoffsLevel4QaView } from "../src/views/layoffs-qa/LayoffsLevel4QaView";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { SnapshotProvider } from "../src/app/SnapshotContext";

describe("Layoffs Level-4 Human QA surface", () => {
  it("exposes the twelve canonical factors and thirteen governed exact series", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    expect(container.querySelectorAll(".sm-l4qa-factor")).toHaveLength(12);
    expect(container.querySelectorAll(".sm-l4qa-series")).toHaveLength(13);
    for (const label of ["Layoffs and Discharges", "Job Openings Rate", "Hires Rate", "Permanent Job Losers", "Temporary Layoffs", "Average Weekly Hours", "Temporary Help Employment", "Gross Job Losses", "Establishment Contractions", "Establishment Closures", "Establishment Deaths", "Initial Claims"]) {
      expect(screen.getByRole("heading", { name: label })).toBeTruthy();
    }
    expect(screen.getByText("203")).toBeTruthy();
    expect(container.querySelector(".sm-l4qa")?.getAttribute("data-human-qa")).toBe("PENDING");
  });

  it("separates stale primary XML health from current official fallback evidence", () => {
    render(<LayoffsLevel4QaView />);
    const claims = screen.getByRole("heading", { name: "Initial Claims" }).closest("section")!;
    expect(within(claims).getByText(/Primary XML: STALE through 2026-08-15/)).toBeTruthy();
    expect(within(claims).getByText("CURRENT · OFFICIAL FALLBACK")).toBeTruthy();
    expect(within(claims).getAllByText("206,000 claims").length).toBeGreaterThan(0);
    expect(within(claims).getByText(/209,000 claims → 212,000 claims/)).toBeTruthy();
    expect(within(claims).getAllByText("2026-09-05").length).toBeGreaterThan(0);
  });

  it("keeps unauthorized analytical claims off the factual QA surface", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    const text = container.textContent?.toLowerCase() ?? "";
    expect(text).not.toContain("materiality");
    expect(text).not.toContain("destination impact");
    expect(text).not.toContain("supportive");
    expect(text).not.toContain("adverse");
    expect(text).not.toContain("causality");
    expect(text).not.toContain("forecast");
    expect(text).not.toContain("prediction");
  });

  it("uses precise history, latest-value, rate, unit, and placement semantics", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    const text = container.textContent ?? "";
    expect(text).not.toContain("Current accepted value");
    expect(text).not.toContain("comparable periods");
    expect(screen.getAllByText("Latest accepted value")).toHaveLength(13);

    const deaths = screen.getByRole("heading", { name: "Establishment Deaths" }).closest("section")!;
    expect(within(deaths).getByText("Accepted history · 1 period")).toBeTruthy();
    expect(within(deaths).getByText("Not yet available")).toBeTruthy();

    const openings = screen.getByRole("heading", { name: "Job Openings Rate" }).closest("section")!;
    expect(within(openings).getByText("+0.1 pp")).toBeTruthy();
    expect(within(openings).queryByText(/\+2\.33%/)).toBeNull();

    const grossLosses = screen.getByRole("heading", { name: "Gross Job Losses" }).closest("section")!;
    expect(within(grossLosses).getAllByText(/7,245,000 jobs/).length).toBeGreaterThan(0);

    const hours = screen.getByRole("heading", { name: "Average Weekly Hours" }).closest("section")!;
    expect(within(hours).getByText("Appears in 3 Layoffs pathways")).toBeTruthy();
    expect(within(hours).getByText("Layoffs & Job Destruction › Layoffs & Discharges › Average Weekly Hours")).toBeTruthy();
    expect(within(hours).getByText("Layoffs & Job Destruction › Continued Claims / Insured Unemployment › Average Weekly Hours")).toBeTruthy();
    expect(within(hours).getByText("Layoffs & Job Destruction › Temporary Layoffs › Average Weekly Hours")).toBeTruthy();
    expect(within(hours).getByText("Source-native unit")).toBeTruthy();
  });

  it("shows the repaired twelve-factor count in the shared QA shell", async () => {
    window.location.hash = "#layoffs-level4-qa";
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByText("12 factors")).toBeTruthy();
    expect(screen.queryByText("8 factors")).toBeNull();
  });
});
