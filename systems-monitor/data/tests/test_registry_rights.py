import copy
import json
import unittest

from _support import CONFIG
from systems_monitor_data.registry import EXPECTED_INDICATORS, EXPECTED_SOURCES, Registry
from systems_monitor_data.rights import RightsDenied, RightsEngine


class RegistryRightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry(CONFIG)
        cls.engine = RightsEngine(cls.registry.rights)

    def test_exact_enabled_sources(self):
        self.assertEqual(EXPECTED_SOURCES, {s["source_id"] for s in self.registry.sources if s["enabled"]})

    def test_exact_eight_indicators(self):
        self.assertEqual(EXPECTED_INDICATORS, {i["indicator_id"] for i in self.registry.indicators})

    def test_exact_six_enabled(self):
        self.assertEqual(6, len(self.registry.enabled_indicators()))

    def test_cpi_gdp_disabled(self):
        self.assertEqual({"US_PRICES_CPI_U_ALL_ITEMS", "US_OUTPUT_REAL_GDP"}, {i["indicator_id"] for i in self.registry.indicators if not i["enabled"]})

    def test_operational_limits_recorded(self):
        self.assertTrue(all(s["operational_limits"] and s["terms_reviewed_at"] for s in self.registry.sources))

    def test_terms_recheck_recorded(self):
        self.assertTrue(all(s["next_terms_recheck"] == "2027-02-18" for s in self.registry.sources))

    def test_mappings_cover_slice(self):
        self.assertEqual(6, len(self.registry.mappings["series_mappings"]))

    def test_ingestion_allow(self):
        self.assertEqual("ALLOW", self.engine.require("bls-ces", "ingestion").decision)

    def test_dimensions_independent(self):
        self.assertEqual("UNKNOWN", self.engine.decide("bls-ces", "model_feature_use").decision)

    def test_unknown_fails_closed(self):
        with self.assertRaises(RightsDenied):
            self.engine.require("bls-ces", "model_training_ml_use")

    def test_unregistered_source_fails_closed(self):
        with self.assertRaises(RightsDenied):
            self.engine.require("missing", "public_display")

    def test_unregistered_operation_fails_closed(self):
        with self.assertRaises(RightsDenied):
            self.engine.require("bls-ces", "invented_operation")


if __name__ == "__main__":
    unittest.main()

