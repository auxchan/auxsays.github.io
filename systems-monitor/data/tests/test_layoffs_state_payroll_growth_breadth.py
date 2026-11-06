import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from _support import CONFIG
from systems_monitor_data.layoffs_ces_calibration import load_state_payroll_growth_breadth_calibration
from systems_monitor_data.layoffs_state_payroll_growth_breadth import (
    StatePayrollBreadthCandidate,
    StatePayrollBreadthUnavailable,
    StatePayrollInputObservation,
    calculate_state_payroll_growth_breadth,
    load_state_payroll_breadth_methodology,
)


class StatePayrollGrowthBreadthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.methodology = load_state_payroll_breadth_methodology(
            CONFIG / "layoffs" / "state_payroll_growth_breadth_methodology.json"
        )
        cls.calibration = load_state_payroll_growth_breadth_calibration(
            CONFIG / "layoffs" / "state_payroll_growth_breadth_calibration.json"
        )
        cls.members = tuple(cls.methodology["universe"]["members"])

    def inputs(self, period: str, values: tuple[str, ...], revision: str = "CURRENT_REVISED"):
        return tuple(
            StatePayrollInputObservation(
                observation_id=f"obs:{member['seriesId']}:{period}:{revision}",
                series_id=member["seriesId"],
                jurisdiction=member["postalCode"],
                valid_time=period,
                value=Decimal(value),
                source_revision_status=revision,
            )
            for member, value in zip(self.members, values, strict=True)
        )

    def test_exact_51_statewide_sa_total_nonfarm_universe(self):
        self.assertEqual(51, len(self.members))
        self.assertEqual(51, len({row["seriesId"] for row in self.members}))
        self.assertEqual(51, len({row["fips"] for row in self.members}))
        self.assertEqual(51, len({row["postalCode"] for row in self.members}))
        self.assertIn("DC", {row["postalCode"] for row in self.members})
        self.assertEqual(tuple(row["seriesId"] for row in self.members), tuple(self.calibration["selectors"]))
        for row in self.members:
            self.assertEqual(f"SMS{row['fips']}000000000000001", row["seriesId"])
        self.assertFalse(self.methodology["universe"]["metropolitanSeriesAllowed"])
        self.assertFalse(self.methodology["universe"]["mixedSeasonalAdjustmentAllowed"])

    def test_formula_uses_fixed_denominator_and_flat_is_not_growth(self):
        prior = self.inputs("2026-01", ("10",) * 51)
        current = self.inputs("2026-02", ("11",) * 25 + ("10",) * 26)
        result = calculate_state_payroll_growth_breadth(self.methodology, current, prior)
        self.assertIsInstance(result, StatePayrollBreadthCandidate)
        self.assertEqual(25, result.growing_member_count)
        self.assertEqual(51, result.denominator)
        self.assertEqual(Decimal("49.0196"), result.value)

        flat = calculate_state_payroll_growth_breadth(self.methodology, self.inputs("2026-02", ("10",) * 51), prior)
        self.assertIsInstance(flat, StatePayrollBreadthCandidate)
        self.assertEqual(0, flat.growing_member_count)
        self.assertEqual(Decimal("0.0000"), flat.value)

    def test_missing_input_never_shrinks_denominator(self):
        result = calculate_state_payroll_growth_breadth(
            self.methodology,
            self.inputs("2026-02", ("11",) * 51)[:-1],
            self.inputs("2026-01", ("10",) * 51),
        )
        self.assertIsInstance(result, StatePayrollBreadthUnavailable)
        self.assertIsNone(result.value)
        self.assertEqual((self.members[-1]["seriesId"],), result.missing_current_series)
        self.assertIn("INCOMPLETE_51_OF_51_COVERAGE", result.reasons)

    def test_non_statewide_mixed_adjustment_or_skipped_month_fails_closed(self):
        prior = self.inputs("2026-01", ("10",) * 51)
        metro = list(self.inputs("2026-02", ("11",) * 51))
        metro[0] = StatePayrollInputObservation(**{**metro[0].__dict__, "geography_scope": "METROPOLITAN"})
        result = calculate_state_payroll_growth_breadth(self.methodology, metro, prior)
        self.assertTrue(any("METROPOLITAN_OR_NON_STATEWIDE_INPUT" in reason for reason in result.reasons))

        nsa = list(self.inputs("2026-02", ("11",) * 51))
        nsa[0] = StatePayrollInputObservation(**{**nsa[0].__dict__, "seasonal_adjustment": "NOT_SEASONALLY_ADJUSTED"})
        result = calculate_state_payroll_growth_breadth(self.methodology, nsa, prior)
        self.assertTrue(any("SEASONALLY_INCOMPATIBLE_INPUT" in reason for reason in result.reasons))

        skipped = calculate_state_payroll_growth_breadth(self.methodology, self.inputs("2026-03", ("11",) * 51), prior)
        self.assertIn("INPUT_PERIODS_NOT_PREVIOUS_COMPATIBLE_MONTHS", skipped.reasons)

    def test_revisions_produce_new_immutable_candidate_identity(self):
        prior = self.inputs("2026-01", ("10",) * 51)
        first = calculate_state_payroll_growth_breadth(self.methodology, self.inputs("2026-02", ("11",) * 51, "FIRST_RELEASE"), prior)
        revised = calculate_state_payroll_growth_breadth(self.methodology, self.inputs("2026-02", ("11",) * 51, "REVISED"), prior)
        self.assertIsInstance(first, StatePayrollBreadthCandidate)
        self.assertIsInstance(revised, StatePayrollBreadthCandidate)
        self.assertNotEqual(first.observation_id, revised.observation_id)
        self.assertEqual(51, len(first.input_provenance))
        with self.assertRaises(FrozenInstanceError):
            first.value = Decimal("0")

    def test_calibration_is_complete_but_never_production_history(self):
        coverage = self.calibration["coverage"]
        self.assertEqual(120, coverage["monthlyPeriods"])
        self.assertEqual(120, coverage["complete51Of51Periods"])
        self.assertEqual(0, coverage["missingObservationsBySelector"])
        self.assertFalse(self.calibration["calibrationHistoryAcceptedForProduction"])
        state = self.methodology["productionState"]
        self.assertEqual(0, state["acceptedCesInputHistoryDepth"])
        self.assertEqual(0, state["calculatedHistoryDepth"])


if __name__ == "__main__":
    unittest.main()
