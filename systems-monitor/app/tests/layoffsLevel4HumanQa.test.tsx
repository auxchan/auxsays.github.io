import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LayoffsLevel4QaView } from "../src/views/layoffs-qa/LayoffsLevel4QaView";

describe("Layoffs Level-4 Human QA surface", () => {
  it("exposes the eight canonical factors and nine governed exact series", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    expect(container.querySelectorAll(".sm-l4qa-factor")).toHaveLength(8);
    expect(container.querySelectorAll(".sm-l4qa-series")).toHaveLength(9);
    for (const label of ["Layoffs and Discharges", "Job Openings Rate", "Hires Rate", "Permanent Job Losers", "Temporary Layoffs", "Average Weekly Hours", "Temporary Help Employment", "Initial Claims"]) {
      expect(screen.getByRole("heading", { name: label })).toBeTruthy();
    }
    expect(screen.getByText("188")).toBeTruthy();
    expect(container.querySelector(".sm-l4qa")?.getAttribute("data-human-qa")).toBe("PENDING");
  });

  it("separates stale current-source state from accepted Initial Claims history", () => {
    render(<LayoffsLevel4QaView />);
    const claims = screen.getByRole("heading", { name: "Initial Claims" }).closest("section")!;
    expect(within(claims).getByText("Current source state: STALE.")).toBeTruthy();
    expect(within(claims).getByText("ACCEPTED HISTORICAL DATA")).toBeTruthy();
    expect(within(claims).getAllByText("207,000 claims").length).toBeGreaterThan(0);
    expect(within(claims).getByText(/209,000 → 212,000 claims/)).toBeTruthy();
    expect(within(claims).getAllByText("2026-08-15").length).toBeGreaterThan(0);
  });

  it("keeps unauthorised analytical claims off the QA surface", () => {
    const { container } = render(<LayoffsLevel4QaView />);
    const text = container.textContent?.toLowerCase() ?? "";
    expect(text).not.toContain("materiality");
    expect(text).not.toContain("supportive");
    expect(text).not.toContain("adverse");
    expect(text).not.toContain("causality");
    expect(text).not.toContain("forecast");
    expect(text).not.toContain("prediction");
  });
});
