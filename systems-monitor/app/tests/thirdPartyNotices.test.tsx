import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { THIRD_PARTY_NOTICES_URL } from "../src/shared/ThirdPartyNoticesLink";

// The published bundle carries no licence comments; the build serves the notices beside it at a fixed
// URL. Both shells a reader can reach in production must link to it: the persistent world (the default)
// and the classic shell (?view=..., #workstream1a).
describe("third-party software notices link", () => {
  it("points at the URL the build serves", () => {
    expect(THIRD_PARTY_NOTICES_URL).toBe("/systems-monitor/THIRD_PARTY_NOTICES.txt");
  });

  it("is in the persistent-world footer", async () => {
    window.history.replaceState({}, "", "/systems-monitor/#persistent-world");
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    const link = await screen.findByRole("link", { name: "Third-party software notices" });
    expect(link.getAttribute("href")).toBe(THIRD_PARTY_NOTICES_URL);
    expect(link.closest("footer")?.className).toBe("sm-immersive-footer");
  });

  it("is in the classic shell footer", async () => {
    window.history.replaceState({}, "", "/systems-monitor/?view=summary");
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    const link = await screen.findByRole("link", { name: "Third-party software notices" });
    expect(link.getAttribute("href")).toBe(THIRD_PARTY_NOTICES_URL);
    expect(link.closest("footer")?.className).toBe("sm-app-footer");
  });
});
