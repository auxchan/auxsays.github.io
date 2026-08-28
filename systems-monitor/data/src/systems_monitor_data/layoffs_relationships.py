from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LIFECYCLES = {"CANDIDATE", "VALIDATED", "ACCEPTED", "SUPERSEDED", "INVALIDATED"}
EVIDENCE_CLASSES = {"DIRECT", "STRUCTURAL", "STATISTICAL", "MODELED", "HYPOTHESIS"}
RELATIONSHIP_TYPES = {"ACCOUNTING_DEFINITIONAL", "STATISTICAL", "MODELED_EXPOSURE", "RESEARCH_HYPOTHESIS"}


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def hierarchy_counts(taxonomy: dict[str, Any]) -> dict[str, int]:
    groups = taxonomy.get("groups", [])
    return {
        "outcomeToLevel1": 1,
        "level1ToLevel2": len(groups),
        "level2ToLevel3": sum(len(group.get("placements", [])) for group in groups),
    }


def validate_registry(registry: dict[str, Any]) -> dict[str, int]:
    seen: set[tuple[str, str]] = set()
    counts = {"CANDIDATE": 0, "VALIDATED": 0, "ACCEPTED": 0}
    for edge in registry.get("relationships", []):
        identity = (edge.get("edgeId", ""), edge.get("version", ""))
        if not all(identity) or identity in seen:
            raise ValueError("duplicate or incomplete relationship identity")
        seen.add(identity)
        required = {
            "sourceNode", "targetNode", "direction", "polarity", "relationshipType",
            "plainLanguageMechanism", "geography", "effectiveFrom", "definitionVersion",
            "lifecycle", "knowledgeEligibility", "publicationEligibility", "evidenceClass",
            "quality", "coverage", "calibration", "regime", "evidenceRefs",
            "sourceDataset", "sourceTable", "classificationIdentity", "crosswalkVersion",
            "derivationRule", "acceptanceRule", "approvalState",
        }
        if not required.issubset(edge):
            raise ValueError(f"relationship is incomplete: {identity[0]}")
        if edge["sourceNode"] == edge["targetNode"] or edge["geography"] != "US":
            raise ValueError(f"invalid relationship endpoints/geography: {identity[0]}")
        if edge["lifecycle"] not in LIFECYCLES or edge["relationshipType"] not in RELATIONSHIP_TYPES:
            raise ValueError(f"invalid lifecycle/type: {identity[0]}")
        if edge["evidenceClass"] not in EVIDENCE_CLASSES:
            raise ValueError(f"invalid evidence class: {identity[0]}")
        if edge["lifecycle"] == "ACCEPTED" and edge["approvalState"] != "ACCEPTED":
            raise ValueError(f"accepted lifecycle lacks approval: {identity[0]}")
        counts[edge["lifecycle"]] = counts.get(edge["lifecycle"], 0) + 1
    return counts


def traversable(edge: dict[str, Any]) -> bool:
    return (
        edge.get("lifecycle") == "ACCEPTED"
        and edge.get("approvalState") == "ACCEPTED"
        and edge.get("publicationEligibility") == "ELIGIBLE"
    )


def relationship_summary(registry: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    lifecycles = validate_registry(registry)
    classes: dict[str, int] = {}
    for edge in registry["relationships"]:
        classes[edge["relationshipType"]] = classes.get(edge["relationshipType"], 0) + 1
    return {
        "hierarchy": hierarchy_counts(taxonomy),
        "semanticByType": classes,
        "lifecycle": lifecycles,
        "traversableCount": sum(traversable(edge) for edge in registry["relationships"]),
    }
