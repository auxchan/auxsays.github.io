import json
import tempfile
import unittest
from pathlib import Path

from _support import CONFIG
from systems_monitor_data.layoffs_history import (
    append_history,
    comparable_change,
    deterministic_interpretation,
    history_artifact,
    load_acceptance_ledger,
    observations_as_of,
    promote_candidate_batch,
)


ACCEPTANCE = CONFIG / "layoffs" / "history_acceptance.json"


def candidate(period: str, value: str, release: str, public: str, retrieved: str) -> dict:
    return {
        "observation_id": f"candidate-{release}-{period}",
        "canonical_factor": "factor:canonical:layoffs-and-discharges",
        "source_id": "bls-jolts",
        "source_series_id": "JTS000000000000000LDL",
        "release_id": release,
        "artifact_sha256": "a" * 64,
        "value": value,
        "unit": "thousands of persons",
        "frequency": "monthly",
        "geography": "US",
        "seasonal_adjustment": "seasonally adjusted",
        "observation_period": period,
        "public_time": public,
        "retrieved_time": retrieved,
        "accepted_time": None,
        "publication_time_kind": "official",
        "revision_status": "as_published",
        "provenance_url": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "evidence_url": "https://data.bls.gov/timeseries/JTS000000000000000LDL",
        "methodology_url": "https://www.bls.gov/opub/hom/jlt/home.htm",
    }


def batch(*rows: dict) -> dict:
    return {
        "schemaVersion": "layoffs-source-candidate-batch-1.0.0",
        "activationStatus": "NOT_ACCEPTED_NOT_PUBLISHABLE",
        "candidates": list(rows),
    }


def authorized_ledger() -> dict:
    return {
        "schemaVersion": "layoffs-history-acceptance-1.0.0",
        "authority": "TEST_AUTHORITY",
        "defaultDecision": "REJECT_UNLESS_EXPLICITLY_LISTED",
        "automaticRoutinePromotionEnabled": True,
        "rules": [{
            "ruleId": "TEST_JOLTS_LDL_V1",
            "authority": "TEST_AUTHORITY",
            "acceptedAt": "2026-01-01T00:00:00Z",
            "canonicalFactorId": "factor:canonical:layoffs-and-discharges",
            "sourceId": "bls-jolts",
            "sourceSeriesId": "JTS000000000000000LDL",
            "unit": "thousands of persons",
            "frequency": "monthly",
            "geography": "US",
            "seasonalAdjustment": "seasonally adjusted",
            "rightsState": "ALLOW",
            "effectiveFrom": "2026-01-01T00:00:00Z",
        }],
    }


class LayoffsHistoryTests(unittest.TestCase):
    def test_production_ledger_is_closed_and_cannot_promote_retrieval(self):
        ledger = load_acceptance_ledger(ACCEPTANCE)
        rows = promote_candidate_batch(
            batch(candidate("2026-07", "1700", "R1", "2026-08-01T12:00:00Z", "2026-08-01T12:01:00Z")),
            ledger,
            accepted_at="2026-08-01T12:02:00Z",
        )
        self.assertEqual("NONE", ledger["authority"])
        self.assertEqual([], rows)

    def test_explicit_rule_builds_native_cadence_change_without_materiality_or_impact(self):
        rows = promote_candidate_batch(
            batch(
                candidate("2026-06", "1700", "R1", "2026-07-01T12:00:00Z", "2026-07-01T12:01:00Z"),
                candidate("2026-07", "1760", "R2", "2026-08-01T12:00:00Z", "2026-08-01T12:01:00Z"),
            ),
            authorized_ledger(),
            accepted_at="2026-08-01T12:02:00Z",
        )
        change = comparable_change(
            rows,
            canonical_factor_id="factor:canonical:layoffs-and-discharges",
            source_series_id="JTS000000000000000LDL",
        )
        self.assertEqual("60", change["absoluteDelta"])
        self.assertEqual("UP", change["direction"])
        self.assertEqual("↑", change["directionGlyph"])
        self.assertEqual("UNKNOWN", change["materiality"]["status"])
        self.assertFalse(change["economicSignalEligible"])
        self.assertEqual("UNKNOWN", change["destinationImpact"]["status"])
        self.assertFalse(change["forecastVintageEligible"])
        interpretation = deterministic_interpretation(
            change,
            source_measure="BLS JOLTS layoffs and discharges, seasonally adjusted.",
            relevance="This is a direct measure of separations initiated by employers.",
        )
        self.assertIn("does not establish causality", interpretation["WHAT_AUXSAYS_CANNOT_CLAIM"])

    def test_source_registry_alias_is_normalized_before_acceptance(self):
        row = candidate("2026-07", "1760", "R2", "2026-08-01T12:00:00Z", "2026-08-01T12:01:00Z")
        row["canonical_factor"] = "factor:layoffs-discharges-level"
        promoted = promote_candidate_batch(
            batch(row),
            authorized_ledger(),
            accepted_at="2026-08-01T12:02:00Z",
        )
        self.assertEqual("factor:canonical:layoffs-and-discharges", promoted[0]["canonicalFactorId"])

    def test_revision_replay_separates_public_operational_and_latest_truth(self):
        ledger = authorized_ledger()
        original = promote_candidate_batch(
            batch(candidate("2026-06", "1700", "R1", "2026-07-01T12:00:00Z", "2026-07-01T12:01:00Z")),
            ledger,
            accepted_at="2026-07-01T12:02:00Z",
        )
        revised = promote_candidate_batch(
            batch(candidate("2026-06", "1680", "R2", "2026-08-01T12:00:00Z", "2026-08-01T12:01:00Z")),
            ledger,
            accepted_at="2026-08-01T12:02:00Z",
            existing_history=original,
        )
        history = append_history(original, revised)
        public_then = observations_as_of(history, mode="PUBLICLY_AVAILABLE_AS_OF", cutoff="2026-07-15T00:00:00Z")
        known_then = observations_as_of(history, mode="OPERATIONALLY_KNOWN_AS_OF", cutoff="2026-07-15T00:00:00Z")
        latest = observations_as_of(history, mode="LATEST_REVISED_TRUTH", cutoff=None)
        self.assertEqual("1700", public_then[0]["value"])
        self.assertEqual("1700", known_then[0]["value"])
        self.assertEqual("1680", latest[0]["value"])
        self.assertEqual(1, latest[0]["revisionNumber"])
        self.assertEqual(original[0]["observationId"], latest[0]["supersedesObservationId"])

    def test_forecast_replay_excludes_current_revised_history(self):
        rows = promote_candidate_batch(
            batch(candidate("2026-06", "1700", "R1", "2026-07-01T12:00:00Z", "2026-07-01T12:01:00Z")),
            authorized_ledger(),
            accepted_at="2026-07-01T12:02:00Z",
        )
        self.assertEqual("CURRENT_REVISED_HISTORY", rows[0]["historyUseClass"])
        self.assertEqual([], observations_as_of(rows, mode="FORECAST_AS_OF", cutoff="2026-08-01T00:00:00Z"))

    def test_forecast_replay_requires_explicit_authorized_vintage_class(self):
        ledger = authorized_ledger()
        ledger["rules"][0].update({
            "historyUseClass": "VINTAGE_RECONSTRUCTED",
            "forecastVintageEligible": True,
            "vintageEvidenceId": "archive-artifact:test-jolts-r1",
        })
        rows = promote_candidate_batch(
            batch(candidate("2026-06", "1700", "R1", "2026-07-01T12:00:00Z", "2026-07-01T12:01:00Z")),
            ledger,
            accepted_at="2026-07-01T12:02:00Z",
        )
        replay = observations_as_of(rows, mode="FORECAST_AS_OF", cutoff="2026-08-01T00:00:00Z")
        self.assertEqual(1, len(replay))
        self.assertTrue(replay[0]["forecastVintageEligible"])

    def test_materiality_registry_without_accepted_governance_stays_unknown(self):
        rows = promote_candidate_batch(
            batch(
                candidate("2026-06", "1700", "R1", "2026-07-01T12:00:00Z", "2026-07-01T12:01:00Z"),
                candidate("2026-07", "1760", "R2", "2026-08-01T12:00:00Z", "2026-08-01T12:01:00Z"),
            ),
            authorized_ledger(),
            accepted_at="2026-08-01T12:02:00Z",
        )
        registry = {
            "authority": "ARBITRARY",
            "profiles": [{
                "sourceSeriesId": "JTS000000000000000LDL",
                "frequency": "monthly",
                "absoluteDeltaThreshold": "1",
            }],
        }
        change = comparable_change(
            rows,
            canonical_factor_id="factor:canonical:layoffs-and-discharges",
            source_series_id="JTS000000000000000LDL",
            materiality_profiles=registry,
        )
        self.assertEqual("UNKNOWN", change["materiality"]["status"])

    def test_immutable_identity_and_artifact_hash_are_enforced(self):
        rows = promote_candidate_batch(
            batch(candidate("2026-06", "1700", "R1", "2026-07-01T12:00:00Z", "2026-07-01T12:01:00Z")),
            authorized_ledger(),
            accepted_at="2026-07-01T12:02:00Z",
        )
        artifact = history_artifact(rows, generated_at="2026-07-01T12:03:00Z")
        self.assertEqual(1, len(artifact["observations"]))
        self.assertEqual(64, len(artifact["payloadSha256"]))
        mutated = dict(rows[0], value="999")
        with self.assertRaisesRegex(ValueError, "object hash"):
            append_history([], [mutated])

    def test_acceptance_ledger_rejects_authority_free_rules(self):
        invalid = authorized_ledger()
        invalid["authority"] = "NONE"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "authority-free"):
                load_acceptance_ledger(path)


if __name__ == "__main__":
    unittest.main()
