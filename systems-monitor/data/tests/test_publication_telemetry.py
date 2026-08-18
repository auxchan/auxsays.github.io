import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from _support import PACKAGE_ROOT
from systems_monitor_data.publication import AtomicPublisher, CandidateError, validate_factual_candidate
from systems_monitor_data.telemetry import RunTelemetry, append_telemetry


def candidate():
    metrics = []
    for number in range(6):
        metrics.append({"id":f"M{number}","label":f"Metric {number}","stateType":"OBS","value":"1","unit":"percent","observationPeriod":"2026-07","sourceId":"bls-cps","sourceLabel":"BLS","publicTime":"2026-08-01T00:00:00Z","retrievedTime":"2026-08-01T00:01:00Z","acceptedTime":"2026-08-01T00:02:00Z","sourceHealth":"current","provenanceUrl":"https://www.bls.gov/","artifactSha256":"a"*64,"vintageId":"v1","rightsState":"ALLOW"})
    return {"schemaVersion":"x","publicationClass":"factual","activationStatus":"LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED","metrics":metrics,"forecasts":[],"scenarios":[],"rankings":[],"events":[],"outlook":{"status":"unavailable_not_yet_supported"}}


class PublicationTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.publisher = AtomicPublisher(Path(self.tmp.name) / "publication")

    def tearDown(self):
        self.tmp.cleanup()

    def test_factual_candidate_valid(self):
        validate_factual_candidate(candidate())

    def test_fixture_rejected(self):
        value = candidate(); value["publicationClass"] = "fixture"
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_forecast_rejected(self):
        value = candidate(); value["metrics"][0]["stateType"] = "FCST"
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_synthetic_collection_rejected(self):
        value = candidate(); value["rankings"] = [{"x": 1}]
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_unknown_rights_rejected(self):
        value = candidate(); value["metrics"][0]["rightsState"] = "UNKNOWN"
        with self.assertRaises(CandidateError): validate_factual_candidate(value)

    def test_atomic_pointer_activation(self):
        digest, _ = self.publisher.stage(candidate())
        self.publisher.activate_local(digest)
        self.assertEqual(digest, json.loads(self.publisher.pointer.read_text())["sha256"])

    def test_failed_candidate_preserves_pointer(self):
        digest, _ = self.publisher.stage(candidate()); self.publisher.activate_local(digest)
        before = self.publisher.pointer.read_bytes()
        invalid = candidate(); invalid["metrics"] = []
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

