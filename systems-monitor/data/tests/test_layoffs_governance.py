from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import CONFIG
from systems_monitor_data.layoffs_relationships import relationship_summary, traversable, validate_registry
from systems_monitor_data.layoffs_update import atomic_activate, build_review_snapshot, credential_state, source_due, validate_snapshot


TAXONOMY = json.loads((CONFIG / "layoffs" / "taxonomy.json").read_text(encoding="utf-8"))
RELATIONSHIPS = json.loads((CONFIG / "layoffs" / "relationships.json").read_text(encoding="utf-8"))
SCHEDULER = json.loads((CONFIG / "layoffs" / "scheduler.json").read_text(encoding="utf-8"))


class LayoffsGovernanceTests(unittest.TestCase):
    def test_relationships_preserve_hierarchy_and_non_traversable_candidates(self):
        counts = validate_registry(RELATIONSHIPS)
        summary = relationship_summary(RELATIONSHIPS, TAXONOMY)
        self.assertEqual({"outcomeToLevel1": 1, "level1ToLevel2": 10, "level2ToLevel3": 100}, summary["hierarchy"])
        self.assertEqual(0, summary["traversableCount"])
        self.assertEqual(0, counts["ACCEPTED"])
        self.assertTrue(all(not traversable(edge) for edge in RELATIONSHIPS["relationships"]))

    def test_accounting_claims_and_bankruptcy_semantics_are_distinct(self):
        by_id = {row["edgeId"]: row for row in RELATIONSHIPS["relationships"]}
        self.assertEqual("ACCOUNTING_DEFINITIONAL", by_id["layoffs:bed:contractions-to-gross-losses"]["relationshipType"])
        self.assertEqual("ACCOUNTING_DEFINITIONAL", by_id["layoffs:bed:closures-to-gross-losses"]["relationshipType"])
        self.assertEqual("MEASURES", by_id["layoffs:dol:initial-claims-measure-entry"]["polarity"])
        self.assertEqual("LEADING_SIGNAL", by_id["layoffs:courts:bankruptcy-to-failure-stress"]["polarity"])
        self.assertNotEqual("factor:canonical:gross-job-losses", by_id["layoffs:courts:bankruptcy-to-failure-stress"]["targetNode"])

    def test_scheduler_is_cadence_aware_and_credentials_are_redacted(self):
        bds = next(row for row in SCHEDULER["sources"] if row["sourceId"] == "census-bds")
        self.assertFalse(source_due(bds, "2026-08-28T00:00:00Z", "2026-08-20T00:00:00Z"))
        blocked = credential_state(bds, {})
        self.assertEqual("BLOCKED", blocked["activationState"])
        self.assertNotIn("secret", json.dumps(blocked).lower())
        self.assertIsNone(credential_state(bds, {"AUXSAYS_CENSUS_API_KEY": "never-persist-me"}))

    def test_snapshot_rejects_unaccepted_values_and_mixed_identity(self):
        sources = [{"sourceId": "source-a", "canonicalFactorId": "factor:canonical:initial-claims", "activationState": "SOURCE_ENABLED_PENDING_ACCEPTANCE", "health": "success", "displayValue": "999"}]
        with self.assertRaisesRegex(ValueError, "unaccepted factor"):
            build_review_snapshot(taxonomy=TAXONOMY, source_states=sources, relationships=RELATIONSHIPS["relationships"], generated_at="2026-08-28T00:00:00Z")

    def test_atomic_activation_retains_unchanged_snapshot(self):
        sources = [{"sourceId": "source-a", "canonicalFactorId": "factor:canonical:initial-claims", "activationState": "SOURCE_IDENTIFIED", "health": "blocked", "reasonCode": "REVIEW_PENDING"}]
        snapshot = build_review_snapshot(taxonomy=TAXONOMY, source_states=sources, relationships=RELATIONSHIPS["relationships"], generated_at="2026-08-28T00:00:00Z")
        validate_snapshot(snapshot)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "active.json"
            self.assertTrue(atomic_activate(snapshot, path)["changed"])
            self.assertFalse(atomic_activate(snapshot, path)["changed"])


if __name__ == "__main__":
    unittest.main()
