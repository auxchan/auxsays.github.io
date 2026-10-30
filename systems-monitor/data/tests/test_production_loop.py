import hashlib
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from _support import PACKAGE_ROOT
from systems_monitor_data.production import _bls_source_freshness, _merge_current_parity, _merge_historical_parity, update_production


PRODUCTION = PACKAGE_ROOT / "production" / "systems-monitor-production.json"


class ProductionLoopTests(unittest.TestCase):
    def test_partial_cadence_carries_forward_not_due_parity_without_masking_due_results(self):
        existing = {
            "sourceParity": [
                {"sourceSeriesId": "DOL", "match": True, "acceptedLatestValue": "10"},
                {"sourceSeriesId": "BLS", "match": True, "acceptedLatestValue": "20"},
            ],
            "historicalParity": {
                "samples": [
                    {"sourceSeriesId": "DOL", "period": "2026-01-01", "sampleRoles": ["NEWEST"], "status": "MATCH_CURRENT_OFFICIAL"},
                    {"sourceSeriesId": "BLS", "period": "2026-01", "sampleRoles": ["NEWEST"], "status": "MATCH_CURRENT_OFFICIAL"},
                ]
            },
        }
        fresh_current = [{"sourceSeriesId": "DOL", "match": True, "acceptedLatestValue": "11"}]
        current = _merge_current_parity(existing, fresh_current, {"DOL", "BLS"}, {"DOL"})
        self.assertEqual(["BLS", "DOL"], [row["sourceSeriesId"] for row in current])
        self.assertEqual("20", current[0]["acceptedLatestValue"])
        self.assertEqual("11", current[1]["acceptedLatestValue"])

        fresh_historical = {
            "samples": [
                {"sourceSeriesId": "DOL", "period": "2026-01-08", "sampleRoles": ["NEWEST"], "status": "MATCH_CURRENT_OFFICIAL"}
            ]
        }
        historical = _merge_historical_parity(existing, fresh_historical, {"DOL", "BLS"}, {"DOL"})
        self.assertEqual(2, historical["counts"]["seriesAudited"])
        self.assertEqual(2, historical["counts"]["matches"])
        self.assertEqual({"BLS", "DOL"}, {row["sourceSeriesId"] for row in historical["samples"]})

    def test_committed_production_model_is_governed_current_and_self_contained(self):
        document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
        self.assertEqual("systems-monitor-production-1.0.0", document["schemaVersion"])
        self.assertEqual(18, len(document["sourceParity"]))
        self.assertTrue(all(row["match"] for row in document["sourceParity"]))
        self.assertEqual(18, len({row["sourceSeriesId"] for row in document["sourceParity"]}))
        historical = document["historicalParity"]
        self.assertEqual("NEWEST_PRIOR_OLDER_PLUS_EVERY_REVISION_CHAIN_PERIOD", historical["selectionPolicy"])
        self.assertEqual(18, historical["counts"]["seriesAudited"])
        self.assertEqual(0, historical["counts"]["staleAcceptedRevisions"])
        self.assertEqual(0, historical["counts"]["officialWindowNotRetrieved"])
        self.assertEqual(historical["counts"]["samples"], historical["counts"]["matches"])
        revision_periods = {
            (row["sourceSeriesId"], row["period"])
            for row in historical["samples"]
            if "REVISION_CHAIN" in row["sampleRoles"]
        }
        expected_revision_periods = {
            (row["sourceSeriesId"], row["validTime"])
            for row in document["acceptedHistory"]["observations"]
            if row["supersedesObservationId"] is not None
        }
        self.assertEqual(expected_revision_periods, revision_periods)
        self.assertEqual(0, document["governance"]["acceptedStructuralRelationships"])
        self.assertEqual("OPEN", document["governance"]["gateB"])
        self.assertEqual("LOCKED_UNAVAILABLE", document["governance"]["forecasting"])
        self.assertIsNone(document["calculations"]["PAYROLL_CHANGE_V1"]["publicValue"])
        self.assertEqual("CALC_CANDIDATE_PENDING_ACCEPTANCE", document["calculations"]["PAYROLL_CHANGE_V1"]["status"])
        accepted_ids = {row["sourceSeriesId"] for row in document["acceptedHistory"]["observations"]}
        self.assertNotIn("DOL-UI-SA-CONTINUED", accepted_ids)
        self.assertNotIn("DOL-UI-SA-IUR", accepted_ids)
        for record in document["rawEvidence"]:
            path = PACKAGE_ROOT.parent.parent / record["repositoryPath"]
            self.assertTrue(path.is_file())
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_second_run_inside_every_source_cadence_is_a_true_no_op(self):
        document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
        clock = datetime.fromisoformat(document["generatedAt"].replace("Z", "+00:00")) + timedelta(hours=1)
        before = PRODUCTION.read_bytes()
        result = update_production(
            package_root=PACKAGE_ROOT,
            runtime_root=PACKAGE_ROOT / "local" / "production-idempotency-test",
            output_path=PRODUCTION,
            now=clock,
            force=False,
        )
        self.assertEqual("NO_SOURCES_DUE", result["status"])
        self.assertFalse(result["changed"])
        self.assertEqual(before, PRODUCTION.read_bytes())

    def test_bls_freshness_uses_the_governed_period_age_ceiling(self):
        profile = {"health_policy": {"stale_after_hours": 1488}}
        current = _bls_source_freshness(
            "bls-ces", [{"observation_period": "2026-09"}], profile,
            datetime.fromisoformat("2026-10-30T12:00:00+00:00"),
        )
        stale = _bls_source_freshness(
            "bls-ces", [{"observation_period": "2026-06"}], profile,
            datetime.fromisoformat("2026-10-30T12:00:00+00:00"),
        )
        self.assertEqual("CURRENT", current["status"])
        self.assertEqual("STALE", stale["status"])

    def test_public_app_has_no_review_snapshot_or_review_history_import(self):
        imports = "\n".join(path.read_text(encoding="utf-8") for path in (PACKAGE_ROOT.parent / "app" / "src").rglob("*.ts*"))
        self.assertNotIn("data/review/local-active-pdi-test-snapshot.json", imports)
        self.assertNotIn("data/review/layoffs-accepted-history.json", imports)
        self.assertIn("data/production/systems-monitor-production.json", imports)
        runner = (PACKAGE_ROOT / "src" / "systems_monitor_data" / "production.py").read_text(encoding="utf-8")
        self.assertNotIn("review/local-active-pdi-test-snapshot.json", runner)
        self.assertNotIn("review/layoffs-accepted-history.json", runner)


if __name__ == "__main__":
    unittest.main()
