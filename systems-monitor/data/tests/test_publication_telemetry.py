import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from _support import PACKAGE_ROOT
from systems_monitor_data.publication import AtomicPublisher, CandidateError, export_public_pdi_candidate, validate_factual_candidate, validate_internal_review_model
from systems_monitor_data.telemetry import RunTelemetry, append_telemetry


def candidate():
    return json.loads((PACKAGE_ROOT / "review" / "factual-snapshot-candidate.json").read_text(encoding="utf-8"))


def internal_review_model():
    return json.loads((PACKAGE_ROOT / "review" / "internal-factual-review-model.json").read_text(encoding="utf-8"))


def old_incorrect_candidate():
    return {"schemaVersion":"phase3-factual-candidate-1.0.0","publicationClass":"factual","activationStatus":"LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED","generatedAt":"2026-08-18T19:46:00Z","geography":"US","metrics":[],"forecasts":[],"scenarios":[],"rankings":[],"events":[],"outlook":{"status":"unavailable_not_yet_supported"}}


class PublicationTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.publisher = AtomicPublisher(Path(self.tmp.name) / "publication")

    def tearDown(self):
        self.tmp.cleanup()

    def test_factual_candidate_valid(self):
        validate_factual_candidate(candidate())

    def test_internal_review_model_is_explicit_and_exportable(self):
        internal = internal_review_model()
        validate_internal_review_model(internal)
        self.assertEqual(candidate(), export_public_pdi_candidate(internal))

    def test_old_incorrect_candidate_shape_fails_pdi(self):
        with self.assertRaises(CandidateError): validate_factual_candidate(old_incorrect_candidate())

    def test_fixture_rejected(self):
        value = candidate(); value["snapshot"]["publicationClass"] = "fixture"
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_forecast_rejected(self):
        value = candidate(); value["extensions"]["auxsays.phase2.metrics"][0]["stateType"] = "FCST"
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_synthetic_collection_rejected(self):
        value = candidate(); value["outlook"]["occupations"] = [{"label": "SYNTHETIC TEST"}]
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_unknown_rights_rejected(self):
        value = candidate(); value["sources"]["bls-cps"]["publicDisplayAllowed"] = False
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_contract_version_required(self):
        value = candidate(); del value["contractVersion"]
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_snapshot_metadata_required(self):
        value = candidate(); del value["snapshot"]["publishedAt"]
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_source_snapshot_identity_required(self):
        value = candidate(); value["snapshot"]["sourceSnapshotId"] = ""
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_source_reference_required(self):
        value = candidate(); value["extensions"]["auxsays.phase2.metrics"][0]["sourceRefs"] = ["missing"]
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_provenance_reference_required(self):
        value = candidate(); value["extensions"]["auxsays.phase2.metrics"][0]["provenanceRefs"] = ["missing"]
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_official_bls_publication_times_are_separate(self):
        provenance = candidate()["extensions"]["auxsays.phase3.provenance"].values()
        ces = next(record for record in provenance if record["sourceId"] == "bls-ces")
        jolts = next(record for record in provenance if record["sourceId"] == "bls-jolts")
        self.assertEqual("2026-08-07T12:30:00Z", ces["publishedAt"])
        self.assertEqual("2026-08-04T14:00:00Z", jolts["publishedAt"])
        self.assertNotEqual(ces["publishedAt"], ces["retrievedAt"])

    def test_dol_xml_lag_is_not_masked(self):
        health = candidate()["extensions"]["auxsays.phase3.sourceHealth"]["dol-ui-claims"]
        self.assertEqual("current", health["observationFreshness"])
        self.assertEqual("stale", health["retrievalPathHealth"])
        self.assertIn("2026-07-18", health["retrievalPathReason"])

    def test_atomic_pointer_activation(self):
        digest, _ = self.publisher.stage(candidate())
        self.publisher.activate_local(digest)
        self.assertEqual(digest, json.loads(self.publisher.pointer.read_text())["sha256"])

    def test_failed_candidate_preserves_pointer(self):
        digest, _ = self.publisher.stage(candidate()); self.publisher.activate_local(digest)
        before = self.publisher.pointer.read_bytes()
        invalid = candidate(); invalid["extensions"]["auxsays.phase2.metrics"] = []
        with self.assertRaises(CandidateError): self.publisher.stage(invalid)
        self.assertEqual(before, self.publisher.pointer.read_bytes())

    def test_rights_revocation_blocks_activation(self):
        digest, _ = self.publisher.stage(candidate())
        with self.assertRaises(CandidateError): self.publisher.activate_local(digest, rights_allowed=False)
        self.assertFalse(self.publisher.pointer.exists())

    def test_rights_withdrawal_replaces_pointer(self):
        digest, _ = self.publisher.stage(candidate()); self.publisher.activate_local(digest)
        self.publisher.withdraw("rights revoked")
        self.assertEqual("UNAVAILABLE", json.loads(self.publisher.pointer.read_text())["status"])

    def test_concurrent_activation_never_partial(self):
        digests = [self.publisher.stage(candidate())[0] for _ in range(2)]
        threads = [threading.Thread(target=self.publisher.activate_local, args=(digest,)) for digest in digests]
        [thread.start() for thread in threads]; [thread.join() for thread in threads]
        pointer = json.loads(self.publisher.pointer.read_text())
        self.assertIn(pointer["sha256"], digests)

    def test_telemetry_required_fields(self):
        path = Path(self.tmp.name) / "telemetry.jsonl"
        event = RunTelemetry("r","bls-ces","a","b","ok","ok",0,10,1,0,"a"*64,"c","valid")
        append_telemetry(path, event)
        self.assertEqual("bls-ces", json.loads(path.read_text())["source_id"])

    def test_telemetry_secret_guard(self):
        path = Path(self.tmp.name) / "telemetry.jsonl"
        event = RunTelemetry("registrationkey=secret","bls-ces","a","b","ok","ok",0,10,1,0,None,None,"valid")
        with self.assertRaises(ValueError): append_telemetry(path, event)


if __name__ == "__main__":
    unittest.main()
