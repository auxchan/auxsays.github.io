import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from _support import CONFIG
from systems_monitor_data.layoffs_payroll_contraction_breadth import (
    CesInputObservation,
    PayrollBreadthCandidate,
    PayrollBreadthUnavailable,
    calculate_payroll_contraction_breadth,
    load_payroll_breadth_methodology,
)


EXPECTED_SELECTORS = (
    "CES1000000001",
    "CES2000000001",
    "CES3000000001",
    "CES4000000001",
    "CES5000000001",
    "CES5500000001",
    "CES6000000001",
    "CES6500000001",
    "CES7000000001",
    "CES8000000001",
)


class PayrollContractionBreadthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.methodology = load_payroll_breadth_methodology(
            CONFIG / "layoffs" / "payroll_contraction_breadth_methodology.json"
        )

    def inputs(self, period: str, values: tuple[str, ...], revision: str = "CURRENT_REVISED"):
        return tuple(
            CesInputObservation(
                observation_id=f"obs:{series_id}:{period}:{revision}",
                series_id=series_id,
                valid_time=period,
                value=Decimal(value),
                source_revision_status=revision,
            )
            for series_id, value in zip(EXPECTED_SELECTORS, values, strict=True)
        )

    def test_exact_ten_selector_metadata_and_mutual_exclusion(self):
        universe = self.methodology["universe"]
        members = universe["members"]
        self.assertEqual(EXPECTED_SELECTORS, tuple(member["seriesId"] for member in members))
        self.assertEqual(10, len({member["exclusivePartition"] for member in members}))
        self.assertTrue(universe["mutuallyExclusive"])
        self.assertTrue(universe["nonOverlapping"])
        self.assertFalse(universe["mixedParentChildAggregates"])
        for member in members:
            self.assertEqual("US_NATIONAL", member["geography"])
            self.assertEqual("PRIVATE_INDUSTRY", member["industryScope"])
            self.assertEqual("ALL_EMPLOYEES_THOUSANDS", member["measure"])
            self.assertEqual("SEASONALLY_ADJUSTED", member["seasonalAdjustment"])

    def test_formula_uses_fixed_denominator_and_flat_is_not_contraction(self):
        prior = self.inputs("2026-01", ("10",) * 10)
        current = self.inputs("2026-02", ("9", "9", "9", "9", "10", "10", "11", "11", "11", "11"))
        result = calculate_payroll_contraction_breadth(self.methodology, current, prior)
        self.assertIsInstance(result, PayrollBreadthCandidate)
        self.assertEqual(Decimal("40"), result.value)
        self.assertEqual(4, result.contracted_member_count)
        self.assertEqual(10, result.denominator)
        self.assertEqual("40% of tracked private-industry supersectors contracted payrolls from the previous month.", result.public_statement)

    def test_zero_change_is_not_contraction(self):
        prior = self.inputs("2026-01", ("10",) * 10)
        current = self.inputs("2026-02", ("10",) * 10)
        result = calculate_payroll_contraction_breadth(self.methodology, current, prior)
        self.assertIsInstance(result, PayrollBreadthCandidate)
        self.assertEqual(Decimal("0"), result.value)

    def test_missing_input_suppresses_value_at_nine_of_ten(self):
        prior = self.inputs("2026-01", ("10",) * 10)
        current = self.inputs("2026-02", ("9",) * 10)[:-1]
        result = calculate_payroll_contraction_breadth(self.methodology, current, prior)
        self.assertIsInstance(result, PayrollBreadthUnavailable)
        self.assertIsNone(result.value)
        self.assertEqual(("CES8000000001",), result.missing_current_series)
        self.assertIn("INCOMPLETE_10_OF_10_COVERAGE", result.reasons)

    def test_incompatible_period_or_seasonality_suppresses_value(self):
        prior = self.inputs("2026-01", ("10",) * 10)
        skipped_month = self.inputs("2026-03", ("9",) * 10)
        result = calculate_payroll_contraction_breadth(self.methodology, skipped_month, prior)
        self.assertIsInstance(result, PayrollBreadthUnavailable)
        self.assertIn("INPUT_PERIODS_NOT_PREVIOUS_COMPATIBLE_MONTHS", result.reasons)
        incompatible = list(self.inputs("2026-02", ("9",) * 10))
        incompatible[0] = CesInputObservation(
            **{**incompatible[0].__dict__, "seasonal_adjustment": "NOT_SEASONALLY_ADJUSTED"}
        )
        result = calculate_payroll_contraction_breadth(self.methodology, incompatible, prior)
        self.assertIsInstance(result, PayrollBreadthUnavailable)
        self.assertIn("CES1000000001:SEASONALLY_INCOMPATIBLE_INPUT", result.reasons)

        unaccepted = list(self.inputs("2026-02", ("9",) * 10))
        unaccepted[0] = CesInputObservation(
            **{**unaccepted[0].__dict__, "acceptance_state": "CANDIDATE"}
        )
        result = calculate_payroll_contraction_breadth(self.methodology, unaccepted, prior)
        self.assertIsInstance(result, PayrollBreadthUnavailable)
        self.assertIn("CES1000000001:INPUT_NOT_ACCEPTED", result.reasons)

    def test_provenance_history_class_and_forecast_boundary(self):
        prior = self.inputs("2026-01", ("10",) * 10)
        current = self.inputs("2026-02", ("9",) * 10)
        result = calculate_payroll_contraction_breadth(self.methodology, current, prior)
        self.assertIsInstance(result, PayrollBreadthCandidate)
        self.assertEqual("PAYROLL_CONTRACTION_BREADTH_V1", result.methodology_version)
        self.assertEqual("CES_PRIVATE_SUPERSECTORS_V1", result.universe_version)
        self.assertEqual(10, len(result.input_provenance))
        self.assertEqual(EXPECTED_SELECTORS, tuple(row.series_id for row in result.input_provenance))
        self.assertTrue(all(row.current_observation_id and row.prior_observation_id for row in result.input_provenance))
        self.assertTrue(all(row.current_value == "9" and row.prior_value == "10" for row in result.input_provenance))
        self.assertEqual("CURRENT_REVISED_HISTORY", result.history_class)
        self.assertFalse(result.forecast_vintage_eligible)

    def test_revision_yields_new_immutable_candidate_identity(self):
        prior = self.inputs("2026-01", ("10",) * 10)
        original = calculate_payroll_contraction_breadth(
            self.methodology, self.inputs("2026-02", ("9",) * 10, "FIRST_RELEASE"), prior
        )
        revised = calculate_payroll_contraction_breadth(
            self.methodology, self.inputs("2026-02", ("9",) * 10, "REVISED"), prior
        )
        self.assertIsInstance(original, PayrollBreadthCandidate)
        self.assertIsInstance(revised, PayrollBreadthCandidate)
        self.assertNotEqual(original.observation_id, revised.observation_id)
        self.assertEqual("FIRST_RELEASE", original.input_provenance[0].current_revision_state)
        self.assertEqual("REVISED", revised.input_provenance[0].current_revision_state)
        with self.assertRaises(FrozenInstanceError):
            original.value = Decimal("0")

    def test_calibration_history_is_not_production_history(self):
        state = self.methodology["productionState"]
        self.assertEqual(0, state["acceptedCesInputSeries"])
        self.assertEqual(0, state["acceptedCesInputHistoryDepth"])
        self.assertEqual(0, state["calculatedHistoryDepth"])
        self.assertIsNone(state["latestAcceptedValue"])
        self.assertIsNone(state["latestAcceptedPeriod"])
        self.assertEqual("CALIBRATION_ONLY_NOT_ACCEPTED_NOT_PUBLISHABLE", self.methodology["calibrationEvidence"]["productionHistoryStatus"])


if __name__ == "__main__":
    unittest.main()
