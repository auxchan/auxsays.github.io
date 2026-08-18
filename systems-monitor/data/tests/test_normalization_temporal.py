import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from _support import CONFIG, FIXTURES, fixture
from systems_monitor_data.normalize import normalize_bls, normalize_dol_release, normalize_dol_xml
from systems_monitor_data.registry import Registry
from systems_monitor_data.storage import ObservationStore


class NormalizationTemporalTests(unittest.TestCase):
    def setUp(self):
        self.registry = Registry(CONFIG)
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ObservationStore(Path(self.tmp.name) / "data.sqlite")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def bls(self, payload=None):
        raw = payload if payload is not None else (FIXTURES / "bls_response_minimized.json").read_bytes()
        indicators = [i for i in self.registry.enabled_indicators() if i["source_id"].startswith("bls-")]
        return normalize_bls(raw, indicators, release_id="BLS-R1", artifact_sha256="a" * 64, retrieved_time="2026-08-18T19:44:00Z", accepted_time="2026-08-18T19:44:01Z", provenance_url="https://api.bls.gov/publicAPI/v2/timeseries/data/")

    def test_valid_bls_response(self):
        observations = self.bls()
        self.assertEqual(5, len(observations))
        self.assertEqual(Decimal("158858"), observations[0].value)

    def test_bls_times_are_separate(self):
        observation = self.bls()[0]
        self.assertEqual("conservative_retrieval_bound", observation.publication_time_kind)
        self.assertNotEqual(observation.retrieved_time, observation.accepted_time)

    def test_bls_schema_drift(self):
        with self.assertRaises(ValueError):
            self.bls(b'{"status":"REQUEST_SUCCEEDED","Results":{"changed":[]}}')

    def test_bls_series_mismatch(self):
        document = fixture("bls_response_minimized.json")
        document["Results"]["series"][0]["seriesID"] = "WRONG"
        with self.assertRaises(ValueError):
            self.bls(json.dumps(document).encode())

    def test_bls_invalid_number(self):
        document = fixture("bls_response_minimized.json")
        document["Results"]["series"][0]["data"][0]["value"] = "not-number"
        with self.assertRaises(ValueError):
            self.bls(json.dumps(document).encode())

    def test_bls_malformed_period(self):
        document = fixture("bls_response_minimized.json")
        document["Results"]["series"][0]["data"][0]["period"] = "M13"
        with self.assertRaises(ValueError):
            self.bls(json.dumps(document).encode())

    def test_dol_xml_latest_nonblank(self):
        indicator = next(i for i in self.registry.enabled_indicators() if i["source_id"] == "dol-ui-claims")
        obs = normalize_dol_xml((FIXTURES / "dol_xml_minimized.xml").read_bytes(), indicator, release_id="Q1", artifact_sha256="b" * 64, retrieved_time="2026-08-18T19:45:00Z", accepted_time="2026-08-18T19:45:01Z", provenance_url="https://oui.doleta.gov/unemploy/wkclaims/report.asp")
        self.assertEqual("2026-07-18", obs.valid_time)
        self.assertEqual(Decimal("189000"), obs.value)

    def test_dol_xml_schema_drift(self):
        indicator = next(i for i in self.registry.enabled_indicators() if i["source_id"] == "dol-ui-claims")
        with self.assertRaises(ValueError):
            normalize_dol_xml(b"<changed />", indicator, release_id="Q1", artifact_sha256="b" * 64, retrieved_time="2026-08-18T19:45:00Z", accepted_time="2026-08-18T19:45:01Z", provenance_url="https://oui.doleta.gov/")

    def test_real_dol_revision_and_asof(self):
        pair = fixture("dol_revision_pair.json")
        first = normalize_dol_release(pair["release_a"])
        second_record = dict(pair["release_b"])
        second_record["supersedes_observation_id"] = first.observation_id
        second = normalize_dol_release(second_record)
        self.assertTrue(self.store.add(first))
        self.assertTrue(self.store.add(second))
        self.assertEqual("210000", self.store.latest_revised_truth(first.indicator_id, first.valid_time)["value"])
        self.assertEqual("217000", self.store.publicly_available_as_of(first.indicator_id, first.valid_time, "2024-03-10T00:00:00Z")["value"])
        self.assertEqual("217000", self.store.operationally_known_as_of(first.indicator_id, first.valid_time, "2026-08-18T19:42:49.300000Z")["value"])

    def test_future_revision_does_not_leak(self):
        pair = fixture("dol_revision_pair.json")
        first = normalize_dol_release(pair["release_a"])
        second_record = dict(pair["release_b"]); second_record["supersedes_observation_id"] = first.observation_id
        self.store.add(first); self.store.add(normalize_dol_release(second_record))
        self.assertNotEqual("210000", self.store.publicly_available_as_of(first.indicator_id, first.valid_time, "2024-03-13T23:59:59Z")["value"])

    def test_exact_retry_is_idempotent(self):
        observation = self.bls()[0]
        self.assertTrue(self.store.add(observation))
        self.assertFalse(self.store.add(observation))

    def test_conflicting_duplicate_publication_rejected(self):
        observation = self.bls()[0]
        self.store.add(observation)
        from systems_monitor_data.models import Observation
        data = observation.as_record(); data["observation_id"] = "d" * 64; data["value"] = "999"
        conflicting = Observation(value=Decimal(data.pop("value")), **data)
        with self.assertRaises(ValueError): self.store.add(conflicting)

    def test_same_value_new_release_is_distinct(self):
        first = self.bls()[0]
        data = first.as_record()
        data.update({"observation_id": "c" * 64, "release_id": "BLS-R2", "vintage_id": "BLS-R2", "public_time": "2026-08-19T00:00:00Z", "retrieved_time": "2026-08-19T00:01:00Z", "accepted_time": "2026-08-19T00:02:00Z"})
        from systems_monitor_data.models import Observation
        second = Observation(value=Decimal(data.pop("value")), **data)
        self.assertTrue(self.store.add(first))
        self.assertTrue(self.store.add(second))

    def test_impossible_temporal_order_rejected(self):
        pair = fixture("dol_revision_pair.json")
        pair["release_a"]["accepted_time"] = "2020-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            normalize_dol_release(pair["release_a"])

    def test_provenance_lookup(self):
        observation = self.bls()[0]
        self.store.add(observation)
        self.assertEqual(observation.artifact_sha256, self.store.provenance(observation.observation_id)["artifact_sha256"])


if __name__ == "__main__":
    unittest.main()
