import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from _support import CONFIG, PACKAGE_ROOT
from systems_monitor_data.eia_wpsr import EiaWpsrError, parse_commercial_crude_stocks, parse_refinery_utilization
from systems_monitor_data.phase4b import build_phase4b_candidate, structural_artifact_as_of
from systems_monitor_data.propagation import PropagationEngine


class EiaWpsrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = PACKAGE_ROOT / "evidence" / "eia"

    def test_exact_current_capacity_and_inventory(self):
        capacity = parse_refinery_utilization((self.evidence / "WPSR-table2-2026-08-19.csv").read_bytes(), public_time="2026-08-19T14:30:00Z", retrieved_time="2026-08-22T04:47:28Z")
        inventory = parse_commercial_crude_stocks((self.evidence / "WPSR-table4-2026-08-19.csv").read_bytes(), public_time="2026-08-19T14:30:00Z", retrieved_time="2026-08-22T04:47:28Z")
        self.assertEqual("97.2", capacity.value)
        self.assertEqual("HEADROOM_CONSTRAINED", capacity.assessment)
        self.assertEqual("428.815", inventory.value)
        self.assertEqual("BUFFER_AVAILABLE", inventory.assessment)

    def test_schema_drift_fails_closed(self):
        with self.assertRaises(EiaWpsrError):
            parse_refinery_utilization(b"a,b\n1,2\n", public_time="2026-08-19T14:30:00Z", retrieved_time="2026-08-22T04:47:28Z")


class Phase4bCandidateTests(unittest.TestCase):
    def test_missing_credential_blocks_live_acceptance_without_fabrication(self):
        with patch.dict(os.environ, {}, clear=True):
            candidate = build_phase4b_candidate(data_root=PACKAGE_ROOT)
        self.assertEqual("BLOCKED_LIVE_BEA_CREDENTIAL", candidate["gateBStatus"])
        self.assertEqual([], candidate["acceptedRelationships"])
        self.assertEqual([], candidate["structuralCalculations"])
        self.assertEqual("PENDING", candidate["humanPhase4bQa"])

    def test_exact_484_obs_and_no_forecast(self):
        with patch.dict(os.environ, {}, clear=True):
            candidate = build_phase4b_candidate(data_root=PACKAGE_ROOT)
        obs = next(row for row in candidate["currentObservations"] if row.get("seriesId") == "CES4348400001")
        self.assertEqual("1465.1", obs["value"])
        self.assertEqual("2026-07", obs["observationPeriod"])
        self.assertEqual("https://data.bls.gov/timeseries/CES4348400001", obs["evidenceUrl"])
        self.assertEqual(["FCST", "SCEN"], candidate["claimClassesAbsent"])

    def test_coverage_and_cost_are_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            candidate = build_phase4b_candidate(data_root=PACKAGE_ROOT)
        self.assertEqual("BOUNDED_STRUCTURAL_PROOF_PENDING_LIVE_ACCEPTANCE", candidate["structuralCoverageState"])
        self.assertIn("not a whole-economy model", candidate["coverageWarning"])
        self.assertEqual(0, candidate["recurringInfrastructureCostUsd"])

    def test_replay_has_no_future_leakage(self):
        artifacts = [{"sourceArtifactId":"a","publicReleaseTime":"2025-09-30T12:30:00Z","retrievedTime":"2025-10-01T00:00:00Z","acceptedTime":"2025-10-02T00:00:00Z"}]
        self.assertIsNone(structural_artifact_as_of(artifacts, "2025-09-29T00:00:00Z", "PUBLICLY_AVAILABLE_AS_OF"))
        self.assertEqual("a", structural_artifact_as_of(artifacts, "2025-10-01T00:00:00Z", "PUBLICLY_AVAILABLE_AS_OF")["sourceArtifactId"])
        self.assertIsNone(structural_artifact_as_of(artifacts, "2025-10-01T00:00:00Z", "OPERATIONALLY_KNOWN_AS_OF"))
        self.assertEqual("a", structural_artifact_as_of(artifacts, "2025-10-02T00:00:00Z", "OPERATIONALLY_KNOWN_AS_OF")["sourceArtifactId"])

    def test_phase4a_engine_applies_direct_coefficient_without_total_overlap(self):
        profile = json.loads((CONFIG / "phase4b" / "profile.json").read_text())
        edge = {
            "edgeId":"e", "version":"1.0.0", "sourceNode":"bea:commodity:324", "targetNode":"bea:industry:484",
            "sourceUnit":"STRUCTURAL_PRESSURE_INDEX", "targetUnit":"STRUCTURAL_PRESSURE_INDEX",
            "stateFamily":"STRUCTURAL_PRESSURE", "lifecycle":"ACCEPTED", "effectiveFrom":"2025-09-30T12:30:00Z",
            "acceptedAt":"2026-08-21T00:00:00Z", "polarity":"POSITIVE_REQUIREMENT",
            "evidenceClass":"AUTHORITATIVE_STRUCTURAL", "calibration":"DIRECT_REQUIREMENT_COEFFICIENT",
            "directCoefficient":"0.25",
        }
        result = PropagationEngine(profile).run(
            [{"stateId":"fixture:pressure", "nodeId":"bea:commodity:324", "value":"2", "unit":"STRUCTURAL_PRESSURE_INDEX"}],
            [edge], replay_mode="OPERATIONALLY_KNOWN_AS_OF", knowledge_cutoff="2026-08-21T00:00:00Z",
            source_snapshot_id="TEST_ONLY_NOT_FACTUAL",
        )
        self.assertEqual("0.50", result["contributions"][0]["value"])
        self.assertEqual("BEA_DIRECT_REQUIREMENT_COEFFICIENT", result["contributions"][0]["disposition"])


if __name__ == "__main__":
    unittest.main()
