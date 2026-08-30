import { describe, expect, it } from "vitest";
import { phase2Fixture } from "../src/fixtures/phase2Fixture";
import { parseRoute, serializeRoute } from "../src/state/routeSchema";
import { createSnapshotViewModel } from "../src/data/snapshotViewModelFactory";

const fixtureView = createSnapshotViewModel(phase2Fixture);

describe("canonical Systems Monitor routing", () => {
  it("uses a clean canonical default", () => {
    const parsed = parseRoute("", fixtureView);
    expect(parsed.canonicalSearch).toBe("");
    expect(parsed.state.view).toBe("summary");
  });

  it("preserves valid deep links in canonical parameter order", () => {
    const path = "fixture-driver-1/fixture-factor-2";
    const parsed = parseRoute(`?range=fixture-5-period&path=${path}&system=fixture-system-1&view=outlook&horizon=next-year&scenario=fixture-scenario-alpha&geo=fixture-national`, fixtureView);
    expect(parsed.state.path).toEqual(path.split("/"));
    expect(parsed.state.horizon).toBe("next-year");
    expect([...new URLSearchParams(parsed.canonicalSearch).keys()]).toEqual(["view", "path", "horizon", "scenario"]);
  });

  it("truncates invalid hierarchy and removes view-incompatible state", () => {
    const parsed = parseRoute("?view=summary&path=fixture-driver-1/not-real&horizon=plus-3-years&scenario=not-real&unknown=yes", fixtureView);
    expect(parsed.state.path).toEqual(["fixture-driver-1"]);
    expect(parsed.canonicalSearch).toBe("?path=fixture-driver-1");
    expect(parsed.state.notice).toMatch(/truncated/);
    expect(parsed.state.notice).toMatch(/Outlook-only/);
    expect(parsed.state.notice).toMatch(/Unsupported URL/);
  });

  it("serializes Outlook state and omits defaults", () => {
    const parsed = parseRoute("?view=outlook", fixtureView);
    expect(serializeRoute({ ...parsed.state, horizon: "plus-3-years", scenario: "fixture-scenario-alpha" }, fixtureView)).toBe("?view=outlook&horizon=plus-3-years&scenario=fixture-scenario-alpha");
  });
});
