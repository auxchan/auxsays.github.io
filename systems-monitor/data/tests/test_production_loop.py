import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from _support import PACKAGE_ROOT
from systems_monitor_data.production import _bls_source_freshness, _due, _merge_current_parity, _merge_historical_parity, update_production
from systems_monitor_data.production_integrity import payload_sha256, validate_production_evidence


PRODUCTION = PACKAGE_ROOT / "production" / "systems-monitor-production.json"


class ProductionLoopTests(unittest.TestCase):
    def test_all_history_rows_resolve_to_verified_original_raw_bytes(self):
        document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
        result = validate_production_evidence(document, PRODUCTION.parent / "raw")
        self.assertEqual(len(document["acceptedHistory"]["observations"]), result["verifiedHistoryRows"])
        self.assertEqual(0, result["missingHistoryArtifacts"])

    def test_integrity_rejects_missing_history_reference_even_with_valid_payload_hash(self):
        document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
        document["acceptedHistory"]["observations"][0]["artifactSha256"] = "0" * 64
        document["payloadSha256"] = payload_sha256(document)
        with self.assertRaisesRegex(ValueError, "unmanifested"):
            validate_production_evidence(document, PRODUCTION.parent / "raw")

    def test_integrity_rejects_tampered_bytes_and_escaping_paths(self):
        document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            record = document["rawEvidence"][0]
            target = Path(directory) / record["relative_path"]
            target.parent.mkdir(parents=True)
            target.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "integrity failure"):
                validate_production_evidence(document, Path(directory))
        document["rawEvidence"][0]["relative_path"] = "../outside.bin"
        document["payloadSha256"] = payload_sha256(document)
        with self.assertRaisesRegex(ValueError, "escapes"):
            validate_production_evidence(document, PRODUCTION.parent / "raw")

    def test_successful_no_change_check_controls_cadence_without_republishing_snapshot(self):
        clock = datetime.fromisoformat("2026-11-01T12:00:00+00:00")
        seed = {"automation": {"sourceChecks": {"bls-ces": {"lastSuccessfulCheck": "2026-10-30T12:00:00Z"}}}}
        checks = {"bls-ces": {"lastSuccessfulCheck": "2026-11-01T11:00:00Z"}}
        self.assertTrue(_due("bls-ces", seed, clock, False))
        self.assertFalse(_due("bls-ces", seed, clock, False, checks))
        self.assertTrue(_due("bls-ces", seed, clock, True, checks))
        checks["bls-ces"]["lastSuccessfulCheck"] = "2099-01-01T00:00:00Z"
        self.assertTrue(_due("bls-ces", seed, clock, False, checks))

    def test_fresh_series_does_not_mask_stale_sibling(self):
        result = _bls_source_freshness("bls-ces", [
            {"source_series_id": "fresh", "observation_period": "2026-09"},
            {"source_series_id": "stale", "observation_period": "2026-01"},
        ], {"health_policy": {"stale_after_hours": 1488}}, datetime.fromisoformat("2026-10-30T12:00:00+00:00"))
        self.assertEqual("STALE", result["status"])
        self.assertEqual("CURRENT", result["series"]["fresh"]["status"])

    def test_no_change_retrieval_persists_cadence_without_rewriting_production(self):
        document = json.loads(PRODUCTION.read_text(encoding="utf-8"))
        record = max((row for row in document["rawEvidence"] if row["source_id"] == "bls-layoffs-combined"), key=lambda row: row["retrieved_time"])
        body = (PRODUCTION.parent / "raw" / record["relative_path"]).read_bytes()
        clock = datetime.fromisoformat(document["generatedAt"].replace("Z", "+00:00")) + timedelta(hours=5)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock.astimezone(tz or timezone.utc)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "production" / PRODUCTION.name
            shutil.copytree(PRODUCTION.parent / "raw", output.parent / "raw")
            output.write_text(json.dumps(document), encoding="utf-8")

            def run():
                # Keep other sources within cadence so this exercises real BLS parsing,
                # acceptance, parity, persistence, and cadence without any live network.
                telemetry = output.parent / "source-checks.json"
                checks = json.loads(telemetry.read_text()) if telemetry.exists() else {"sourceChecks": {}}
                for source in document["automation"]["sourceChecks"]:
                    if source != "bls-ces":
                        checks["sourceChecks"][source] = {"lastSuccessfulCheck": clock.isoformat()}
                telemetry.write_text(json.dumps(checks), encoding="utf-8")
                def response(specs, *_):
                    payload = json.loads(body)
                    requested = {spec.series_id for spec in specs}
                    payload["Results"]["series"] = [row for row in payload["Results"]["series"] if row["seriesID"] in requested]
                    return SimpleNamespace(body=json.dumps(payload).encode(), final_url=record["request_identity"], content_type=record["content_type"], retrieved_time=clock.isoformat())

                with patch("systems_monitor_data.production.datetime", Clock), patch("systems_monitor_data.production.BlsDolLayoffsCollector.retrieve_bls", side_effect=response) as retrieve:
                    result = update_production(package_root=PACKAGE_ROOT, runtime_root=root / "runtime", output_path=output, now=clock)
                return result, retrieve.call_count

            first, calls = run()
            self.assertEqual("UPDATED", first["status"])
            self.assertEqual(1, calls)
            before = output.read_bytes()
            clock += timedelta(hours=5)
            second, calls = run()
            self.assertEqual("UNCHANGED", second["status"])
            self.assertEqual(1, calls)
            self.assertEqual(before, output.read_bytes())
            telemetry = json.loads((output.parent / "source-checks.json").read_text())
            self.assertEqual(clock, datetime.fromisoformat(telemetry["sourceChecks"]["bls-ces"]["lastSuccessfulCheck"].replace("Z", "+00:00")))
            clock += timedelta(hours=1)
            third, calls = run()
            self.assertEqual("NO_SOURCES_DUE", third["status"])
            self.assertEqual(0, calls)
            self.assertEqual(before, output.read_bytes())

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
