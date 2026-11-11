import unittest

from _support import CONFIG
from systems_monitor_data.layoffs_ces_calibration import (
    load_payroll_breadth_calibration,
    simulate_coverage,
)


class LayoffsCesCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_payroll_breadth_calibration(
            CONFIG / "layoffs" / "payroll_contraction_breadth_calibration.json"
        )

    def test_two_nonoverlapping_options_remain_calibration_only(self):
        self.assertEqual([10, 21], [len(option["members"]) for option in self.document["options"]])
        self.assertEqual("OPTION_A", self.document["recommendation"]["universe"])
        self.assertEqual(95, self.document["recommendation"]["minimumPublishableCoveragePercent"])
        self.assertEqual("REJECTED_SUPERSEDED_BY_TAYLOR_DECISION_2026_10_01", self.document["recommendation"]["authorization"])
        self.assertEqual("OPTION_A", self.document["decision"]["approvedUniverse"])
        self.assertEqual(100, self.document["decision"]["requiredCoveragePercent"])
        self.assertFalse(self.document["decision"]["calibrationHistoryAcceptedForProduction"])
        self.assertTrue(all(option["coverage"]["at100Percent"] == 100.0 for option in self.document["options"]))

    def test_coverage_simulation_reports_thresholds_and_missing_patterns(self):
        response = {
            "status": "REQUEST_SUCCEEDED",
            "Results": {"series": [
                {"seriesID": "CES1000000001", "data": [
                    {"year": "2025", "period": "M03", "value": "1"},
                    {"year": "2025", "period": "M02", "value": "1"},
                    {"year": "2025", "period": "M01", "value": "1"},
                ]},
                {"seriesID": "CES2000000001", "data": [
                    {"year": "2025", "period": "M03", "value": "2"},
                    {"year": "2025", "period": "M01", "value": "2"},
                ]},
            ]},
        }
        result = simulate_coverage([response], ["CES1000000001", "CES2000000001"])
        self.assertEqual(3, result["periods"])
        self.assertEqual(66.6667, result["at100Percent"])
        self.assertEqual(1, result["missingBySeries"]["CES2000000001"])

    def test_exact_universe_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exact universe"):
            simulate_coverage([{"status": "REQUEST_SUCCEEDED", "Results": {"series": []}}], ["CES1000000001"])


if __name__ == "__main__":
    unittest.main()
