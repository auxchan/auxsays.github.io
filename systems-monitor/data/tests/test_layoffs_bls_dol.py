import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from _support import CONFIG, FIXTURES
from systems_monitor_data.layoffs_bls_dol import (
    BlsDolLayoffsCollector,
    collect_layoffs_bls_dol_candidates,
    load_layoffs_bls_dol_registry,
    parse_bls_api_response,
    parse_dol_national_xml,
)


REGISTRY = CONFIG / "layoffs" / "sources_bls_dol.json"


class LayoffsBlsDolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acquisition, cls.specs = load_layoffs_bls_dol_registry(REGISTRY)

    def test_registry_has_reviewed_exact_series_and_no_credentials(self):
        self.assertEqual(19, len(self.specs))
        ids = {spec.series_id for spec in self.specs}
        self.assertIn("JTS000000000000000LDL", ids)
        self.assertIn("LNS13026638", ids)
        self.assertIn("LNS13023653", ids)
        self.assertIn("CES0500000002", ids)
        self.assertIn("BDS0000000000000000110004LQ5", ids)
        self.assertIn("BDS0000000000000000110005LQ5", ids)
        self.assertIn("BDS0000000000000000110006LQ5", ids)
        self.assertIn("DOL-UI-SA-CONTINUED", ids)
        self.assertEqual(5, len(json.loads(REGISTRY.read_text(encoding="utf-8"))["source_profiles"]))
        initial = next(spec for spec in self.specs if spec.series_id == "DOL-UI-SA-INITIAL")
        self.assertIn("every new retrieval remains pending acceptance", initial.existing_acceptance_scope)
        serialized = REGISTRY.read_text(encoding="utf-8").lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("registrationkey", serialized)

    def test_bls_parser_preserves_period_unit_adjustment_and_preliminary_marker(self):
        wanted = {
            "JTS000000000000000LDL",
            "LNS13026638",
            "CES0500000002",
            "BDS0000000000000000110004LQ5",
            "BDS0000000000000000110008LQ5",
        }
        specs = [spec for spec in self.specs if spec.series_id in wanted]
        batch = parse_bls_api_response(
            (FIXTURES / "layoffs_bls_response_minimized.json").read_bytes(),
            specs,
            release_id="bls-release-2026-08-27",
            artifact_sha256="a" * 64,
            retrieved_time="2026-08-27T15:00:00Z",
            accepted_time="2026-08-27T15:00:01Z",
            provenance_url="https://api.bls.gov/publicAPI/v2/timeseries/data/",
        )
        self.assertEqual(6, len(batch.observations))
        self.assertEqual(1, batch.skipped_missing_values)
        layoffs = next(row for row in batch.observations if row.source_series_id.endswith("LDL") and row.observation_period == "2026-06")
        self.assertEqual(Decimal("1766"), layoffs.value)
        self.assertEqual("thousands of persons", layoffs.unit)
        self.assertEqual("seasonally adjusted", layoffs.seasonal_adjustment)
        self.assertEqual("preliminary", layoffs.revision_status)
        bed = next(row for row in batch.observations if row.source_series_id.endswith("0004LQ5"))
        self.assertEqual("2025-Q4", bed.observation_period)
        self.assertEqual("thousands of jobs", bed.unit)
        death = next(row for row in batch.observations if row.source_series_id.endswith("0008LQ5"))
        self.assertEqual("2025-Q1", death.observation_period)
        self.assertEqual(Decimal("809"), death.value)

    def test_bls_parser_rejects_omitted_or_duplicate_series(self):
        payload = json.loads((FIXTURES / "layoffs_bls_response_minimized.json").read_text(encoding="utf-8"))
        specs = [spec for spec in self.specs if spec.series_id in {"LNS13026638", "CES0500000002"}]
        payload["Results"]["series"] = [payload["Results"]["series"][1]]
        with self.assertRaisesRegex(ValueError, "omitted"):
            parse_bls_api_response(json.dumps(payload).encode(), specs, release_id="R1", artifact_sha256="b" * 64, retrieved_time="2026-08-27T15:00:00Z", accepted_time="2026-08-27T15:00:01Z", provenance_url=self.acquisition["bls"]["endpoint"])

    def test_dol_parser_emits_three_independent_series_without_blank_fallback(self):
        specs = [spec for spec in self.specs if spec.source_id == "dol-ui-claims"]
        batch = parse_dol_national_xml(
            (FIXTURES / "layoffs_dol_xml_minimized.xml").read_bytes(),
            specs,
            release_id="dol-ui-release-2026-08-27",
            artifact_sha256="c" * 64,
            retrieved_time="2026-08-27T15:00:00Z",
            accepted_time="2026-08-27T15:00:01Z",
            provenance_url=self.acquisition["dol_ui"]["endpoint"],
        )
        self.assertEqual(3, len(batch.observations))
        self.assertEqual(3, batch.skipped_missing_values)
        by_id = {row.source_series_id: row for row in batch.observations}
        self.assertEqual(Decimal("200000"), by_id["DOL-UI-SA-INITIAL"].value)
        self.assertEqual(Decimal("1781000"), by_id["DOL-UI-SA-CONTINUED"].value)
        self.assertEqual(Decimal("1.2"), by_id["DOL-UI-SA-IUR"].value)
        self.assertEqual({"2026-08-01"}, {row.observation_period for row in batch.observations})
        self.assertTrue(all(row.publication_time_kind == "conservative_retrieval_bound" for row in batch.observations))

    def test_future_official_publication_time_is_rejected(self):
        spec = next(spec for spec in self.specs if spec.series_id == "LNS13026638")
        payload = json.loads((FIXTURES / "layoffs_bls_response_minimized.json").read_text(encoding="utf-8"))
        payload["Results"]["series"] = [payload["Results"]["series"][1]]
        with self.assertRaisesRegex(ValueError, "cannot follow retrieval"):
            parse_bls_api_response(
                json.dumps(payload).encode(),
                [spec],
                release_id="R1",
                artifact_sha256="e" * 64,
                retrieved_time="2026-08-27T15:00:00Z",
                accepted_time=None,
                provenance_url=self.acquisition["bls"]["endpoint"],
                official_publication_time="2026-08-28T15:00:00Z",
            )

    def test_exact_retry_is_stable_but_new_release_is_a_new_vintage(self):
        spec = next(spec for spec in self.specs if spec.series_id == "LNS13026638")
        payload = json.loads((FIXTURES / "layoffs_bls_response_minimized.json").read_text(encoding="utf-8"))
        payload["Results"]["series"] = [payload["Results"]["series"][1]]
        kwargs = dict(artifact_sha256="d" * 64, retrieved_time="2026-08-27T15:00:00Z", accepted_time="2026-08-27T15:00:01Z", provenance_url=self.acquisition["bls"]["endpoint"])
        first = parse_bls_api_response(json.dumps(payload).encode(), [spec], release_id="R1", **kwargs).observations[0]
        retry = parse_bls_api_response(json.dumps(payload).encode(), [spec], release_id="R1", **kwargs).observations[0]
        revised = parse_bls_api_response(json.dumps(payload).encode(), [spec], release_id="R2", **kwargs).observations[0]
        self.assertEqual(first.observation_id, retry.observation_id)
        self.assertNotEqual(first.observation_id, revised.observation_id)

    def test_collector_builds_one_bounded_bls_request_for_all_sixteen_series(self):
        calls = []

        class FakeRetriever:
            def fetch(self, url, **kwargs):
                calls.append((url, kwargs))
                return "artifact"

        collector = BlsDolLayoffsCollector(self.acquisition, retriever=FakeRetriever())
        bls_specs = [spec for spec in self.specs if spec.source_id != "dol-ui-claims"]
        self.assertEqual("artifact", collector.retrieve_bls(bls_specs, 2025, 2026))
        body = json.loads(calls[0][1]["body"])
        self.assertEqual(16, len(body["seriesid"]))
        self.assertEqual("2025", body["startyear"])
        self.assertEqual("2026", body["endyear"])

    def test_runner_writes_raw_evidence_and_non_publishable_candidates(self):
        bls = (FIXTURES / "layoffs_bls_response_minimized.json").read_bytes()
        dol = (FIXTURES / "layoffs_dol_xml_minimized.xml").read_bytes()

        class FakeCollector:
            def retrieve_bls(self, specs, start_year, end_year):
                document = {"status": "REQUEST_SUCCEEDED", "message": [], "Results": {"series": []}}
                for spec in specs:
                    period = "Q04" if spec.frequency == "quarterly" else "M07"
                    value = "1.2" if spec.unit == "percent" else "100"
                    document["Results"]["series"].append({
                        "seriesID": spec.series_id,
                        "data": [{"year": "2025" if spec.frequency == "quarterly" else "2026", "period": period, "value": value, "footnotes": [{}]}],
                    })
                body = json.dumps(document).encode()
                from systems_monitor_data.retrieval import RetrievedArtifact
                return RetrievedArtifact(body, "application/json", self.bls_url, "2026-08-27T15:00:00Z", 1, 1)

            def retrieve_dol(self, year):
                from systems_monitor_data.retrieval import RetrievedArtifact
                return RetrievedArtifact(dol, "text/xml", self.dol_url, "2026-08-27T15:00:00Z", 1, 1)

            bls_url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
            dol_url = "https://oui.doleta.gov/unemploy/wkclaims/report.asp"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = collect_layoffs_bls_dol_candidates(
                registry_path=REGISTRY,
                raw_root=root / "raw",
                candidate_path=root / "candidate.json",
                start_year=2025,
                end_year=2026,
                collector=FakeCollector(),
            )
            self.assertEqual("NOT_ACCEPTED_NOT_PUBLISHABLE", result["activationStatus"])
            self.assertTrue((root / "candidate.json").exists())
            self.assertEqual(2, len(result["rawArtifacts"]))
            self.assertTrue(all(row["accepted_time"] is None for row in result["candidates"]))
            self.assertTrue(all(row["publication_eligible"] is False for row in result["candidates"]))
            self.assertTrue(all(row["activation_state"] == "SOURCE_ENABLED_PENDING_ACCEPTANCE" for row in result["candidates"]))


if __name__ == "__main__":
    unittest.main()
