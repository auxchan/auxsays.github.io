from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import parse_utc


LIFECYCLE = {"CANDIDATE", "VALIDATED", "ACCEPTED", "SUPERSEDED", "INVALIDATED"}
TRAVERSABLE = {"ACCEPTED"}
ALLOWED_TYPES = {"DIRECT_SEMANTIC_MAPPING", "SYNTHETIC_MECHANICS_FIXTURE"}
ALLOWED_EVIDENCE = {"DIRECT", "AUTHORITATIVE_STRUCTURAL", "TEST_FIXTURE"}


def _rule_map(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["ruleId"]: row for row in rules.get("rules", [])}


def validate_candidate(edge: dict[str, Any], rule: dict[str, Any]) -> None:
    required = {
        "edgeId", "version", "sourceNode", "targetNode", "direction",
        "polarity", "relationshipType", "mechanism", "geography",
        "effectiveFrom", "evidenceClass", "quality", "coverage",
        "calibration", "lifecycle", "evidenceRefs", "acceptanceRuleId",
        "sourceUnit", "targetUnit", "stateFamily",
    }
    if not required.issubset(edge):
        raise ValueError("relationship is incomplete")
    if edge["lifecycle"] != "CANDIDATE" or edge["relationshipType"] not in ALLOWED_TYPES:
        raise ValueError("relationship has invalid candidate lifecycle or type")
    if edge["evidenceClass"] not in ALLOWED_EVIDENCE:
        raise ValueError("relationship evidence class is invalid")
    if edge["geography"] != "US" or edge["sourceNode"] == edge["targetNode"]:
        raise ValueError("relationship geography or identity is invalid")
    if any(word in edge["relationshipType"].upper() for word in ("CAUSE", "CAUSAL")):
        raise ValueError("unsupported causal relationship")
    parse_utc(edge["effectiveFrom"])
    pair = [edge["sourceNode"], edge["targetNode"]]
    if edge["acceptanceRuleId"] != rule.get("ruleId") or pair not in rule.get("allowedPairs", []):
        raise ValueError("relationship is not covered by the external acceptance rule")
    for field in ("relationshipType", "evidenceClass", "calibration", "geography"):
        if edge[field] != rule.get(field):
            raise ValueError(f"relationship does not satisfy acceptance rule: {field}")
    if edge["calibration"] == "NONE_IDENTITY_ONLY" and edge["sourceUnit"] != edge["targetUnit"]:
        raise ValueError("identity mapping cannot change units")


def promote_relationships(definitions: dict[str, Any], rules: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(definitions.get("relationships", [])) not in range(4, 9):
        raise ValueError("Phase-4A requires 4–8 bounded relationships")
    rule_by_id = _rule_map(rules)
    accepted: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in sorted(definitions["relationships"], key=lambda row: (row["edgeId"], row["version"])):
        identity = (source["edgeId"], source["version"])
        if identity in seen:
            raise ValueError("duplicate relationship version")
        seen.add(identity)
        rule = rule_by_id.get(source.get("acceptanceRuleId"))
        if rule is None:
            raise ValueError("acceptance rule does not exist")
        validate_candidate(source, rule)
        validated = deepcopy(source)
        validated["lifecycle"] = "VALIDATED"
        events.append({"edgeId": source["edgeId"], "version": source["version"], "from": "CANDIDATE", "to": "VALIDATED", "ruleId": rule["ruleId"]})
        promoted = deepcopy(validated)
        promoted["lifecycle"] = "ACCEPTED"
        promoted["acceptedAt"] = rule["acceptedAt"]
        promoted["acceptanceAuthority"] = rule["authority"]
        events.append({"edgeId": source["edgeId"], "version": source["version"], "from": "VALIDATED", "to": "ACCEPTED", "ruleId": rule["ruleId"]})
        accepted.append(promoted)
    return accepted, events


def relationship_as_of(versions: list[dict[str, Any]], edge_id: str, cutoff: str) -> dict[str, Any] | None:
    cutoff_time = parse_utc(cutoff)
    eligible = [
        row for row in versions
        if row.get("edgeId") == edge_id
        and row.get("lifecycle") == "ACCEPTED"
        and parse_utc(row["effectiveFrom"]) <= cutoff_time
        and parse_utc(row["acceptedAt"]) <= cutoff_time
    ]
    return sorted(eligible, key=lambda row: (row["effectiveFrom"], row["version"]))[-1] if eligible else None


def can_traverse(edge: dict[str, Any], cutoff: str | None = None) -> bool:
    if edge.get("lifecycle") not in TRAVERSABLE:
        return False
    if cutoff is None:
        return True
    cutoff_time = parse_utc(cutoff)
    return parse_utc(edge["effectiveFrom"]) <= cutoff_time and parse_utc(edge["acceptedAt"]) <= cutoff_time


def supersede(edge: dict[str, Any]) -> dict[str, Any]:
    if edge.get("lifecycle") != "ACCEPTED":
        raise ValueError("only accepted relationships can be superseded")
    result = deepcopy(edge)
    result["lifecycle"] = "SUPERSEDED"
    return result
