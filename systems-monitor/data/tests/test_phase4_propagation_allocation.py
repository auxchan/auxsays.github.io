import copy
import json
import unittest
from decimal import Decimal

from _support import CONFIG
from systems_monitor_data.allocation import allocate
from systems_monitor_data.propagation import PropagationEngine, apply_fixture_mechanics, detect_cycle, reconcile_common_causes
from systems_monitor_data.relationships import promote_relationships


PROFILE = json.loads((CONFIG / "phase4a" / "profile.json").read_text(encoding="utf-8"))
DEFINITIONS = json.loads((CONFIG / "phase4a" / "relationships.json").read_text(encoding="utf-8"))
RULES = json.loads((CONFIG / "phase4a" / "acceptance_rules.json").read_text(encoding="utf-8"))
ACCEPTED = promote_relationships(DEFINITIONS, RULES)[0]


def edge(edge_id, source, target, unit="claims", family="claims"):
    return {
        "edgeId": edge_id, "version": "1.0.0", "sourceNode": source,
        "targetNode": target, "sourceUnit": unit, "targetUnit": unit,
        "stateFamily": family, "lifecycle": "ACCEPTED",
        "effectiveFrom": "2026-08-19T00:00:00Z", "acceptedAt": "2026-08-19T00:00:00Z",
        "polarity": "UNKNOWN_NOT_APPLICABLE", "evidenceClass": "TEST_FIXTURE",
    }


def seed(node="a", value="10", unit="claims"):
    return {"stateId": "seed:1", "nodeId": node, "value": value, "unit": unit}


def run(edges, seeds=None, profile=None):
    return PropagationEngine(profile or PROFILE).run(
        seeds or [seed()], edges, replay_mode="OPERATIONALLY_KNOWN_AS_OF",
        knowledge_cutoff="2026-08-19T00:00:00Z", source_snapshot_id="sha256:test",
    )


class Phase4PropagationTests(unittest.TestCase):
    def test_one_edge(self):
        result = run([edge("e1", "a", "b")])
        self.assertEqual(1, result["traversalCount"])
        self.assertEqual("TRANSMITTED", result["contributions"][0]["outcome"])

    def test_multiple_edges_have_deterministic_path_order(self):
        edges = [edge("e2", "a", "c"), edge("e1", "a", "b")]
        result = run(edges)
        self.assertEqual(["b", "c"], [row["targetNode"] for row in result["contributions"]])

    def test_candidate_edge_cannot_traverse(self):
        candidate = edge("e1", "a", "b"); candidate["lifecycle"] = "CANDIDATE"
        self.assertEqual(0, run([candidate])["traversalCount"])

    def test_max_depth_stops_chain(self):
        profile = copy.deepcopy(PROFILE); profile["maxDepth"] = 1
        result = run([edge("e1", "a", "b"), edge("e2", "b", "c")], profile=profile)
        self.assertEqual(1, result["traversalCount"])
        self.assertIn("max_depth", result["stopReasons"])

    def test_max_rounds_stops_chain(self):
        profile = copy.deepcopy(PROFILE); profile["maxDepth"] = 3; profile["maxRounds"] = 1
        result = run([edge("e1", "a", "b"), edge("e2", "b", "c")], profile=profile)
        self.assertEqual(1, result["traversalCount"])
        self.assertIn("max_rounds", result["stopReasons"])

    def test_contribution_budget(self):
        profile = copy.deepcopy(PROFILE); profile["budgets"]["maxContributions"] = 1
        result = run([edge("e1", "a", "b"), edge("e2", "a", "c")], profile=profile)
        self.assertIn("contribution_budget", result["stopReasons"])

    def test_materiality_is_family_specific(self):
        result = run([edge("e1", "a", "b", family="claims")], [seed(value="0")])
        self.assertEqual(0, result["traversalCount"])
        self.assertIn("below_materiality", result["stopReasons"])

    def test_incompatible_units_stop(self):
        bad = edge("e1", "a", "b"); bad["targetUnit"] = "percent"
        result = run([bad])
        self.assertEqual(0, result["traversalCount"])
        self.assertIn("incompatible_units", result["stopReasons"])

    def test_same_period_cycle_is_rejected(self):
        edges = [edge("e1", "a", "b"), edge("e2", "b", "a")]
        self.assertTrue(detect_cycle(edges))
        self.assertEqual(["cycle_rejected"], run(edges)["stopReasons"])

    def test_actual_six_mapping_graph_terminates(self):
        seeds = [{"stateId": f"s:{i}", "nodeId": row["sourceNode"], "value": "10", "unit": row["sourceUnit"]} for i, row in enumerate(ACCEPTED)]
        result = run(ACCEPTED, seeds)
        self.assertEqual(6, result["traversalCount"])
        self.assertEqual(1, result["maxDepthReached"])

    def test_common_cause_overlap_remains_explicit(self):
        rows = [
            {"originStateId": "o1", "commonCauseId": "c1", "targetNode": "t", "pathId": "p1", "value": "5"},
            {"originStateId": "o1", "commonCauseId": "c1", "targetNode": "t", "pathId": "p2", "value": "-2"},
        ]
        group = reconcile_common_causes(rows)["groups"][0]
        self.assertEqual("UNRESOLVED_EXPLICIT_NO_NAIVE_SUM", group["overlapDisposition"])
        self.assertEqual(["5"], group["positiveComponents"])
        self.assertEqual(["-2"], group["negativeComponents"])

    def test_fixture_label_is_required(self):
        with self.assertRaises(ValueError):
            apply_fixture_mechanics("10", {"outcome": "BLOCKED"})

    def test_blocked_fixture(self):
        self.assertEqual("0", self.mechanics("BLOCKED")["transmitted"])

    def test_absorbed_fixture(self):
        self.assertEqual("0", self.mechanics("ABSORBED")["transmitted"])

    def test_partially_absorbed_fixture(self):
        self.assertEqual("6", self.mechanics("PARTIALLY_ABSORBED", absorbed="4")["transmitted"])

    def test_delayed_fixture(self):
        self.assertEqual("0", self.mechanics("DELAYED", lagState="KNOWN_DELAY")["transmitted"])

    def test_transmitted_fixture(self):
        self.assertEqual("10", self.mechanics("TRANSMITTED")["transmitted"])

    def test_amplified_fixture(self):
        self.assertEqual("15.0", self.mechanics("AMPLIFIED", fixtureFactor="1.5")["transmitted"])

    def test_unknown_buffer_and_lag_remain_unknown(self):
        result = self.mechanics("TRANSMITTED")
        self.assertEqual("UNKNOWN", result["bufferState"])
        self.assertEqual("UNKNOWN", result["lagState"])

    def test_substitute_states_are_explicit(self):
        for value in ("AVAILABLE", "CAPACITY_LIMITED", "NONE"):
            self.assertEqual(value, self.mechanics("TRANSMITTED", substituteState=value)["substituteState"])

    def test_capacity_states_are_explicit(self):
        for value in ("FINITE", "EXHAUSTED"):
            self.assertEqual(value, self.mechanics("TRANSMITTED", capacityState=value)["capacityState"])

    def mechanics(self, outcome, **extra):
        return apply_fixture_mechanics("10", {"fixtureClass": "ENGINE_MECHANICS_TEST_NOT_REAL_ECONOMIC_EVIDENCE", "outcome": outcome, **extra})


class Phase4AllocationTests(unittest.TestCase):
    def test_conservation_and_residual(self):
        result = allocate("10", [{"id": "a", "quantity": "4"}])
        self.assertEqual("6", result["residual"])
        total = sum((Decimal(result[k]) for k in ("allocated", "absorbed", "residual")), Decimal("0"))
        self.assertEqual(Decimal(result["supply"]), total)

    def test_insufficient_supply_is_partial(self):
        result = allocate("5", [{"id": "a", "quantity": "4"}, {"id": "b", "quantity": "4"}])
        self.assertEqual("PARTIAL", result["status"])
        self.assertEqual("3", result["unmet"])

    def test_excess_supply_has_residual(self):
        self.assertEqual("7", allocate("10", [{"id": "a", "quantity": "3"}])["residual"])

    def test_limited_capacity_is_absorbed(self):
        result = allocate("10", [{"id": "a", "quantity": "6"}], capacity="5")
        self.assertEqual("5", result["absorbed"])
        self.assertEqual("1", result["unmet"])

    def test_partial_allocation_is_deterministic(self):
        result = allocate("5", [{"id": "b", "quantity": "4"}, {"id": "a", "quantity": "4"}])
        self.assertEqual(["a", "b"], [row["id"] for row in result["allocations"]])
        self.assertEqual("4", result["allocations"][0]["allocated"])

    def test_unknown_input_behavior(self):
        self.assertEqual("UNKNOWN_INPUT", allocate(None, [{"id": "a", "quantity": "1"}])["status"])


if __name__ == "__main__":
    unittest.main()
