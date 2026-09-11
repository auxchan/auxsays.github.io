import copy
import json
import unittest
from pathlib import Path

from _support import CONFIG, PACKAGE_ROOT
from systems_monitor_data.layoffs_acceptance import (
    load_acceptance_proposal,
    load_vintage_matrix,
    simulate_acceptance,
)


PROPOSAL = CONFIG / "layoffs" / "history_acceptance_proposal.json"
VINTAGES = CONFIG / "layoffs" / "vintage_capability_matrix.json"
RIGHTS = CONFIG / "rights" / "rights.json"
LOCAL_BATCH = PACKAGE_ROOT / "local" / "layoffs-runtime" / "layoffs-batch-candidate.json"


def row(
    source_id: str,
    series_id: str,
    factor: str,
    *,
    unit: str,
    frequency: str,
    period: str,
    artifact_hash: str,
) -> dict:
    return {
        "observation_id": f"candidate-{series_id}-{period}",
        "canonical_factor": factor,
        "source_id": source_id,
        "source_series_id": series_id,
        "release_id": "retrieval-2026-09-10",
        "artifact_sha256": artifact_hash,
        "value": "10",
        "unit": unit,
        "frequency": frequency,
        "geography": "US",
        "seasonal_adjustment": "seasonally adjusted",
        "observation_period": period,
        "public_time": "2026-09-10T12:00:00Z",
        "retrieved_time": "2026-09-10T12:00:00Z",
        "accepted_time": None,
        "publication_time_kind": "conservative_retrieval_bound",
        "publication_eligible": False,
        "provenance_url": "https://example.gov/api",
        "evidence_url": "https://example.gov/evidence",
        "methodology_url": "https://example.gov/methodology",
    }


def batch(*rows: dict) -> dict:
    artifact_hash = "a" * 64
    return {
        "schemaVersion": "layoffs-source-candidate-batch-1.0.0",
        "activationStatus": "NOT_ACCEPTED_NOT_PUBLISHABLE",
        "generatedAt": "2026-09-10T12:00:00Z",
        "runId": "test-run",
        "rawArtifacts": [{"sha256": artifact_hash, "parser_version": "layoffs-bls-json-v1"}],
        "candidates": list(rows),
    }


class LayoffsAcceptanceProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = load_acceptance_proposal(PROPOSAL)
        cls.vintages = load_vintage_matrix(VINTAGES)
        cls.rights = json.loads(RIGHTS.read_text(encoding="utf-8"))

    def test_proposal_is_exact_series_and_cannot_activate(self):
        self.assertEqual("NONE", self.proposal["authority"])
        self.assertEqual("NONE", self.proposal["activationEffect"])
        self.assertFalse(self.proposal["automaticRoutinePromotionEnabled"])
        self.assertEqual(13, len(self.proposal["rules"]))
        self.assertEqual(13, len({(row["sourceId"], row["sourceSeriesId"]) for row in self.proposal["rules"]}))

    def test_simulation_separates_ready_rights_blocked_and_outside_rows(self):
        artifact_hash = "a" * 64
        candidate_batch = batch(
            row(
                "bls-jolts", "JTS000000000000000LDL", "factor:layoffs-discharges-level",
                unit="thousands of persons", frequency="monthly", period="2026-07", artifact_hash=artifact_hash,
            ),
            row(
                "bls-bed", "BDS0000000000000000110004LQ5", "factor:gross-job-losses",
                unit="thousands of jobs", frequency="quarterly", period="2025-Q4", artifact_hash=artifact_hash,
            ),
            row(
                "bls-bed", "BDS0000000000000000110001LQ5", "factor:gross-job-gains",
                unit="thousands of jobs", frequency="quarterly", period="2025-Q4", artifact_hash=artifact_hash,
            ),
        )
        report = simulate_acceptance(candidate_batch, self.proposal, self.rights, self.vintages)
        self.assertEqual(2, report["counts"]["structuralMatches"])
        self.assertEqual(2, report["counts"]["decisionReadyIfTaylorApproves"])
        self.assertEqual(0, report["counts"]["blockedWithinProposedScope"])
        self.assertEqual(0, report["counts"]["contingentWithinProposedScope"])
        self.assertEqual(1, report["counts"]["outsideProposedScope"])
        self.assertEqual(0, report["counts"]["acceptedObservationsWritten"])

    def test_level_two_archive_capability_does_not_self_grant_vintage_eligibility(self):
        artifact_hash = "a" * 64
        current = row(
            "bls-jolts", "JTS000000000000000LDL", "factor:layoffs-discharges-level",
            unit="thousands of persons", frequency="monthly", period="2026-07", artifact_hash=artifact_hash,
        )
        report = simulate_acceptance(batch(current), self.proposal, self.rights, self.vintages)
        self.assertEqual(0, report["counts"]["forecastVintageEligible"])
        self.assertEqual(1, report["counts"]["forecastVintageIneligible"])

        reconstructed = copy.deepcopy(current)
        reconstructed["forecast_vintage_eligible"] = True
        reconstructed["history_use_class"] = "VINTAGE_RECONSTRUCTED"
        reconstructed["vintage_evidence"] = {
            "archive_url": "https://example.gov/archive/release.htm",
            "artifact_sha256": "b" * 64,
            "release_header_time": "2026-08-01T14:00:00Z",
            "table_selector": "Table 1 / layoffs and discharges level",
        }
        report = simulate_acceptance(batch(reconstructed), self.proposal, self.rights, self.vintages)
        self.assertEqual(1, report["counts"]["forecastVintageEligible"])

    def test_exact_series_scope_rejects_identity_constraint_changes(self):
        artifact_hash = "a" * 64
        baseline = row(
            "bls-jolts", "JTS000000000000000LDL", "factor:layoffs-discharges-level",
            unit="thousands of persons", frequency="monthly", period="2026-07", artifact_hash=artifact_hash,
        )
        cases = {
            "unit": ("unit", "persons"),
            "geography": ("geography", "US:CA"),
            "seasonal adjustment": ("seasonal_adjustment", "not seasonally adjusted"),
            "canonical factor": ("canonical_factor", "factor:temporary-layoffs"),
        }
        for label, (field, value) in cases.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(baseline)
                changed[field] = value
                report = simulate_acceptance(batch(changed), self.proposal, self.rights, self.vintages)
                self.assertEqual(1, report["counts"]["constraintRejectedWithinProposedScope"])
                self.assertEqual(0, report["counts"]["outsideProposedScope"])
                self.assertEqual(0, report["counts"]["acceptedObservationsWritten"])

    def test_unknown_series_remains_outside_authority(self):
        artifact_hash = "a" * 64
        unknown = row(
            "bls-jolts", "JTS-NOT-AUTHORIZED", "factor:layoffs-discharges-level",
            unit="thousands of persons", frequency="monthly", period="2026-07", artifact_hash=artifact_hash,
        )
        report = simulate_acceptance(batch(unknown), self.proposal, self.rights, self.vintages)
        self.assertEqual(1, report["counts"]["outsideProposedScope"])
        self.assertEqual(0, report["counts"]["constraintRejectedWithinProposedScope"])

    @unittest.skipUnless(LOCAL_BATCH.exists(), "local acquisition batch is intentionally gitignored")
    def test_current_282_row_batch_calibrates_to_the_reviewed_boundary(self):
        current_batch = json.loads(LOCAL_BATCH.read_text(encoding="utf-8"))
        report = simulate_acceptance(current_batch, self.proposal, self.rights, self.vintages)
        self.assertEqual(282, report["input"]["batchCandidates"])
        self.assertEqual(200, report["counts"]["structuralMatches"])
        self.assertEqual(167, report["counts"]["decisionReadyIfTaylorApproves"])
        self.assertEqual(0, report["counts"]["blockedWithinProposedScope"])
        self.assertEqual(33, report["counts"]["contingentWithinProposedScope"])
        self.assertEqual(82, report["counts"]["outsideProposedScope"])
        self.assertEqual(0, report["counts"]["constraintRejectedWithinProposedScope"])
        self.assertEqual(200, report["counts"]["descriptiveHistoryCandidatesAfterPreconditions"])
        self.assertEqual(11, report["counts"]["comparableHistoryReadySeries"])
        self.assertEqual(12, report["counts"]["comparableHistoryReadySeriesAfterPreconditions"])
        self.assertEqual(12, report["counts"]["structurallyComparableSeriesIfAllBlockersResolve"])
        self.assertEqual(5, report["input"]["sourceDiagnostics"]["blsSkippedMissingValues"])
        self.assertEqual(57, report["input"]["sourceDiagnostics"]["dolSkippedMissingValues"])
        self.assertEqual("DOL-UI-r539cyNational-2026-09-10", report["input"]["sourceDiagnostics"]["dolSourceReleaseMarker"])
        self.assertEqual("STALE", report["input"]["sourceDiagnostics"]["dolFreshness"]["status"])
        self.assertEqual(0, report["counts"]["forecastVintageEligible"])
        self.assertEqual(0, report["counts"]["acceptedObservationsWritten"])

    def test_authority_or_activation_on_proposal_is_rejected(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["authority"] = "SELF_GRANTED"
        with self.assertRaisesRegex(ValueError, "non-authoritative proposal"):
            simulate_acceptance(
                {"schemaVersion": "layoffs-source-candidate-batch-1.0.0", "activationStatus": "NOT_ACCEPTED_NOT_PUBLISHABLE", "candidates": []},
                proposal,
                self.rights,
                self.vintages,
            )


if __name__ == "__main__":
    unittest.main()
