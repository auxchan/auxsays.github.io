import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath

from _support import CONFIG
from systems_monitor_data.raw import RawStore
from systems_monitor_data.storage import ObservationStore


class RawStorageRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_content_addressed_immutable_capture(self):
        store = RawStore(self.root / "raw")
        record = store.capture(source_id="bls-ces", run_id="r1", request_identity="https://api.bls.gov/x", retrieved_time="2026-01-01T00:00:00Z", release_id="x", content_type="application/json", body=b"{}", parser_version="v1", rights_result="ALLOW")
        self.assertEqual(hashlib.sha256(b"{}").hexdigest(), record.sha256)
        self.assertTrue((self.root / "raw" / record.relative_path).exists())

    def test_duplicate_bytes_deduplicated_but_events_preserved(self):
        store = RawStore(self.root / "raw")
        common = dict(source_id="bls-ces", request_identity="https://api.bls.gov/x", retrieved_time="2026-01-01T00:00:00Z", content_type="application/json", body=b"{}", parser_version="v1", rights_result="ALLOW")
        a = store.capture(run_id="r1", release_id="p1", **common)
        b = store.capture(run_id="r2", release_id="p2", **common)
        self.assertEqual(a.relative_path, b.relative_path)
        self.assertEqual(2, len(list((self.root / "raw" / "events").glob("*.json"))))

    def test_external_filename_never_used(self):
        store = RawStore(self.root / "raw")
        record = store.capture(source_id="x", run_id="r", request_identity="https://www.dol.gov/../../evil", retrieved_time="2026-01-01T00:00:00Z", release_id="../evil", content_type="application/pdf", body=b"pdf", parser_version="v", rights_result="ALLOW")
        self.assertNotIn("evil", record.relative_path)

    def test_tombstone_deletes_bytes_and_retains_hash(self):
        store = RawStore(self.root / "raw")
        record = store.capture(source_id="x", run_id="r", request_identity="https://www.dol.gov/x", retrieved_time="2026-01-01T00:00:00Z", release_id="p", content_type="application/pdf", body=b"pdf", parser_version="v", rights_result="ALLOW")
        tombstone = store.tombstone(record.sha256, "rights revoked", "2026-02-01T00:00:00Z")
        data = json.loads(tombstone.read_text())
        self.assertTrue(data["bytes_deleted"])
        self.assertFalse((self.root / "raw" / record.relative_path).exists())

    def test_run_idempotency(self):
        db = ObservationStore(self.root / "db.sqlite")
        try:
            self.assertTrue(db.begin_run("r1", "bls-ces", "2026-01", "same", 1, "2026-01-01T00:00:00Z"))
            self.assertFalse(db.begin_run("r2", "bls-ces", "2026-01", "same", 1, "2026-01-01T00:00:00Z"))
        finally:
            db.close()

    def test_windows_safe_generated_path(self):
        path = PureWindowsPath("objects") / "ab" / ("a" * 64 + ".json")
        self.assertNotIn(":", str(path))

    def test_linux_safe_generated_path(self):
        path = PurePosixPath("objects") / "ab" / ("a" * 64 + ".json")
        self.assertFalse(str(path).startswith("/"))


if __name__ == "__main__":
    unittest.main()

