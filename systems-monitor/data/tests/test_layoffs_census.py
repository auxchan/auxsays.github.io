import json
import unittest
from decimal import Decimal

from _support import CONFIG, FIXTURES
from systems_monitor_data.layoffs_census import (
    CensusArtifact,
    collect_census_candidates,
    census_source,
    load_layoffs_census_registry,
    parse_census_payload,
    plan_census_collection,
)


REGISTRY = CONFIG / "layoffs" / "sources_census.json"


class LayoffsCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_layoffs_census_registry(REGISTRY)

    def test_registry_has_six_programs_and_only_verified_selectors_activate(self):
        sources = {row["source_id"]: row for row in self.registry["sources"]}
        self.assertEqual(
            {"census-bds", "census-bfs", "census-marts", "census-m3", "census-mtis", "census-ftd"},
            set(sources),
        )
        self.assertEqual("AUXSAYS_CENSUS_API_KEY", self.registry["credential_environment_variable"])
        self.assertEqual(7, len(sources["census-bds"]["series"]))
        self.assertEqual("BF_BF4Q", sources["census-bfs"]["series"][0]["selector"]["category_code"])
        self.assertEqual("IMP", sources["census-ftd"]["series"][0]["selector"]["data_type_code"])
        for source_id in ("census-marts", "census-m3", "census-mtis"):
            self.assertEqual("UNRESOLVED_OFFICIAL_METADATA_JOIN", sources[source_id]["selector_status"])
            self.assertEqual([], sources[source_id]["series"])
        self.assertNotIn("super-secret", REGISTRY.read_text(encoding="utf-8"))

    def test_missing_credential_blocks_before_request_or_transport(self):
        plan = plan_census_collection(self.registry, "census-bds", "2023", environment={})
        self.assertEqual("SOURCE_IDENTIFIED", plan.activation_state)
        self.assertEqual("blocked", plan.health_status)
        self.assertEqual("credential_missing:AUXSAYS_CENSUS_API_KEY", plan.reason)
        self.assertIsNone(plan.request)

        class NeverCalled:
            def fetch(self, request):
                raise AssertionError("transport must not run without a credential")

        result = collect_census_candidates(
            self.registry,
            "census-bds",
            "2023",
            release_id="bds-2023",
            environment={},
            transport=NeverCalled(),
        )
        self.assertEqual((), result.candidates)
        self.assertIsNone(result.artifact_sha256)

    def test_unresolved_eits_selector_remains_blocked_even_with_credential(self):
        for source_id in ("census-marts", "census-m3", "census-mtis"):
            plan = plan_census_collection(
                self.registry,
                source_id,
                "2026-07",
                environment={"AUXSAYS_CENSUS_API_KEY": "super-secret"},
            )
            self.assertEqual("SOURCE_IDENTIFIED", plan.activation_state)
            self.assertEqual("official_selector_unresolved", plan.reason)
            self.assertIsNone(plan.request)

    def test_request_keeps_credential_ephemeral_and_out_of_identity_and_repr(self):
        plan = plan_census_collection(
            self.registry,
            "census-bds",
            "2023",
            environment={"AUXSAYS_CENSUS_API_KEY": "super-secret"},
        )
        self.assertEqual("SOURCE_ENABLED_PENDING_ACCEPTANCE", plan.activation_state)
        self.assertIsNotNone(plan.request)
        self.assertNotIn("super-secret", plan.request.public_identity)
        self.assertNotIn("super-secret", repr(plan.request))
        self.assertNotIn("key=", plan.request.public_identity.lower())
        self.assertIn("key=super-secret", plan.request.sensitive_url_for_transport())

    def test_bds_collection_preserves_exact_variables_periods_and_nonaccepted_boundary(self):
        payload = (FIXTURES / "layoffs_census_bds_minimized.json").read_bytes()

        class FixtureTransport:
            def fetch(self, request):
                self.public_identity = request.public_identity
                return CensusArtifact(payload, "application/json", request.public_identity, "2026-08-28T10:00:00Z")

        transport = FixtureTransport()
        result = collect_census_candidates(
            self.registry,
            "census-bds",
            "2023",
            release_id="census-bds-vintage-2026-08-28",
            environment={"AUXSAYS_CENSUS_API_KEY": "super-secret"},
            transport=transport,
        )
        self.assertEqual("SOURCE_ENABLED_PENDING_ACCEPTANCE", result.activation_state)
        self.assertEqual(13, len(result.candidates))
        self.assertNotIn("super-secret", transport.public_identity)
        latest = next(
            row for row in result.candidates
            if row.source_series_id == "JOB_DESTRUCTION_DEATHS" and row.observation_period == "2023"
        )
        self.assertEqual(Decimal("3800000"), latest.value)
        self.assertEqual("jobs", latest.unit)
        self.assertEqual("not seasonally adjusted", latest.seasonal_adjustment)
        self.assertEqual("US", latest.geography)
        self.assertIsNone(latest.accepted_time)
        self.assertFalse(latest.publication_eligible)
        self.assertEqual("SOURCE_ENABLED_PENDING_ACCEPTANCE", latest.activation_state)
        self.assertTrue(all(row.value != Decimal("0") for row in result.candidates))
        self.assertFalse(any(row.source_series_id == "FIRMDEATH_EMP" and row.observation_period == "2022" for row in result.candidates))

    def test_bfs_and_ftd_exact_official_selectors_are_filtered_without_conflation(self):
        bfs = parse_census_payload(
            (FIXTURES / "layoffs_census_bfs_minimized.json").read_bytes(),
            census_source(self.registry, "census-bfs"),
            release_id="bfs-2026-07",
            artifact_sha256="a" * 64,
            retrieved_time="2026-08-28T10:00:00Z",
            provenance_url="https://api.census.gov/data/timeseries/eits/bfs",
        )
        self.assertEqual(1, len(bfs))
        self.assertEqual("BFS:T:BF_BF4Q:SA", bfs[0].source_series_id)
        self.assertEqual("factor:business-formations-four-quarters", bfs[0].canonical_factor)
        self.assertEqual(Decimal("31500"), bfs[0].value)

        ftd = parse_census_payload(
            (FIXTURES / "layoffs_census_ftd_minimized.json").read_bytes(),
            census_source(self.registry, "census-ftd"),
            release_id="ftd-2026-06",
            artifact_sha256="b" * 64,
            retrieved_time="2026-08-28T10:00:00Z",
            provenance_url="https://api.census.gov/data/timeseries/eits/ftd",
        )
        self.assertEqual(1, len(ftd))
        self.assertEqual("FTD:IMP:BOPGS:SA", ftd[0].source_series_id)
        self.assertEqual(Decimal("371200"), ftd[0].value)
        self.assertEqual("millions of dollars", ftd[0].unit)

    def test_bds_schema_drift_and_wrong_geography_fail_closed(self):
        payload = json.loads((FIXTURES / "layoffs_census_bds_minimized.json").read_text(encoding="utf-8"))
        payload[0].remove("JOB_DESTRUCTION_DEATHS")
        for row in payload[1:]:
            del row[2]
        with self.assertRaisesRegex(ValueError, "omitted"):
            parse_census_payload(
                json.dumps(payload).encode(),
                census_source(self.registry, "census-bds"),
                release_id="R1",
                artifact_sha256="c" * 64,
                retrieved_time="2026-08-28T10:00:00Z",
                provenance_url="https://api.census.gov/data/timeseries/bds",
            )

        payload = json.loads((FIXTURES / "layoffs_census_bds_minimized.json").read_text(encoding="utf-8"))
        payload[1][-1] = "2"
        with self.assertRaisesRegex(ValueError, "U.S. annual geography"):
            parse_census_payload(
                json.dumps(payload).encode(),
                census_source(self.registry, "census-bds"),
                release_id="R1",
                artifact_sha256="d" * 64,
                retrieved_time="2026-08-28T10:00:00Z",
                provenance_url="https://api.census.gov/data/timeseries/bds",
            )

    def test_release_vintages_do_not_overwrite_identity(self):
        source = census_source(self.registry, "census-bfs")
        kwargs = dict(
            payload=(FIXTURES / "layoffs_census_bfs_minimized.json").read_bytes(),
            source=source,
            artifact_sha256="e" * 64,
            retrieved_time="2026-08-28T10:00:00Z",
            provenance_url="https://api.census.gov/data/timeseries/eits/bfs",
        )
        first = parse_census_payload(release_id="R1", **kwargs)[0]
        retry = parse_census_payload(release_id="R1", **kwargs)[0]
        revised = parse_census_payload(release_id="R2", **kwargs)[0]
        self.assertEqual(first.observation_id, retry.observation_id)
        self.assertNotEqual(first.observation_id, revised.observation_id)
        self.assertEqual(first.observation_period, revised.observation_period)


if __name__ == "__main__":
    unittest.main()
