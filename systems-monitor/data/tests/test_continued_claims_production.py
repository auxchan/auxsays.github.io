import json
import unittest

from _support import CONFIG, PACKAGE_ROOT


LAYOFFS = CONFIG / "layoffs"


def load(name: str):
    return json.loads((LAYOFFS / name).read_text(encoding="utf-8"))


class ContinuedClaimsProductionTests(unittest.TestCase):
    def test_parent_resolves_to_two_separate_direct_observations(self):
        production = load("continued_claims_production.json")
        observations = production["parentObservations"]
        self.assertEqual("Continued Claims / Insured Unemployment", production["parentLabel"])
        self.assertEqual("TWO_SEPARATELY_LABELED_DIRECT_OBSERVATIONS", production["parentIdentityResolution"])
        self.assertEqual(2, len(observations))
        self.assertEqual(
            [("DOL-UI-SA-CONTINUED", "ContinuedClaims/SA", "claims"), ("DOL-UI-SA-IUR", "IUR/SA", "percent")],
            [(row["selector"], row["xmlPath"], row["unit"]) for row in observations],
        )
        self.assertTrue(all(row["frequency"] == "weekly" for row in observations))
        self.assertTrue(all(row["geography"] == "United States" for row in observations))
        self.assertTrue(all(row["seasonalAdjustment"] == "seasonally adjusted" for row in observations))
        self.assertTrue(all(row["productionDisposition"] == "SOURCE_ENABLED_PENDING_ACCEPTANCE" for row in observations))
        self.assertTrue(all(row["acceptedHistoryRecords"] == 0 for row in observations))

        source_registry = load("sources_bls_dol.json")
        source_rows = {row["series_id"]: row for row in source_registry["series"]}
        for row in observations:
            source = source_rows[row["selector"]]
            self.assertEqual(row["unit"], source["unit"])
            self.assertEqual(row["frequency"], source["frequency"])
            self.assertEqual(row["seasonalAdjustment"], source["seasonal_adjustment"])
            self.assertEqual(row["xmlPath"], source["xml_path"])

        roles = load("level4_source_profile_roles.json")
        parent = next(row for row in roles["factorSourceStateRecords"] if row["canonicalFactorId"] == production["parentPlacementId"].replace("placement:layoffs-job-destruction:", "factor:canonical:"))
        self.assertEqual(["PRIMARY_OBSERVATION_SOURCE", "PRIMARY_OBSERVATION_SOURCE"], [row["role"] for row in parent["sourceBindings"]])

    def test_exact_ten_matches_frozen_taxonomy_and_governance(self):
        production = load("continued_claims_production.json")
        taxonomy = load("taxonomy.json")
        group = next(row for row in taxonomy["groups"] if row["id"] == "continued-claims-insured-unemployment")
        self.assertEqual(10, len(production["placements"]))
        self.assertEqual(
            [(row["label"], row["canonicalFactorId"], row["placementId"]) for row in group["placements"]],
            [(row["label"], row["canonicalFactorId"], row["placementId"]) for row in production["placements"]],
        )
        self.assertEqual("PRODUCTION_COMPLETE_GOVERNED_LEVEL4_EXACT_TEN", production["governanceState"])
        self.assertEqual("READY_FOR_HUMAN_LEVEL4_CONTINUED_CLAIMS_QA", production["reviewState"])
        self.assertEqual("PENDING", production["humanQa"])
        self.assertEqual("FROZEN_EXCEPT_FOR_VERIFIED_DEFECTS", production["frameworkState"])
        self.assertEqual(0, production["unexplainedRendererFixtures"])
        self.assertEqual(0, production["acceptedStructuralRelationships"])
        self.assertEqual("OPEN", production["gateB"])
        self.assertEqual(0, production["forecastVintageObservations"])
        self.assertEqual("UNAUTHORIZED", production["materiality"])
        self.assertEqual("UNAVAILABLE", production["destinationImpact"])
        self.assertEqual("LOCKED", production["phase5"])
        self.assertEqual("LOCKED_UNAVAILABLE", production["forecasting"])

        review = load("level4_p0_review_status.json")
        self.assertEqual("PENDING", review["humanQa"]["HUMAN_LEVEL4_CONTINUED_CLAIMS_QA"])
        self.assertEqual("PRODUCTION_COMPLETE_GOVERNED_LEVEL4_EXACT_TEN", review["continuedClaims"]["status"])
        self.assertEqual(114, review["continuedClaims"]["acceptedHistoryReuseRecords"])
        self.assertEqual("PASS", review["humanQa"]["HUMAN_LEVEL4_INITIAL_UI_CLAIMS_QA"])

    def test_five_factors_reuse_exactly_114_existing_records_without_copying(self):
        production = load("continued_claims_production.json")
        accepted_history = json.loads((PACKAGE_ROOT / "review" / "layoffs-accepted-history.json").read_text(encoding="utf-8"))
        accepted_rows = [row for row in production["placements"] if row["productionDisposition"] == "ACCEPTED_OBSERVATION"]
        self.assertEqual(5, len(accepted_rows))
        actual_counts = {
            row["canonicalFactorId"]: sum(1 for observation in accepted_history["observations"] if observation["canonicalFactorId"] == row["canonicalFactorId"])
            for row in accepted_rows
        }
        self.assertEqual(
            {
                "factor:canonical:initial-claims": 36,
                "factor:canonical:hires-rate": 19,
                "factor:canonical:job-openings-rate": 19,
                "factor:canonical:temporary-help-employment": 20,
                "factor:canonical:average-weekly-hours": 20,
            },
            actual_counts,
        )
        self.assertEqual(114, sum(actual_counts.values()))
        self.assertEqual(114, production["acceptedHistoryReuseRecords"])
        self.assertNotIn("observations", production)

    def test_pending_children_are_truthfully_bounded(self):
        rows = {row["canonicalFactorId"]: row for row in load("continued_claims_production.json")["placements"]}
        payroll = rows["factor:canonical:total-nonfarm-payroll-change"]
        self.assertEqual("GOVERNED_CALC_METHOD_APPROVED_INPUT_HISTORY_PENDING", payroll["productionDisposition"])
        self.assertEqual(["CES0000000001", "PAYROLL_CHANGE_V1"], payroll["selectors"])
        self.assertIsNone(payroll["recommendation"])
        business = rows["factor:canonical:business-formations-within-4-quarters"]
        self.assertEqual("A_DIRECT_OBS", business["claimClass"])
        self.assertEqual("SOURCE_IDENTIFIED_PENDING_ACCEPTANCE", business["productionDisposition"])
        self.assertEqual(["BFS:T:BF_BF4Q:SA"], business["selectors"])
        self.assertNotIn("projected", business["blocker"].lower())
        breadth = rows["factor:canonical:state-level-payroll-growth-breadth"]
        self.assertEqual("GOVERNED_CALC_METHOD_APPROVED_INPUT_HISTORY_PENDING", breadth["productionDisposition"])
        self.assertEqual(["bls-ces-state-and-metro"], breadth["sourceIds"])
        self.assertEqual(["CES_STATE_TOTAL_NONFARM_V1", "STATE_PAYROLL_GROWTH_BREADTH_V1"], breadth["selectors"])
        self.assertEqual("BLOCKED_CREDENTIAL", rows["factor:canonical:real-gdp-growth"]["productionDisposition"])
        self.assertEqual("BLOCKED_CREDENTIAL", rows["factor:canonical:real-personal-consumption-expenditures-growth"]["productionDisposition"])
        self.assertTrue(all(row["blocker"] for row in rows.values() if row["productionDisposition"] != "ACCEPTED_OBSERVATION"))

    def test_exact_ten_corrections_do_not_promote_values_or_change_boundaries(self):
        production = load("continued_claims_production.json")
        self.assertEqual(
            [
                "Initial Claims", "Hires Rate", "Job Openings Rate", "Total Nonfarm Payroll Change",
                "Temporary Help Employment", "Average Weekly Hours", "Business Formations Within 4 Quarters",
                "Real GDP Growth", "Real Personal Consumption Expenditures Growth", "State-Level Payroll Growth Breadth",
            ],
            [row["label"] for row in production["placements"]],
        )
        self.assertEqual(0, production["forecastVintageObservations"])
        self.assertEqual(0, production["acceptedStructuralRelationships"])
        self.assertEqual(0, production["unexplainedRendererFixtures"])
        self.assertEqual("PENDING", production["humanQa"])


if __name__ == "__main__":
    unittest.main()
