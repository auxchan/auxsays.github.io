import copy
import json
import unittest
from pathlib import Path

from _support import CONFIG, PACKAGE_ROOT
from systems_monitor_data.derivation import calculate, create_derivation, reproduce
from systems_monitor_data.phase4a import build_phase4a_candidate
from systems_monitor_data.state_engine import StateEngine, previous_eligible, select_as_of


REVIEW = PACKAGE_ROOT / "review" / "internal-factual-review-model.json"
PROFILE = json.loads((CONFIG / "phase4a" / "profile.json").read_text(encoding="utf-8"))
MODEL = json.loads(REVIEW.read_text(encoding="utf-8"))


class Phase4StateTests(unittest.TestCase):
    def run_state(self, metrics=None, mode="OPERATIONALLY_KNOWN_AS_OF", cutoff="2026-08-18T19:46:00Z"):
        return StateEngine(PROFILE).run(
            MODEL["metrics"] if metrics is None else metrics,
            replay_mode=mode,
            knowledge_cutoff=cutoff,
            evaluated_at="2026-08-18T19:46:00Z",
            source_snapshot_id="sha256:" + "a" * 64,
        )

    def test_current_state_has_six_authorized_observations(self):
        run = self.run_state()
        self.assertEqual(6, len(run["states"]))
        self.assertFalse(run["missingIndicators"])

    def test_public_replay_uses_public_time(self):
        selected = select_as_of(MODEL["metrics"], "PUBLICLY_AVAILABLE_AS_OF", "2026-08-05T00:00:00Z")
        self.assertEqual({"US_LABOR_JOB_OPENINGS", "US_LABOR_HIRES"}, {row["id"] for row in selected})

    def test_operational_replay_uses_accepted_time(self):
        self.assertEqual([], select_as_of(MODEL["metrics"], "OPERATIONALLY_KNOWN_AS_OF", "2026-08-18T19:45:59Z"))

    def test_future_publication_does_not_leak(self):
        selected = select_as_of(MODEL["metrics"], "PUBLICLY_AVAILABLE_AS_OF", "2026-08-06T23:59:59Z")
        self.assertNotIn("US_LABOR_TOTAL_NONFARM_PAYROLLS", {row["id"] for row in selected})

    def test_rights_blocked_observation_is_ineligible(self):
        metrics = copy.deepcopy(MODEL["metrics"])
        metrics[0]["rightsState"] = "DENY"
        self.assertEqual(5, len(self.run_state(metrics)["states"]))

    def test_mixed_frequency_is_preserved(self):
        states = self.run_state()["states"]
        self.assertEqual({"weekly", "monthly"}, {row["frequency"] for row in states})

    def test_carry_forward_does_not_change_observation_period(self):
        state = next(row for row in self.run_state()["states"] if row["sourceSeriesId"] == "JTS000000000000000JOL")
        self.assertTrue(state["carriedForward"])
        self.assertEqual("2026-06", state["observationPeriod"])

    def test_age_and_source_health_are_separate(self):
        state = next(row for row in self.run_state()["states"] if row["sourceSeriesId"] == "DOL-UI-SA-INITIAL")
        self.assertEqual("current", state["freshness"])
        self.assertEqual("stale", state["retrievalPathHealth"])
        self.assertGreaterEqual(state["ageDays"], 0)

    def test_deterministic_state_run(self):
        self.assertEqual(self.run_state()["stateRunId"], self.run_state()["stateRunId"])

    def test_state_run_records_required_context(self):
        run = self.run_state()
        for field in ("stateRunId", "engineVersion", "configurationVersion", "sourceSnapshotId", "replayMode", "knowledgeCutoff", "evaluatedAt", "geography", "rightsDecisionSet"):
            self.assertIn(field, run)

    def test_source_values_remain_obs_and_not_auxsays_calculated(self):
        for state in self.run_state()["states"]:
            self.assertEqual("OBS", state["stateType"])
            self.assertEqual("NONE", state["auxsaysCalculation"])

    def test_unknown_replay_mode_fails(self):
        with self.assertRaises(ValueError):
            select_as_of(MODEL["metrics"], "LATEST", "2026-08-18T19:46:00Z")

    def test_unauthorized_indicator_fails(self):
        metrics = copy.deepcopy(MODEL["metrics"])
        metrics[0]["id"] = "US_OUTPUT_REAL_GDP"
        with self.assertRaises(ValueError):
            self.run_state(metrics)

    def test_missing_baseline_is_explicit_none(self):
        self.assertIsNone(previous_eligible(MODEL["metrics"], MODEL["metrics"][0]["id"], "2026-07", "OPERATIONALLY_KNOWN_AS_OF", "2026-08-18T19:46:00Z"))

    def test_previous_eligible_reference_uses_retained_period(self):
        rows = copy.deepcopy(MODEL["metrics"][:1])
        prior = copy.deepcopy(rows[0]); prior["observationPeriod"] = "2026-06"; prior["value"] = "158000"
        rows.append(prior)
        self.assertEqual("2026-06", previous_eligible(rows, rows[0]["id"], "2026-07", "OPERATIONALLY_KNOWN_AS_OF", "2026-08-18T19:46:00Z")["observationPeriod"])


class Phase4DerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = build_phase4a_candidate(review_model_path=REVIEW, config_root=CONFIG)

    def test_calculated_states_are_calc(self):
        self.assertTrue(all(row["stateType"] == "CALC" for row in self.candidate["calculatedStates"]))

    def test_every_calc_has_reproducible_derivation(self):
        for record in self.candidate["derivations"]:
            self.assertEqual(record["output"]["value"], reproduce(record))

    def test_direct_mapping_baseline_is_not_applicable(self):
        self.assertTrue(all(row["baseline"]["status"] == "NOT_APPLICABLE_DIRECT_STATE_MAPPING" for row in self.candidate["derivations"]))

    def test_invalid_output_fails(self):
        source = self.candidate["stateRun"]["states"][0]
        output = {"stateId": "calc:1", "value": "999", "unit": source["unit"]}
        with self.assertRaises(ValueError):
            create_derivation(calculation_id="x", calculation_version="1", algorithm_id="DIRECT_IDENTITY_V1", configuration_version="1", source_snapshot_id="s", replay_mode="OPERATIONALLY_KNOWN_AS_OF", knowledge_cutoff="2026-08-18T19:46:00Z", inputs=[source], output=output, baseline=None, relationship_refs=[])

    def test_mutated_derivation_identity_fails(self):
        record = copy.deepcopy(self.candidate["derivations"][0])
        record["configurationVersion"] = "changed"
        with self.assertRaises(ValueError):
            reproduce(record)

    def test_unallowlisted_formula_fails(self):
        with self.assertRaises(ValueError):
            calculate("__import__('os').system('whoami')", [{"value": "1"}])

    def test_difference_requires_baseline(self):
        source = self.candidate["stateRun"]["states"][0]
        output = {"stateId": "calc:1", "value": "1", "unit": source["unit"]}
        with self.assertRaises(ValueError):
            create_derivation(calculation_id="x", calculation_version="1", algorithm_id="DIFFERENCE_V1", configuration_version="1", source_snapshot_id="s", replay_mode="OPERATIONALLY_KNOWN_AS_OF", knowledge_cutoff="2026-08-18T19:46:00Z", inputs=[source, {**source, "stateId": "prior", "value": str(float(source["value"]) - 1)}], output=output, baseline=None, relationship_refs=[])

    def test_candidate_identity_is_deterministic(self):
        other = build_phase4a_candidate(review_model_path=REVIEW, config_root=CONFIG)
        self.assertEqual(self.candidate["candidateId"], other["candidateId"])


if __name__ == "__main__":
    unittest.main()
