import copy
import json
import unittest

from _support import CONFIG, PACKAGE_ROOT
from systems_monitor_data.phase4a import build_phase4a_candidate
from systems_monitor_data.read_model import build_master_read_model


REVIEW = PACKAGE_ROOT / "review" / "internal-factual-review-model.json"


class Phase4ReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = build_phase4a_candidate(review_model_path=REVIEW, config_root=CONFIG)
        cls.model = cls.candidate["masterReadModel"]

    def test_public_safe_read_model_exists(self):
        self.assertEqual("phase4a_master_read_model_candidate", self.model["artifactClass"])
        self.assertEqual("LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED", self.model["activationStatus"])

    def test_coverage_is_limited_engine_proof(self):
        self.assertEqual("LIMITED_ENGINE_PROOF", self.model["structuralCoverageState"])
        self.assertIn("not Gate-B evidence", self.model["coverageWarning"])

    def test_unsupported_domains_are_explicit(self):
        self.assertIn("industry-structure", self.model["unsupportedDomains"])
        self.assertIn("occupation-demand", self.model["unsupportedDomains"])

    def test_obs_and_calc_are_visible(self):
        self.assertEqual({"OBS", "CALC"}, {row["stateType"] for row in self.model["stateComponents"]})
        self.assertEqual(6, len([row for row in self.model["stateComponents"] if row["stateType"] == "OBS"]))
        self.assertEqual(6, len([row for row in self.model["stateComponents"] if row["stateType"] == "CALC"]))

    def test_no_forecast_or_scenario(self):
        self.assertEqual(["FCST", "SCEN"], self.model["claimClassesAbsent"])
        self.assertEqual([], self.candidate["forecasts"])
        self.assertEqual([], self.candidate["scenarios"])

    def test_derivation_references_are_available(self):
        self.assertEqual(6, len(self.model["derivationRefs"]))
        self.assertTrue(all(row.get("derivationRef") for row in self.model["stateComponents"] if row["stateType"] == "CALC"))

    def test_obs_read_model_preserves_three_evidence_layers(self):
        observations = [row for row in self.model["stateComponents"] if row["stateType"] == "OBS"]
        self.assertEqual(6, len(observations))
        for row in observations:
            self.assertTrue(row["acquisitionProvenanceUrl"].startswith("https://"))
            self.assertTrue(row["evidenceUrl"].startswith("https://"))
            self.assertTrue(row["methodologyUrl"].startswith("https://"))

    def test_bls_read_model_opens_exact_series_page(self):
        for row in self.model["stateComponents"]:
            if row["stateType"] == "OBS" and "api.bls.gov" in row["acquisitionProvenanceUrl"]:
                self.assertTrue(row["evidenceUrl"].startswith("https://data.bls.gov/timeseries/"))
                self.assertNotEqual(row["acquisitionProvenanceUrl"], row["evidenceUrl"])

    def test_relationship_counts_are_accurate(self):
        self.assertEqual(6, self.model["acceptedRelationshipCount"])
        self.assertEqual(0, self.model["candidateRelationshipCount"])

    def test_stale_retrieval_path_is_degraded_not_hidden(self):
        self.assertEqual("DEGRADED_SOURCE_PATH", self.model["degradedState"])

    def test_no_internal_storage_or_secret_fields(self):
        serialized = json.dumps(self.model).lower()
        for forbidden in ("sqlite", "api_key", "password", "authorization", "localpath"):
            self.assertNotIn(forbidden, serialized)

    def test_relationship_label_cannot_escape_serialization(self):
        relationships = copy.deepcopy(self.candidate["acceptedRelationships"])
        relationships[0]["mechanism"] = "<script>raise SystemExit</script>\n../../secret"
        model = build_master_read_model(
            state_run=self.candidate["stateRun"], calculated_states=self.candidate["calculatedStates"],
            derivations=self.candidate["derivations"], accepted_relationships=relationships,
            candidate_count=0, propagation_run=self.candidate["propagationRun"], profile=self.candidate["profile"],
        )
        self.assertEqual(6, model["acceptedRelationshipCount"])

    def test_source_label_is_encoded_as_data(self):
        state_run = copy.deepcopy(self.candidate["stateRun"])
        state_run["states"][0]["label"] = "<img src=x onerror=alert(1)>"
        model = build_master_read_model(
            state_run=state_run, calculated_states=self.candidate["calculatedStates"], derivations=self.candidate["derivations"],
            accepted_relationships=self.candidate["acceptedRelationships"], candidate_count=0,
            propagation_run=self.candidate["propagationRun"], profile=self.candidate["profile"],
        )
        self.assertIn("&lt;img", model["stateComponents"][0]["label"])

    def test_candidate_is_deterministic_across_platform_paths(self):
        other = build_phase4a_candidate(review_model_path=REVIEW.resolve(), config_root=CONFIG.resolve())
        self.assertEqual(self.candidate["candidateId"], other["candidateId"])

    def test_recurring_cost_is_zero(self):
        self.assertEqual(0, self.model["recurringInfrastructureCostUsd"])


if __name__ == "__main__":
    unittest.main()
