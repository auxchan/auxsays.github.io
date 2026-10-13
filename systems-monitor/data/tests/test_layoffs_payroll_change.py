import json
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from _support import CONFIG
from systems_monitor_data.layoffs_payroll_change import (
    PayrollChangeCandidate,
    PayrollChangeUnavailable,
    PayrollLevelObservation,
    calculate_total_nonfarm_payroll_change,
    load_payroll_change_methodology,
)


class TotalNonfarmPayrollChangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.methodology = load_payroll_change_methodology(
            CONFIG / "layoffs" / "total_nonfarm_payroll_change_methodology.json"
        )

    @staticmethod
    def observation(period: str, value: str, revision: str = "CURRENT_REVISED", **overrides):
        values = {
            "observation_id": f"obs:CES0000000001:{period}:{revision}",
            "valid_time": period,
            "value": Decimal(value),
            "source_revision_status": revision,
        }
        values.update(overrides)
        return PayrollLevelObservation(**values)

    def test_exact_selector_and_metadata_match_authoritative_registry(self):
        indicators = json.loads((CONFIG / "indicators" / "indicators.json").read_text(encoding="utf-8"))["indicators"]
        registry = json.loads((CONFIG / "layoffs" / "sources_bls_dol.json").read_text(encoding="utf-8"))["series"]
        indicator = next(row for row in indicators if row["source_series_id"] == "CES0000000001")
        source = next(row for row in registry if row["series_id"] == "CES0000000001")
        self.assertEqual("US_LABOR_TOTAL_NONFARM_PAYROLLS", indicator["indicator_id"])
        self.assertEqual("Total nonfarm payroll employment", source["label"])
        self.assertEqual("thousands of persons", indicator["unit"])
        self.assertEqual("monthly", indicator["frequency"])
        self.assertEqual("seasonally adjusted", indicator["seasonal_adjustment"])
        self.assertEqual("two monthly revisions plus annual benchmark", indicator["revision_behavior"])
        self.assertEqual("CES0000000001", self.methodology["inputContract"]["seriesId"])

    def test_formula_is_level_difference_in_thousands_of_jobs(self):
        result = calculate_total_nonfarm_payroll_change(
            self.methodology,
            self.observation("2026-02", "160250"),
            self.observation("2026-01", "160000"),
        )
        self.assertIsInstance(result, PayrollChangeCandidate)
        self.assertEqual(Decimal("250"), result.value)
        self.assertEqual("thousands of jobs", result.unit)
        self.assertEqual("PAYROLL_CHANGE_V1", result.methodology_version)
        self.assertFalse(result.forecast_vintage_eligible)

    def test_missing_unaccepted_or_incompatible_inputs_suppress_value(self):
        missing = calculate_total_nonfarm_payroll_change(self.methodology, None, self.observation("2026-01", "10"))
        self.assertIsInstance(missing, PayrollChangeUnavailable)
        self.assertIsNone(missing.value)
        self.assertIn("CURRENT_INPUT_MISSING", missing.reasons)

        unaccepted = calculate_total_nonfarm_payroll_change(
            self.methodology,
            self.observation("2026-02", "11", acceptance_state="CANDIDATE"),
            self.observation("2026-01", "10"),
        )
        self.assertIn("CURRENT_INPUT_NOT_ACCEPTED", unaccepted.reasons)

        wrong_period = calculate_total_nonfarm_payroll_change(
            self.methodology,
            self.observation("2026-03", "11"),
            self.observation("2026-01", "10"),
        )
        self.assertIn("INPUT_PERIODS_NOT_PREVIOUS_COMPATIBLE_MONTHS", wrong_period.reasons)

        mixed_adjustment = calculate_total_nonfarm_payroll_change(
            self.methodology,
            self.observation("2026-02", "11", seasonal_adjustment="NOT_SEASONALLY_ADJUSTED"),
            self.observation("2026-01", "10"),
        )
        self.assertIn("CURRENT_SEASONALLY_INCOMPATIBLE_INPUT", mixed_adjustment.reasons)
        self.assertIn("INPUT_SEASONAL_ADJUSTMENT_MISMATCH", mixed_adjustment.reasons)

    def test_revisions_produce_new_immutable_candidate_identity(self):
        prior = self.observation("2026-01", "160000")
        original = calculate_total_nonfarm_payroll_change(
            self.methodology, self.observation("2026-02", "160250", "FIRST_RELEASE"), prior
        )
        revised = calculate_total_nonfarm_payroll_change(
            self.methodology, self.observation("2026-02", "160245", "REVISED"), prior
        )
        self.assertIsInstance(original, PayrollChangeCandidate)
        self.assertIsInstance(revised, PayrollChangeCandidate)
        self.assertNotEqual(original.observation_id, revised.observation_id)
        self.assertEqual("FIRST_RELEASE", original.current_revision_state)
        self.assertEqual("REVISED", revised.current_revision_state)
        with self.assertRaises(FrozenInstanceError):
            original.value = Decimal("0")

    def test_prohibited_transformations_and_production_history_remain_off(self):
        rules = self.methodology["calculationRules"]
        self.assertTrue(all(rules[field] is False for field in (
            "percentChangeAllowed", "annualizationAllowed", "smoothingAllowed", "interpolationAllowed", "carryForwardAllowed"
        )))
        state = self.methodology["productionState"]
        self.assertEqual(0, state["acceptedInputHistoryDepth"])
        self.assertEqual(0, state["calculatedHistoryDepth"])
        self.assertIsNone(state["latestAcceptedValue"])


if __name__ == "__main__":
    unittest.main()
