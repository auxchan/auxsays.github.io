import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from _support import FIXTURES, PACKAGE_ROOT
from systems_monitor_data.phase4b_live import (
    LIVE_BLOCKED,
    LiveBeaAcceptanceRunner,
    LiveBeaBlocked,
    main,
)


TEST_USER_ID = "0" * 36


def live_fixture(name: str, user_id: str = TEST_USER_ID) -> bytes:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    payload.pop("fixtureClass", None)
    payload["BEAAPI"]["Request"] = {
        "RequestParam": [
            {"ParameterName": "USERID", "ParameterValue": user_id},
            {"ParameterName": "RESULTFORMAT", "ParameterValue": "JSON"},
        ]
    }
    return json.dumps(payload).encode("utf-8")


class FakeBeaTransport:
    def __init__(self, *, table_body: bytes | None = None, topology_body: bytes | None = None):
        self.urls = []
        self.table_body = table_body or live_fixture("bea_parameter_values_test_only.json")
        self.year_body = live_fixture("bea_year_values_test_only.json")
        self.topology_body = topology_body or live_fixture("bea_direct_requirements_test_only.json")
        self.benchmark_body = live_fixture("bea_total_requirements_test_only.json")

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        query = parse_qs(urlsplit(url).query)
        method = query["method"][0]
        if method == "GetParameterValues":
            return self.table_body if query["ParameterName"] == ["TableID"] else self.year_body
        if method == "GetData" and query["TableID"] == ["999999"]:
            return self.topology_body
        if method == "GetData" and query["TableID"] == ["999998"]:
            return self.benchmark_body
        raise AssertionError("runner requested an unresolved or unbounded product")


class Phase4bLiveRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "data"
        self.review = Path(self.tmp.name) / "review"
        shutil.copytree(PACKAGE_ROOT / "config", self.root / "config")
        shutil.copytree(PACKAGE_ROOT / "evidence", self.root / "evidence")

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, transport=None, environment=None):
        return LiveBeaAcceptanceRunner(
            data_root=self.root,
            review_root=self.review,
            environment={} if environment is None else environment,
            transport=transport,
            now=lambda: "2026-08-22T12:00:00Z",
        )

    def test_absent_credential_fails_before_network_or_filesystem_mutation(self):
        called = []
        with self.assertRaisesRegex(LiveBeaBlocked, LIVE_BLOCKED):
            self.runner(transport=lambda url: called.append(url) or b"{}").run()
        self.assertEqual([], called)
        self.assertFalse((self.root / "evidence" / "bea" / "live").exists())
        self.assertFalse(self.review.exists())

    def test_cli_has_no_key_argument_and_prints_only_blocked_status(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.dict(os.environ, {}, clear=True):
            result = main(["--data-root", str(self.root), "--review-root", str(self.review)])
        self.assertEqual(2, result)
        self.assertEqual({"status": LIVE_BLOCKED}, json.loads(output.getvalue()))

    def test_live_runner_wires_metadata_data_capture_and_promotion(self):
        transport = FakeBeaTransport()
        result = self.runner(transport, {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        queries = [parse_qs(urlsplit(url).query) for url in transport.urls]
        self.assertEqual(["GetParameterValues", "GetParameterValues", "GetData", "GetData"], [row["method"][0] for row in queries])
        self.assertEqual(["TableID", "Year"], [row["ParameterName"][0] for row in queries[:2]])
        self.assertEqual(["999999", "999998"], [row["TableID"][0] for row in queries[2:]])
        self.assertEqual(14, result["acceptedRelationshipCount"])
        self.assertEqual(10, result["nodeCount"])
        self.assertEqual(0, result["structuralCalculationCount"])
        self.assertEqual("BLOCKED_STRUCTURAL_HANDOFF_UNPROVEN", result["gateBStatus"])
        self.assertFalse(result["topologyCheck"]["pathAExecutable"])
        self.assertFalse(result["topologyCheck"]["pathBExecutable"])
        self.assertEqual("NON_RECURSIVE_BENCHMARK_ONLY", result["directTotalBenchmark"]["totalRole"])
        self.assertFalse(result["directTotalBenchmark"]["includedInPropagation"])
        self.assertEqual(3, len(result["currentStateAttachments"]))
        self.assertTrue(all(row["propagationSeed"] is False for row in result["currentStateAttachments"]))
        self.assertEqual("BUFFER_AVAILABLE", result["behavioralEvidence"]["inventory"])
        self.assertEqual("HEADROOM_CONSTRAINED", result["behavioralEvidence"]["capacity"])
        self.assertEqual("BLOCKED_HANDOFF_UNPROVEN", result["commonCauseResult"]["status"])
        self.assertEqual("NOT_GENERATED", result["structuralEmploymentExposure"]["status"])
        self.assertIsNone(result["replay"]["publicBefore"])
        self.assertIsNotNone(result["replay"]["publicAtArtifactId"])

    def test_secret_is_absent_from_results_and_all_persisted_text(self):
        result = self.runner(FakeBeaTransport(), {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        self.assertNotIn(TEST_USER_ID, json.dumps(result))
        for path in list(self.review.rglob("*")) + list((self.root / "evidence" / "bea" / "live").rglob("*")):
            if path.is_file():
                self.assertNotIn(TEST_USER_ID.encode(), path.read_bytes())
        self.assertTrue(all("UserID=REDACTED" in row["requestIdentity"] for row in result["requestMetrics"]["requests"]))

    def test_transport_exception_cannot_echo_secret(self):
        def hostile(url):
            raise RuntimeError(url)
        with self.assertRaises(RuntimeError) as captured:
            self.runner(hostile, {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        self.assertNotIn(TEST_USER_ID, str(captured.exception))

    def test_live_table_ids_are_not_hard_coded_in_runner(self):
        source = (PACKAGE_ROOT / "src" / "systems_monitor_data" / "phase4b_live.py").read_text(encoding="utf-8")
        self.assertNotIn("999999", source)
        self.assertNotIn("999998", source)

    def test_metadata_ambiguity_fails_before_capture(self):
        payload = json.loads(live_fixture("bea_parameter_values_test_only.json"))
        payload["BEAAPI"]["Results"]["ParamValue"].append({"Key":"123456","Desc":"Direct Requirements, After Redefinitions (Summary)"})
        transport = FakeBeaTransport(table_body=json.dumps(payload).encode())
        with self.assertRaises(ValueError):
            self.runner(transport, {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        self.assertFalse((self.root / "evidence" / "bea" / "live").exists())

    def test_schema_drift_fails_before_capture(self):
        payload = json.loads(live_fixture("bea_direct_requirements_test_only.json"))
        del payload["BEAAPI"]["Results"]["Data"][0]["RowCode"]
        transport = FakeBeaTransport(topology_body=json.dumps(payload).encode())
        with self.assertRaises(ValueError):
            self.runner(transport, {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        self.assertFalse((self.root / "evidence" / "bea" / "live").exists())

    def test_fixture_marker_is_rejected_from_live_promotion(self):
        fixture_body = (FIXTURES / "bea_parameter_values_test_only.json").read_bytes()
        transport = FakeBeaTransport(table_body=fixture_body)
        with self.assertRaises(ValueError):
            self.runner(transport, {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        self.assertFalse((self.root / "evidence" / "bea" / "live").exists())

    def test_no_accepted_relationships_produces_no_candidate_or_calc(self):
        payload = json.loads(live_fixture("bea_direct_requirements_test_only.json"))
        for row in payload["BEAAPI"]["Results"]["Data"]:
            row["DataValue"] = "0"
        transport = FakeBeaTransport(topology_body=json.dumps(payload).encode())
        with self.assertRaises(ValueError):
            self.runner(transport, {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        self.assertFalse((self.review / "phase4b-read-model-candidate.json").exists())
        self.assertFalse((self.root / "evidence" / "bea" / "live").exists())

    def test_immutable_capture_records_source_identity(self):
        result = self.runner(FakeBeaTransport(), {"AUXSAYS_BEA_USER_ID": TEST_USER_ID}).run()
        run_record = json.loads(Path(result["runRecordPath"]).read_text())
        self.assertEqual(4, len(run_record["immutableCaptures"]))
        self.assertTrue(all(row["sha256"] and row["relative_path"].startswith("objects/") for row in run_record["immutableCaptures"]))
        self.assertTrue(all(row["metadataStatus"] == "VERIFIED_LIVE_GET_PARAMETER_VALUES" for row in run_record["sourceArtifacts"]))


if __name__ == "__main__":
    unittest.main()
