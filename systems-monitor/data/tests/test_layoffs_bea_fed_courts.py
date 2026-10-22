import copy
import io
import unittest
import zipfile
from decimal import Decimal

from _support import CONFIG, FIXTURES
from systems_monitor_data.layoffs_bea_fed_courts import (
    discover_courts_f2_xlsx_url,
    load_layoffs_bea_fed_courts_registry,
    official_source,
    parse_bea_api_response,
    parse_courts_f2_xlsx,
    parse_fed_ddp_csv,
    plan_official_intake,
    validate_g17_alltables_payload,
    validate_sloos_payload,
)


REGISTRY = CONFIG / "layoffs" / "sources_bea_fed_courts.json"


class LayoffsBeaFedCourtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_layoffs_bea_fed_courts_registry(REGISTRY)

    def test_registry_is_complete_review_only_and_preserves_semantic_boundaries(self):
        self.assertEqual(6, len(self.registry["sources"]))
        self.assertEqual("NOT_ACCEPTED_NOT_PUBLISHABLE", self.registry["publication_status"])
        courts = official_source(self.registry, "uscourts-f2")
        self.assertEqual(5, len(courts["series"]))
        self.assertEqual(
            "CONTEXT_ONLY_NOT_FIRM_DEATH_NOT_CLOSURE_NOT_LAYOFFS",
            courts["relationship_boundary"],
        )
        for source_id in ("bea-nipa", "bea-gdp-industry", "fed-h15", "fed-sloos"):
            source = official_source(self.registry, source_id)
            self.assertEqual([], source["series"])
            self.assertIn("blocked_reason", source)
        serialized = REGISTRY.read_text(encoding="utf-8")
        self.assertNotIn("UserID=", serialized)

    def test_bea_plan_is_credential_then_selector_blocked_without_leaking_secret(self):
        missing = plan_official_intake(self.registry, "bea-nipa", environment={})
        self.assertEqual("blocked", missing.health_status)
        self.assertEqual("credential_missing:AUXSAYS_BEA_USER_ID", missing.reason)
        self.assertIsNone(missing.request)

        unresolved = plan_official_intake(
            self.registry,
            "bea-nipa",
            environment={"AUXSAYS_BEA_USER_ID": "sensitive-review-id"},
        )
        self.assertEqual("exact_table_line_or_crosswalk_unresolved", unresolved.reason)
        self.assertIsNone(unresolved.request)

        amended = copy.deepcopy(self.registry)
        source = official_source(amended, "bea-nipa")
        source["selector_status"] = "VERIFIED_EXACT_TABLE_LINE"
        source["series"] = [self._bea_spec()]
        plan = plan_official_intake(
            amended,
            "bea-nipa",
            environment={"AUXSAYS_BEA_USER_ID": "sensitive-review-id"},
        )
        self.assertIsNotNone(plan.request)
        self.assertNotIn("sensitive-review-id", repr(plan.request))
        self.assertNotIn("sensitive-review-id", str(plan.request))
        self.assertNotIn("UserID", plan.request.public_identity)
        self.assertIn("UserID=sensitive-review-id", plan.request.transport_url())

    def test_bea_parser_refuses_unapproved_selectors_then_emits_nonpublishable_candidate(self):
        source = official_source(self.registry, "bea-nipa")
        kwargs = dict(
            release_id="bea-review-2026-08-27",
            artifact_sha256="a" * 64,
            retrieved_time="2026-08-27T18:00:00Z",
            provenance_url=source["endpoint"],
        )
        with self.assertRaisesRegex(ValueError, "not verified"):
            parse_bea_api_response(
                (FIXTURES / "layoffs_bea_response_minimized.json").read_bytes(),
                source,
                **kwargs,
            )

        amended = copy.deepcopy(source)
        amended["selector_status"] = "VERIFIED_EXACT_TABLE_LINE"
        amended["series"] = [self._bea_spec()]
        candidate = parse_bea_api_response(
            (FIXTURES / "layoffs_bea_response_minimized.json").read_bytes(),
            amended,
            **kwargs,
        )[0]
        self.assertEqual(Decimal("12345.6"), candidate.value)
        self.assertEqual("2026Q2", candidate.observation_period)
        self.assertIsNone(candidate.accepted_time)
        self.assertFalse(candidate.publication_eligible)

        with self.assertRaisesRegex(ValueError, "cannot contain credential"):
            parse_bea_api_response(
                (FIXTURES / "layoffs_bea_response_minimized.json").read_bytes(),
                amended,
                **{**kwargs, "provenance_url": source["endpoint"] + "?UserID=must-not-persist"},
            )

    def test_g17_is_raw_review_only_and_schema_drift_fails_closed(self):
        plan = plan_official_intake(self.registry, "fed-g17")
        self.assertEqual("RAW_REVIEW_ONLY_PENDING_RIGHTS_AND_SELECTOR_ACCEPTANCE", plan.activation_state)
        self.assertIsNotNone(plan.request)
        marker = validate_g17_alltables_payload(
            (FIXTURES / "layoffs_g17_alltables_minimized.txt").read_bytes()
        )
        self.assertEqual("g17-raw-review|year=2026", marker)
        with self.assertRaisesRegex(ValueError, "schema marker"):
            validate_g17_alltables_payload(b"Industrial Production only")

    def test_h15_and_sloos_remain_blocked_until_exact_bindings_exist(self):
        for source_id in ("fed-h15", "fed-sloos"):
            plan = plan_official_intake(self.registry, source_id)
            self.assertEqual("SOURCE_IDENTIFIED", plan.activation_state)
            self.assertEqual("blocked", plan.health_status)
            self.assertIsNone(plan.request)

        sloos = copy.deepcopy(official_source(self.registry, "fed-sloos"))
        with self.assertRaisesRegex(ValueError, "not verified"):
            validate_sloos_payload((FIXTURES / "layoffs_sloos_minimized.html").read_bytes(), sloos)
        sloos["selector_status"] = "VERIFIED_QUESTION_IDENTIFIER_AND_UNIVERSE"
        sloos["series"] = [{"question_id": "SLOOS-Q-CI-STANDARDS-LARGE"}]
        self.assertEqual(
            ("SLOOS-Q-CI-STANDARDS-LARGE",),
            validate_sloos_payload((FIXTURES / "layoffs_sloos_minimized.html").read_bytes(), sloos),
        )

    def test_federal_reserve_csv_parser_requires_exact_series_and_never_auto_accepts(self):
        source = copy.deepcopy(official_source(self.registry, "fed-h15"))
        kwargs = dict(
            release_id="h15-review-2026-08-27",
            artifact_sha256="b" * 64,
            retrieved_time="2026-08-27T20:00:00Z",
            provenance_url=source["endpoint"],
        )
        with self.assertRaisesRegex(ValueError, "not verified"):
            parse_fed_ddp_csv((FIXTURES / "layoffs_fed_ddp_minimized.csv").read_bytes(), source, **kwargs)
        source["selector_status"] = "VERIFIED_EXACT_DDP_SERIES"
        source["series"] = [
            {
                "canonical_factor": "factor:reviewed-rate-test-only",
                "source_series_id": "H15:REVIEWED_RATE",
                "label": "Reviewed rate fixture",
                "unit": "percent per year",
                "period_column": "Time Period",
                "value_column": "REVIEWED_RATE",
                "frequency": "business daily",
                "seasonal_adjustment": "not seasonally adjusted",
            }
        ]
        candidates = parse_fed_ddp_csv(
            (FIXTURES / "layoffs_fed_ddp_minimized.csv").read_bytes(), source, **kwargs
        )
        self.assertEqual(1, len(candidates))
        self.assertEqual(Decimal("5.25"), candidates[0].value)
        self.assertIsNone(candidates[0].accepted_time)
        self.assertFalse(candidates[0].publication_eligible)

    def test_courts_page_discovers_one_official_xlsx_and_rejects_ambiguity(self):
        source = official_source(self.registry, "uscourts-f2")
        url = discover_courts_f2_xlsx_url(
            (FIXTURES / "layoffs_courts_f2_page_minimized.html").read_bytes(), source["endpoint"]
        )
        self.assertEqual(
            "https://www.uscourts.gov/sites/default/files/2026-08/f-2-june-2026.xlsx",
            url,
        )
        ambiguous = b'<a href="/a/f-2.xlsx">F-2</a><a href="/b/f-2.xlsx">F-2</a>'
        with self.assertRaisesRegex(ValueError, "found 2"):
            discover_courts_f2_xlsx_url(ambiguous, source["endpoint"])

    def test_courts_xlsx_parser_selects_business_national_totals_only(self):
        source = official_source(self.registry, "uscourts-f2")
        payload = self._f2_workbook()
        candidates = parse_courts_f2_xlsx(
            payload,
            source,
            release_id="courts-f2-2026-06-30",
            artifact_sha256="c" * 64,
            retrieved_time="2026-08-27T21:00:00Z",
            dated_page_url=source["endpoint"],
        )
        self.assertEqual(5, len(candidates))
        by_id = {candidate.source_series_id: candidate for candidate in candidates}
        self.assertEqual(Decimal("22999"), by_id["F2:US:BUSINESS:ALL"].value)
        self.assertEqual(Decimal("10000"), by_id["F2:US:BUSINESS:CH11"].value)
        self.assertNotIn(Decimal("400000"), {candidate.value for candidate in candidates})
        self.assertTrue(all(candidate.observation_period == "2026-06-30" for candidate in candidates))
        self.assertTrue(all(candidate.accepted_time is None for candidate in candidates))
        self.assertTrue(all(candidate.publication_eligible is False for candidate in candidates))
        self.assertTrue(all(candidate.relationship_boundary.endswith("NOT_LAYOFFS") for candidate in candidates))

    @staticmethod
    def _bea_spec():
        return {
            "canonical_factor": "factor:reviewed-bea-concept-test-only",
            "source_series_id": "BEA:NIPA:T-REVIEWED:1:Q",
            "label": "Reviewed BEA fixture",
            "unit": "test unit",
            "dataset_name": "NIPA",
            "table_name": "T-REVIEWED",
            "line_number": "1",
            "frequency_code": "Q",
            "frequency": "quarterly",
            "seasonal_adjustment": "table-defined; fixture only",
        }

    @staticmethod
    def _f2_workbook() -> bytes:
        def cell(reference, value):
            return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'

        sheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1">{}</row>
<row r="2">{}</row>
<row r="3">{}</row>
</sheetData></worksheet>""".format(
            "".join(
                [cell("A1", "Court"), cell("B1", "Business"), cell("G1", "Nonbusiness")]
            ),
            "".join(
                [
                    cell("B2", "All Chapters"),
                    cell("C2", "Chapter 7"),
                    cell("D2", "Chapter 11"),
                    cell("E2", "Chapter 12"),
                    cell("F2", "Chapter 13"),
                    cell("G2", "All Chapters"),
                    cell("H2", "Chapter 7"),
                    cell("I2", "Chapter 11"),
                    cell("J2", "Chapter 12"),
                    cell("K2", "Chapter 13"),
                ]
            ),
            "".join(
                [
                    cell("A3", "United States"),
                    cell("B3", "22999"),
                    cell("C3", "10000"),
                    cell("D3", "10000"),
                    cell("E3", "600"),
                    cell("F3", "2399"),
                    cell("G3", "400000"),
                    cell("H3", "300000"),
                    cell("I3", "50000"),
                    cell("J3", "50"),
                    cell("K3", "49950"),
                ]
            ),
        )
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/worksheets/sheet1.xml", sheet)
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
