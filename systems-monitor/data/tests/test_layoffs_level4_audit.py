import importlib.util
import json
import unittest
from pathlib import Path

from _support import CONFIG, PACKAGE_ROOT


AUDIT_PATH = CONFIG / "layoffs" / "level4_source_profile_roles.json"
SCRIPT_PATH = PACKAGE_ROOT / "scripts" / "build_layoffs_level4_audit.py"
SPEC = importlib.util.spec_from_file_location("build_layoffs_level4_audit", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class LayoffsLevel4AuditTests(unittest.TestCase):
    def test_generated_audit_matches_current_registries(self):
        expected = MODULE.build_audit(CONFIG)
        actual = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(expected, actual)

    def test_reconciles_64_factors_100_placements_and_74_active_ui_state_records(self):
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        counts = audit["counts"]
        self.assertEqual(64, counts["canonicalLevel4Factors"])
        self.assertEqual(100, counts["level4Placements"])
        self.assertEqual(74, counts["factorSourceStateRecords"])
        self.assertEqual(46, counts["expandedSourceBindings"])
        self.assertEqual(42, counts["recordsWithSourceBindings"])
        self.assertEqual(32, counts["sourceIdentifiedPlaceholders"])
        self.assertEqual(6, counts["sourceOnlyRecords"])
        self.assertEqual(6, counts["sourceOnlyRecordsWithDisposition"])
        self.assertEqual(7, counts["sourceOnlyIdentitiesReviewed"])
        self.assertEqual(1, counts["supersededSourceOnlyAliases"])
        self.assertEqual(0, len(audit["reconciliation"]["sourceOnlyRecords"]) - len(audit["reconciliation"]["sourceOnlyDispositions"]))
        self.assertTrue(all(row["decisionStatus"] == "IMPLEMENTED_NON_ACTIVATING" for row in audit["reconciliation"]["allReviewedDispositions"]))
        self.assertEqual(100, sum(row["placementCount"] for row in audit["canonicalFactors"]))

    def test_every_binding_has_an_explicit_role_and_every_factor_is_classified(self):
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        allowed_roles = {
            "PRIMARY_OBSERVATION_SOURCE",
            "SECONDARY_CORROBORATING_SOURCE",
            "CALC_INPUT",
            "STRUCTURAL_SOURCE",
            "FALLBACK_ACQUISITION_METHOD",
            "ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE",
            "LEGACY_DUPLICATE_SHOULD_REMOVE",
        }
        bindings = [binding for row in audit["factorSourceStateRecords"] for binding in row["sourceBindings"]]
        self.assertEqual(46, len(bindings))
        self.assertTrue(all(binding["role"] in allowed_roles for binding in bindings))
        self.assertTrue(all(binding["whyNeeded"] for binding in bindings))
        self.assertTrue(all(row["claimClass"] for row in audit["canonicalFactors"]))
        self.assertTrue(all(row["sourceStatus"] for row in audit["canonicalFactors"]))


if __name__ == "__main__":
    unittest.main()
