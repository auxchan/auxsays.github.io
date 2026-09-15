import { describe, expect, it } from "vitest";
import {
  acceptedLayoffsHistoryForFactor,
  layoffsAcceptedFactorSummaries,
  LAYOFFS_ACCEPTED_COMPARABLE_FACTOR_COUNT,
  LAYOFFS_ACCEPTED_COMPARABLE_SERIES_COUNT,
  LAYOFFS_ACCEPTED_OBSERVATION_COUNT,
  LAYOFFS_DOL_SOURCE_FRESHNESS,
  LAYOFFS_DOL_PRIMARY_FRESHNESS,
  displayAcceptedLayoffsValue,
} from "../src/data/layoffsAcceptedHistoryReadModel";
import { persistentWorldFactualBindingForFactor } from "../src/data/persistentWorldFactualBindings";
import { persistentChangeNotices } from "../src/data/persistentWorldTemporalReadModel";

describe("Taylor-authorized Layoffs accepted history", () => {
  it("exposes only the exact accepted descriptive-history scope", () => {
    expect(LAYOFFS_ACCEPTED_OBSERVATION_COUNT).toBe(203);
    expect(LAYOFFS_ACCEPTED_COMPARABLE_FACTOR_COUNT).toBe(11);
    expect(LAYOFFS_ACCEPTED_COMPARABLE_SERIES_COUNT).toBe(12);
    expect(new Set(layoffsAcceptedFactorSummaries.map((row) => row.canonicalFactorId))).toEqual(new Set([
      "factor:canonical:layoffs-and-discharges",
      "factor:canonical:job-openings-rate",
      "factor:canonical:hires-rate",
      "factor:canonical:permanent-job-losers",
      "factor:canonical:temporary-layoffs",
      "factor:canonical:average-weekly-hours",
      "factor:canonical:temporary-help-employment",
      "factor:canonical:gross-job-losses",
      "factor:canonical:establishment-contractions",
      "factor:canonical:establishment-closures",
      "factor:canonical:establishment-deaths",
      "factor:canonical:initial-claims",
    ]));
    for (const factor of layoffsAcceptedFactorSummaries) {
      for (const series of factor.series) {
        expect(series.materialityStatus).toBe("UNKNOWN");
        expect(series.impactStatus).toBe("UNKNOWN");
        expect(series.forecastVintageEligible).toBe(false);
        expect(series.current.historyUseClass).toBe("CURRENT_REVISED_HISTORY");
      }
    }
  });

  it("preserves the accepted 209,000 seed and the later 212,000 revision", () => {
    const claims = acceptedLayoffsHistoryForFactor("factor:canonical:initial-claims")!;
    expect(claims.primary.current.value).toBe("206000");
    expect(claims.primary.current.validTime).toBe("2026-09-05");
    expect(claims.primary.revisions).toHaveLength(1);
    expect(claims.primary.revisions[0].previous.value).toBe("209000");
    expect(claims.primary.revisions[0].current.value).toBe("212000");
    expect(claims.primary.revisions[0].current.revisionNumber).toBe(1);
    expect(LAYOFFS_DOL_SOURCE_FRESHNESS.status).toBe("CURRENT");
    expect(LAYOFFS_DOL_PRIMARY_FRESHNESS.status).toBe("STALE");
  });

  it("wires accepted comparable history into Level-4 readings without creating impact", () => {
    const binding = persistentWorldFactualBindingForFactor("factor:canonical:average-weekly-hours", "Average Weekly Hours");
    expect(binding).toMatchObject({ status: "CONNECTED", seriesId: "CES0500000002", displayValue: "34.4 hours" });
    expect(binding.temporalHistory?.primary.previous?.validTime).toBe("2026-07");
    const historyNotices = persistentChangeNotices.filter((notice) => notice.id.startsWith("accepted-history:"));
    expect(historyNotices).toHaveLength(12);
    expect(historyNotices.every((notice) => notice.impactClass === "UNKNOWN" && notice.economicSignalEligible === false)).toBe(true);
  });

  it("presents source-scaled counts in human units while preserving exact values", () => {
    expect(displayAcceptedLayoffsValue("1666", "thousands of persons")).toBe("1,666,000 people");
    expect(displayAcceptedLayoffsValue("2519.5", "thousands of persons")).toBe("2,519,500 people");
    expect(displayAcceptedLayoffsValue("7245", "thousands of jobs")).toBe("7,245,000 jobs");
    expect(displayAcceptedLayoffsValue("4.4", "percent")).toBe("4.4%");
  });
});
