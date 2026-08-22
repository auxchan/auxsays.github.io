import copy
import json
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from _support import CONFIG, FIXTURES, PACKAGE_ROOT, fixture
from systems_monitor_data.bea_crosswalk import CrosswalkError, inspect_bea_concordance, validate_downstream_484_bridge
from systems_monitor_data.bea_io import (
    BeaApiError, BeaInputOutputClient, BeaRequestBudget, parse_input_output_data,
    parse_parameter_values, redact_bea_url, resolve_table_id, resolve_year,
)
from systems_monitor_data.structural import (
    StructuralValidationError, generate_structural_candidates,
    promote_structural_candidates, validate_product_roles,
)
from systems_monitor_data.retrieval import BoundedRetriever


class BeaInputOutputTests(unittest.TestCase):
    def test_credential_is_validated_and_redacted(self):
        with self.assertRaises(BeaApiError):
            BeaInputOutputClient("secret", lambda _: b"{}")
        url = "https://apps.bea.gov/api/data?UserID=123&method=GetData"
        self.assertNotIn("123", redact_bea_url(url))

    def test_metadata_uses_get_parameter_values(self):
        calls = []
        body = (FIXTURES / "bea_parameter_values_test_only.json").read_bytes()
        client = BeaInputOutputClient("00000000-0000-0000-0000-000000000000", lambda url: calls.append(url) or body)
        values, logged_url = client.parameter_values("TableID")
        self.assertIn("method=GetParameterValues", calls[0])
        self.assertIn("ParameterName=TableID", calls[0])
        self.assertNotIn("00000000", logged_url)
        self.assertEqual("999999", resolve_table_id(values, ("Direct Requirements", "After Redefinitions", "Summary")).key)

    def test_year_is_resolved_from_metadata(self):
        values = parse_parameter_values((FIXTURES / "bea_year_values_test_only.json").read_bytes())
        self.assertEqual("2024", resolve_year(values, "2024").key)
        with self.assertRaises(BeaApiError):
            resolve_year(values, "2019")

    def test_parser_preserves_namespaces_and_missing_is_not_zero(self):
        cells = parse_input_output_data(
            (FIXTURES / "bea_direct_requirements_test_only.json").read_bytes(),
            expected_table_id="999999", expected_year="2024", expected_unit="Coefficient",
        )
        self.assertEqual("COMMODITY", cells[0].row_namespace)
        self.assertEqual("INDUSTRY", cells[0].column_namespace)
        self.assertNotEqual("COMMODITY:211", "INDUSTRY:211")
        malformed = {"BEAAPI": {"Results": {"Data": [{"TableID":"999999","Year":"2024","Unit":"Coefficient","RowCode":"211","RowDescr":"Oil","ColCode":"484","ColDescr":"Truck","DataValue":"--"}]}}}
        with self.assertRaisesRegex(BeaApiError, "missing is not zero"):
            parse_input_output_data(json.dumps(malformed).encode(), expected_table_id="999999", expected_year="2024", expected_unit="Coefficient")

    def test_parser_rejects_identity_drift_and_hostile_values(self):
        source = fixture("bea_direct_requirements_test_only.json")
        source["BEAAPI"]["Results"]["Data"][0]["Year"] = "2023"
        with self.assertRaises(BeaApiError):
            parse_input_output_data(json.dumps(source).encode(), expected_table_id="999999", expected_year="2024", expected_unit="Coefficient")

    def test_http_429_honors_bounded_retry_after(self):
        headers = Message(); headers["Retry-After"] = "7"
        error = urllib.error.HTTPError("https://apps.bea.gov/api/data", 429, "rate", headers, None)
        sleeps = []
        retriever = BoundedRetriever(max_attempts=2, sleeper=sleeps.append)
        with patch.object(retriever, "_request", side_effect=error), self.assertRaises(RuntimeError):
            retriever.fetch("https://apps.bea.gov/api/data", expected_types=("application/json",))
        self.assertEqual([7], sleeps)

    def test_bea_request_and_error_budgets_fail_closed(self):
        budget = BeaRequestBudget(clock=lambda: 1000.0)
        for _ in range(100):
            budget.begin_request()
        with self.assertRaisesRegex(BeaApiError, "request-per-minute"):
            budget.begin_request()
        errors = BeaRequestBudget(clock=lambda: 1000.0)
        for _ in range(30):
            errors.record_result(0, failed=True)
        with self.assertRaisesRegex(BeaApiError, "error-per-minute"):
            errors.record_result(0, failed=True)
        source = fixture("bea_direct_requirements_test_only.json")
        source["BEAAPI"]["Results"]["Data"][0]["DataValue"] = {"not": "numeric"}
        with self.assertRaises(BeaApiError):
            parse_input_output_data(json.dumps(source).encode(), expected_table_id="999999", expected_year="2024", expected_unit="Coefficient")


class BeaCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = PACKAGE_ROOT / "evidence" / "bea" / "BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx"
        cls.evidence = inspect_bea_concordance(
            cls.path,
            source_url="https://www.bea.gov/sites/default/files/2023-10/BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx",
            allowed_summary_codes={"211", "22", "324", "484", "486", "493"},
        )

    def test_official_workbook_is_bounded_and_non_executable(self):
        self.assertEqual("2017_NAICS", self.evidence.naics_vintage)
        self.assertFalse(self.evidence.macros_present)
        self.assertFalse(self.evidence.formulas_present)
        self.assertFalse(self.evidence.external_links_present)

    def test_downstream_bridge_is_versioned_and_exact(self):
        bridge = json.loads((CONFIG / "phase4b" / "naics_bridge_484.json").read_text())
        record = validate_downstream_484_bridge(self.evidence, bridge)
        self.assertEqual("484", record["employmentNaicsCode"])
        self.assertEqual("ONE_TO_ONE_UNCHANGED_AGGREGATE", record["mappingType"])
        bad = copy.deepcopy(bridge); bad["targetCode"] = "486"
        with self.assertRaises(CrosswalkError):
            validate_downstream_484_bridge(self.evidence, bad)


class StructuralGenerationTests(unittest.TestCase):
    def setUp(self):
        self.cells = parse_input_output_data(
            (FIXTURES / "bea_direct_requirements_test_only.json").read_bytes(),
            expected_table_id="999999", expected_year="2024", expected_unit="Coefficient",
        )
        self.rule = json.loads((CONFIG / "phase4b" / "acceptance_rule.json").read_text())
        self.artifact = {
            "sourceArtifactId":"bea:live:test", "metadataStatus":"VERIFIED_LIVE_GET_PARAMETER_VALUES",
            "tableId":"999999", "productToken":"CxIDRAR", "year":"2024", "aggregation":"SUMMARY_71",
            "redefinitionBasis":"AFTER_REDEFINITIONS", "priceBasis":"PRODUCERS_PRICES", "unit":"Coefficient",
            "rightsState":"ALLOW_WITH_ATTRIBUTION_AND_TERMS_FINGERPRINT", "schemaHash":"sha256:schema",
            "contentHash":"sha256:content", "crosswalkVersion":"crosswalk:1", "publicReleaseTime":"2025-09-30T12:30:00Z",
        }

    def test_total_product_cannot_be_recursive(self):
        validate_product_roles({"topologyProduct":"CxIDRAR","totalRequirementsProduct":"IxCTRAR","totalRequirementsRole":"NON_RECURSIVE_BENCHMARK_ONLY","includeTotalInPropagation":False})
        with self.assertRaises(StructuralValidationError):
            validate_product_roles({"topologyProduct":"CxIDRAR","totalRequirementsProduct":"IxCTRAR","totalRequirementsRole":"RECURSIVE","includeTotalInPropagation":True})

    def test_live_metadata_is_required_for_auto_acceptance(self):
        bad = copy.deepcopy(self.artifact); bad["metadataStatus"] = "TEST_FIXTURE"
        with self.assertRaises(StructuralValidationError):
            generate_structural_candidates(self.cells, artifact=bad, rule=self.rule)

    def test_generation_and_promotion_are_deterministic_and_bounded(self):
        candidates, rejected = generate_structural_candidates(self.cells, artifact=self.artifact, rule=self.rule)
        accepted, events = promote_structural_candidates(candidates, self.rule)
        self.assertEqual(14, len(accepted))
        self.assertEqual(28, len(events))
        self.assertFalse(rejected)
        self.assertTrue(all(row["lifecycle"] == "ACCEPTED" for row in accepted))
        self.assertTrue(any(row["sourceNode"] == "bea:commodity:324" and row["targetNode"] == "bea:industry:484" for row in accepted))
        again, _ = generate_structural_candidates(self.cells, artifact=self.artifact, rule=self.rule)
        self.assertEqual([row["edgeId"] for row in candidates], [row["edgeId"] for row in again])


if __name__ == "__main__":
    unittest.main()
