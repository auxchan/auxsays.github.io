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
    expect(LAYOFFS_ACCEPTED_OBSERVATION_COUNT).toBeGreaterThanOrEqual(203);
    expect(LAYOFFS_ACCEPTED_COMPARABLE_FACTOR_COUNT).toBe(17);
    expect(LAYOFFS_ACCEPTED_COMPARABLE_SERIES_COUNT).toBe(18);
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
      "factor:canonical:jobs-lost-at-establishment-deaths",
      "factor:canonical:initial-claims",
      "factor:canonical:total-nonfarm-payroll-employment",
      "factor:canonical:u3-unemployment-rate",
      "factor:canonical:labor-force-participation-rate",
      "factor:canonical:job-openings-level",
      "factor:canonical:hires-level",
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

  it("keeps accepted establishment-death history addressable through the legacy canonical alias", () => {
    const legacy = acceptedLayoffsHistoryForFactor("factor:canonical:establishment-deaths");
    const canonical = acceptedLayoffsHistoryForFactor("factor:canonical:jobs-lost-at-establishment-deaths");
    expect(legacy).toBe(canonical);
    expect(canonical?.primary.sourceSeriesId).toBe("BDS0000000000000000110008LQ5");
  });

  it("keeps the current official claims period while preserving the accepted 209,000 to 212,000 revision chain", () => {
    const claims = acceptedLayoffsHistoryForFactor("factor:canonical:initial-claims")!;
    expect(claims.primary.current.validTime).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(Number(claims.primary.current.value)).toBeGreaterThan(0);
    const seedRevision = claims.primary.revisions.find((revision) => revision.previous.value === "209000" && revision.current.value === "212000");
    expect(seedRevision?.current.revisionNumber).toBe(1);
    expect(LAYOFFS_DOL_SOURCE_FRESHNESS.status).toBe("CURRENT");
    expect(LAYOFFS_DOL_PRIMARY_FRESHNESS.status).toBe("STALE");
  });

  it("wires accepted comparable history into Level-4 readings without creating impact", () => {
    const binding = persistentWorldFactualBindingForFactor("factor:canonical:average-weekly-hours", "Average Weekly Hours");
    expect(binding).toMatchObject({ status: "CONNECTED", seriesId: "CES0500000002", displayValue: "34.4 hours" });
    expect((binding.temporalHistory?.primary.previous?.validTime ?? "") < binding.temporalHistory!.primary.current.validTime).toBe(true);
    const historyNotices = persistentChangeNotices.filter((notice) => notice.id.startsWith("accepted-history:"));
    expect(historyNotices.length).toBeGreaterThanOrEqual(12);
    expect(historyNotices.every((notice) => notice.impactClass === "UNKNOWN" && notice.economicSignalEligible === false)).toBe(true);
  });

  it("presents source-scaled counts in human units while preserving exact values", () => {
    expect(displayAcceptedLayoffsValue("1666", "thousands of persons")).toBe("1,666,000 people");
    expect(displayAcceptedLayoffsValue("2519.5", "thousands of persons")).toBe("2,519,500 people");
    expect(displayAcceptedLayoffsValue("7245", "thousands of jobs")).toBe("7,245,000 jobs");
    expect(displayAcceptedLayoffsValue("4.4", "percent")).toBe("4.4%");
  });
});
