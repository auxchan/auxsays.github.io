import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from _support import PACKAGE_ROOT
from systems_monitor_data.publication import AtomicPublisher, CandidateError, export_publication_candidate, materialize_active_pdi_snapshot, validate_active_pdi_snapshot, validate_internal_review_model, validate_publication_candidate
from systems_monitor_data.telemetry import RunTelemetry, append_telemetry


def candidate():
    return json.loads((PACKAGE_ROOT / "review" / "factual-snapshot-candidate.json").read_text(encoding="utf-8"))


def internal_review_model():
    return json.loads((PACKAGE_ROOT / "review" / "internal-factual-review-model.json").read_text(encoding="utf-8"))


def active_proof():
    return json.loads((PACKAGE_ROOT / "review" / "local-active-pdi-test-snapshot.json").read_text(encoding="utf-8"))


def old_incorrect_candidate():
    return {"schemaVersion":"phase3-factual-candidate-1.0.0","publicationClass":"factual","activationStatus":"LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED","generatedAt":"2026-08-18T19:46:00Z","geography":"US","metrics":[],"forecasts":[],"scenarios":[],"rankings":[],"events":[],"outlook":{"status":"unavailable_not_yet_supported"}}


class PublicationTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.publisher = AtomicPublisher(Path(self.tmp.name) / "publication")

    def tearDown(self):
        self.tmp.cleanup()

    def test_factual_candidate_valid(self):
        validate_publication_candidate(candidate())
        self.assertNotIn("publishedAt", candidate()["candidate"])
        self.assertNotIn("snapshot", candidate())

    def test_internal_review_model_is_explicit_and_exportable(self):
        internal = internal_review_model()
        validate_internal_review_model(internal)
        self.assertEqual(candidate(), export_publication_candidate(internal))

    def test_old_incorrect_candidate_shape_fails_pdi(self):
        with self.assertRaises(CandidateError): validate_publication_candidate(old_incorrect_candidate())

    def test_fixture_rejected(self):
        value = candidate(); value["candidate"]["publicationClass"] = "fixture"
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_forecast_rejected(self):
        value = candidate(); value["payload"]["extensions"]["auxsays.phase2.metrics"][0]["stateType"] = "FCST"
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_synthetic_collection_rejected(self):
        value = candidate(); value["payload"]["outlook"]["occupations"] = [{"label": "SYNTHETIC TEST"}]
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_unknown_rights_rejected(self):
        value = candidate(); value["payload"]["sources"]["bls-cps"]["publicDisplayAllowed"] = False
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_contract_version_required(self):
        value = candidate(); del value["candidate"]["targetContractVersion"]
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_candidate_publication_time_prohibited(self):
        value = candidate(); value["candidate"]["publishedAt"] = "2026-08-18T19:46:00Z"
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_source_snapshot_identity_required(self):
        value = candidate(); value["candidate"]["sourceSnapshotId"] = ""
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_source_reference_required(self):
        value = candidate(); value["payload"]["extensions"]["auxsays.phase2.metrics"][0]["sourceRefs"] = ["missing"]
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_provenance_reference_required(self):
        value = candidate(); value["payload"]["extensions"]["auxsays.phase2.metrics"][0]["provenanceRefs"] = ["missing"]
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_official_bls_publication_times_are_separate(self):
        provenance = candidate()["payload"]["extensions"]["auxsays.phase3.provenance"].values()
        ces = next(record for record in provenance if record["sourceId"] == "bls-ces")
        jolts = next(record for record in provenance if record["sourceId"] == "bls-jolts")
        self.assertEqual("2026-08-07T12:30:00Z", ces["publishedAt"])
        self.assertEqual("2026-08-04T14:00:00Z", jolts["publishedAt"])
        self.assertNotEqual(ces["publishedAt"], ces["retrievedAt"])

    def test_dol_xml_lag_is_not_masked(self):
        health = candidate()["payload"]["extensions"]["auxsays.phase3.sourceHealth"]["dol-ui-claims"]
        self.assertEqual("current", health["observationFreshness"])
        self.assertEqual("stale", health["retrievalPathHealth"])
        self.assertIn("2026-07-18", health["retrievalPathReason"])

    def test_six_factual_values_unchanged(self):
        metrics = candidate()["payload"]["extensions"]["auxsays.phase2.metrics"]
        self.assertEqual({
            "US_LABOR_TOTAL_NONFARM_PAYROLLS": 158858,
            "US_LABOR_U3_UNEMPLOYMENT_RATE": 4.1,
            "US_LABOR_FORCE_PARTICIPATION_RATE": 61.4,
            "US_LABOR_INITIAL_UI_CLAIMS": 209000,
            "US_LABOR_JOB_OPENINGS": 7359,
            "US_LABOR_HIRES": 5348,
        }, {metric["id"]: metric["value"] for metric in metrics})

    def test_atomic_pointer_activation(self):
        candidate_digest, candidate_path = self.publisher.stage(candidate())
        active_digest, active_path = self.publisher.activate_local(candidate_digest, activated_at="2026-08-19T00:00:00Z")
        self.assertNotEqual(candidate_digest, active_digest)
        self.assertEqual(active_digest, json.loads(self.publisher.pointer.read_text())["sha256"])
        self.assertNotIn("publishedAt", json.loads(candidate_path.read_text())["candidate"])
        active = json.loads(active_path.read_text())
        self.assertEqual("2026-08-19T00:00:00Z", active["snapshot"]["publishedAt"])
        validate_active_pdi_snapshot(active)

    def test_candidate_cannot_pass_active_pdi_validation(self):
        with self.assertRaises(CandidateError):
            validate_active_pdi_snapshot(candidate())

    def test_committed_local_active_pdi_proof_validates(self):
        proof = active_proof()
        validate_active_pdi_snapshot(proof)
        self.assertEqual("2026-08-18T23:09:35.452742Z", proof["snapshot"]["publishedAt"])

    def test_materialized_snapshot_is_distinct_and_immutable(self):
        before = copy.deepcopy(candidate())
        active = materialize_active_pdi_snapshot(before, activated_at="2026-08-19T00:01:00Z")
        self.assertEqual(candidate(), before)
        self.assertNotEqual(before["candidate"]["id"], active["snapshot"]["id"])
        self.assertEqual("2026-08-19T00:01:00Z", active["snapshot"]["publishedAt"])

    def test_public_hierarchy_uses_child_refs(self):
        value = candidate()
        root = value["payload"]["systems"][0]
        self.assertEqual(6, len(root["childRefs"]))
        self.assertNotIn("children", root)

    def test_embedded_children_rejected(self):
        value = candidate(); value["payload"]["systems"][0]["children"] = []
        with self.assertRaises(CandidateError): validate_publication_candidate(value)

    def test_missing_duplicate_and_cyclic_child_refs_rejected(self):
        missing = candidate(); missing["payload"]["systems"][0]["childRefs"][0] = "missing"
        duplicate = candidate(); duplicate["payload"]["systems"][0]["childRefs"][1] = duplicate["payload"]["systems"][0]["childRefs"][0]
        cyclic = candidate(); child_id = cyclic["payload"]["systems"][0]["childRefs"][0]; cyclic["payload"]["extensions"]["auxsays.phase2.navigationNodes"][child_id]["childRefs"] = ["us-labor"]
        for invalid in (missing, duplicate, cyclic):
            with self.assertRaises(CandidateError): validate_publication_candidate(invalid)

    def test_failed_candidate_preserves_pointer(self):
        digest, _ = self.publisher.stage(candidate()); self.publisher.activate_local(digest, activated_at="2026-08-19T00:00:00Z")
        before = self.publisher.pointer.read_bytes()
        invalid = candidate(); invalid["payload"]["extensions"]["auxsays.phase2.metrics"] = []
        with self.assertRaises(CandidateError): self.publisher.stage(invalid)
        self.assertEqual(before, self.publisher.pointer.read_bytes())

    def test_rights_revocation_blocks_activation(self):
        digest, _ = self.publisher.stage(candidate())
        with self.assertRaises(CandidateError): self.publisher.activate_local(digest, rights_allowed=False)
        self.assertFalse(self.publisher.pointer.exists())
        self.assertEqual([], list(self.publisher.objects.iterdir()))

    def test_failed_activation_preserves_prior_pointer(self):
        digest, _ = self.publisher.stage(candidate())
        self.publisher.activate_local(digest, activated_at="2026-08-19T00:00:00Z")
        before = self.publisher.pointer.read_bytes()
        with self.assertRaises(CandidateError):
            self.publisher.activate_local(digest, rights_allowed=False, activated_at="2026-08-19T00:01:00Z")
        self.assertEqual(before, self.publisher.pointer.read_bytes())

    def test_rights_withdrawal_replaces_pointer(self):
        digest, _ = self.publisher.stage(candidate()); self.publisher.activate_local(digest, activated_at="2026-08-19T00:00:00Z")
        self.publisher.withdraw("rights revoked")
        self.assertEqual("UNAVAILABLE", json.loads(self.publisher.pointer.read_text())["status"])

    def test_concurrent_activation_never_partial(self):
        candidate_digests = [self.publisher.stage(candidate())[0] for _ in range(2)]
        active_results = []
        def activate(digest, timestamp):
            active_results.append(self.publisher.activate_local(digest, activated_at=timestamp)[0])
        threads = [threading.Thread(target=activate, args=(digest, f"2026-08-19T00:00:0{index}Z")) for index, digest in enumerate(candidate_digests)]
        [thread.start() for thread in threads]; [thread.join() for thread in threads]
        pointer = json.loads(self.publisher.pointer.read_text())
        self.assertIn(pointer["sha256"], active_results)

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
