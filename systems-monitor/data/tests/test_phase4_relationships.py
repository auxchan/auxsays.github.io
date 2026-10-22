import copy
import json
import unittest

from _support import CONFIG
from systems_monitor_data.relationships import can_traverse, promote_relationships, relationship_as_of, supersede


DEFINITIONS = json.loads((CONFIG / "phase4a" / "relationships.json").read_text(encoding="utf-8"))
RULES = json.loads((CONFIG / "phase4a" / "acceptance_rules.json").read_text(encoding="utf-8"))


class Phase4RelationshipTests(unittest.TestCase):
    def test_deterministic_rules_promote_six_direct_mappings(self):
        accepted, events = promote_relationships(DEFINITIONS, RULES)
        self.assertEqual(6, len(accepted))
        self.assertEqual(12, len(events))
        self.assertTrue(all(row["lifecycle"] == "ACCEPTED" for row in accepted))

    def test_candidate_cannot_traverse(self):
        self.assertFalse(can_traverse(DEFINITIONS["relationships"][0]))

    def test_validated_cannot_traverse(self):
        edge = copy.deepcopy(DEFINITIONS["relationships"][0]); edge["lifecycle"] = "VALIDATED"
        self.assertFalse(can_traverse(edge))

    def test_accepted_can_traverse(self):
        edge = promote_relationships(DEFINITIONS, RULES)[0][0]
        self.assertTrue(can_traverse(edge, "2026-08-19T00:00:00Z"))

    def test_superseded_cannot_traverse(self):
        edge = supersede(promote_relationships(DEFINITIONS, RULES)[0][0])
        self.assertFalse(can_traverse(edge))

    def test_invalidated_cannot_traverse(self):
        edge = promote_relationships(DEFINITIONS, RULES)[0][0]; edge["lifecycle"] = "INVALIDATED"
        self.assertFalse(can_traverse(edge))

    def test_historical_version_eligibility(self):
        edge = promote_relationships(DEFINITIONS, RULES)[0][0]
        self.assertIsNone(relationship_as_of([edge], edge["edgeId"], "2026-08-18T23:59:59Z"))
        self.assertEqual(edge["version"], relationship_as_of([edge], edge["edgeId"], "2026-08-19T00:00:00Z")["version"])

    def test_record_cannot_self_promote_outside_rule(self):
        definitions = copy.deepcopy(DEFINITIONS)
        definitions["relationships"][0]["targetNode"] = "labor-state:unauthorized"
        definitions["relationships"][0]["lifecycle"] = "ACCEPTED"
        with self.assertRaises(ValueError):
            promote_relationships(definitions, RULES)

    def test_unsupported_causal_semantics_fail(self):
        definitions = copy.deepcopy(DEFINITIONS)
        definitions["relationships"][0]["relationshipType"] = "CAUSES"
        with self.assertRaises(ValueError):
            promote_relationships(definitions, RULES)

    def test_incompatible_geography_fails(self):
        definitions = copy.deepcopy(DEFINITIONS); definitions["relationships"][0]["geography"] = "CA"
        with self.assertRaises(ValueError):
            promote_relationships(definitions, RULES)

    def test_identity_mapping_cannot_change_units(self):
        definitions = copy.deepcopy(DEFINITIONS); definitions["relationships"][0]["targetUnit"] = "percent"
        with self.assertRaises(ValueError):
            promote_relationships(definitions, RULES)

    def test_duplicate_relationship_version_fails(self):
        definitions = copy.deepcopy(DEFINITIONS); definitions["relationships"].append(copy.deepcopy(definitions["relationships"][0]))
        with self.assertRaises(ValueError):
            promote_relationships(definitions, RULES)

    def test_optional_numeric_semantics_remain_absent(self):
        edge = promote_relationships(DEFINITIONS, RULES)[0][0]
        for field in ("elasticity", "transmissionWeight", "numericLag", "capacity", "substitutionCoefficient"):
            self.assertNotIn(field, edge)


if __name__ == "__main__":
    unittest.main()
