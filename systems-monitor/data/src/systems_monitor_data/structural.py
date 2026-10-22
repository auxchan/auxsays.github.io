from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from .bea_io import BeaCell
from .derivation import stable_id


APPROVED_CODES = {"211", "22", "324", "484", "486", "493"}
REQUIRED_CORE_CODES = {"211", "22", "324", "484"}


class StructuralValidationError(ValueError):
    pass


def validate_product_roles(configuration: dict[str, Any]) -> None:
    if configuration.get("topologyProduct") != "CxIDRAR":
        raise StructuralValidationError("CxIDRAR is the only approved topology product")
    if configuration.get("totalRequirementsProduct") != "IxCTRAR":
        raise StructuralValidationError("IxCTRAR is the required total benchmark")
    if configuration.get("totalRequirementsRole") != "NON_RECURSIVE_BENCHMARK_ONLY":
        raise StructuralValidationError("total requirements must remain non-recursive")
    if configuration.get("includeTotalInPropagation") is not False:
        raise StructuralValidationError("direct traversal plus total-requirements contribution is prohibited")


def generate_structural_candidates(
    cells: list[BeaCell],
    *,
    artifact: dict[str, Any],
    rule: dict[str, Any],
    allowed_codes: set[str] = APPROVED_CODES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    required_artifact = {
        "sourceArtifactId", "metadataStatus", "tableId", "productToken", "year",
        "aggregation", "redefinitionBasis", "priceBasis", "unit", "rightsState",
        "schemaHash", "contentHash", "crosswalkVersion", "publicReleaseTime",
    }
    if not required_artifact.issubset(artifact):
        raise StructuralValidationError("BEA artifact identity is incomplete")
    if artifact["metadataStatus"] != "VERIFIED_LIVE_GET_PARAMETER_VALUES":
        raise StructuralValidationError("accepted generation requires live GetParameterValues metadata")
    if artifact["productToken"] != "CxIDRAR" or artifact["year"] != "2024":
        raise StructuralValidationError("artifact is outside approved O-008 product/year")
    if artifact["rightsState"] != "ALLOW_WITH_ATTRIBUTION_AND_TERMS_FINGERPRINT":
        raise StructuralValidationError("artifact rights do not permit relationship generation")
    if not str(artifact["tableId"]).isdigit():
        raise StructuralValidationError("artifact TableID was not resolved live")
    if rule.get("ruleId") != "BEA_CXIDRAR_ENERGY_2024_V1" or rule.get("authority") != "TAYLOR_O008":
        raise StructuralValidationError("structural acceptance rule is not approved")
    threshold = Decimal(str(rule.get("minimumDirectCoefficient", "0")))
    candidates = []
    rejected = []
    for cell in sorted(cells, key=lambda row: (row.row_code, row.column_code, row.identity)):
        reason = None
        if cell.table_id != str(artifact["tableId"]) or cell.year != artifact["year"]:
            reason = "SOURCE_IDENTITY_MISMATCH"
        elif cell.row_code not in allowed_codes or cell.column_code not in allowed_codes:
            reason = "OUTSIDE_APPROVED_BOUND"
        elif cell.row_namespace != "COMMODITY" or cell.column_namespace != "INDUSTRY":
            reason = "NAMESPACE_MISMATCH"
        elif Decimal(cell.value) < threshold:
            reason = "BELOW_APPROVED_MATERIALITY"
        if reason:
            rejected.append({"sourceCellIdentity": cell.identity, "reason": reason})
            continue
        core = {
            "sourceCellIdentity": cell.identity,
            "sourceArtifactId": artifact["sourceArtifactId"],
            "sourceCommodityNode": f"bea:commodity:{cell.row_code}",
            "targetIndustryNode": f"bea:industry:{cell.column_code}",
            "directCoefficient": cell.value,
            "tableId": artifact["tableId"],
            "productToken": artifact["productToken"],
            "economicYear": artifact["year"],
            "crosswalkVersion": artifact["crosswalkVersion"],
            "acceptanceRuleVersion": rule["version"],
        }
        candidates.append({
            "edgeId": stable_id("structural-edge", core),
            "version": "1.0.0",
            "sourceNode": core["sourceCommodityNode"],
            "targetNode": core["targetIndustryNode"],
            "direction": "INPUT_TO_DIRECTLY_CONSUMING_INDUSTRY",
            "polarity": "POSITIVE_REQUIREMENT",
            "relationshipType": "AUTHORITATIVE_DIRECT_REQUIREMENT",
            "mechanism": "BEA_DIRECT_REQUIREMENT_PER_DOLLAR_OUTPUT",
            "geography": "US",
            "effectiveFrom": artifact["publicReleaseTime"],
            "evidenceClass": "AUTHORITATIVE_STRUCTURAL",
            "quality": "OFFICIAL_ORIGINAL_AUTHORITY",
            "coverage": "BOUNDED_ENERGY_SLICE",
            "calibration": "DIRECT_REQUIREMENT_COEFFICIENT",
            "lifecycle": "CANDIDATE",
            "evidenceRefs": [artifact["sourceArtifactId"], cell.identity],
            "acceptanceRuleId": rule["ruleId"],
            "acceptanceRuleVersion": rule["version"],
            "sourceUnit": "STRUCTURAL_PRESSURE_INDEX",
            "targetUnit": "STRUCTURAL_PRESSURE_INDEX",
            "stateFamily": "STRUCTURAL_PRESSURE",
            "directCoefficient": cell.value,
            "sourceTableId": artifact["tableId"],
            "sourceProduct": artifact["productToken"],
            "economicYear": artifact["year"],
            "sourceCellIdentity": cell.identity,
            "relationshipVersion": "1.0.0",
            "crosswalkVersion": artifact["crosswalkVersion"],
            "rightsState": artifact["rightsState"],
            "provenance": {
                "authority": "U.S. Bureau of Economic Analysis",
                "sourceArtifactId": artifact["sourceArtifactId"],
                "schemaHash": artifact["schemaHash"],
                "contentHash": artifact["contentHash"],
            },
        })
    return candidates, rejected


def promote_structural_candidates(candidates: list[dict[str, Any]], rule: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 12 <= len(candidates) <= 40:
        raise StructuralValidationError("accepted structural slice must contain 12–40 relationships")
    accepted = []
    events = []
    seen = set()
    for candidate in candidates:
        identity = (candidate["edgeId"], candidate["version"])
        if identity in seen:
            raise StructuralValidationError("duplicate structural relationship")
        seen.add(identity)
        if candidate["lifecycle"] != "CANDIDATE" or candidate["acceptanceRuleId"] != rule["ruleId"]:
            raise StructuralValidationError("candidate is outside the approved rule")
        if candidate["relationshipType"] != "AUTHORITATIVE_DIRECT_REQUIREMENT" or candidate["evidenceClass"] != "AUTHORITATIVE_STRUCTURAL":
            raise StructuralValidationError("candidate is not authoritative direct structure")
        validated = deepcopy(candidate)
        validated["lifecycle"] = "VALIDATED"
        events.append({"edgeId": candidate["edgeId"], "from": "CANDIDATE", "to": "VALIDATED", "ruleId": rule["ruleId"]})
        promoted = deepcopy(validated)
        promoted["lifecycle"] = "ACCEPTED"
        promoted["acceptedAt"] = rule["acceptedAt"]
        promoted["acceptanceAuthority"] = rule["authority"]
        events.append({"edgeId": candidate["edgeId"], "from": "VALIDATED", "to": "ACCEPTED", "ruleId": rule["ruleId"]})
        accepted.append(promoted)
    nodes = {node for edge in accepted for node in (edge["sourceNode"], edge["targetNode"])}
    if not 8 <= len(nodes) <= 20:
        raise StructuralValidationError("accepted structural node count is outside the approved bound")
    if not all(any(code in edge["sourceNode"] or code in edge["targetNode"] for edge in accepted) for code in REQUIRED_CORE_CODES):
        raise StructuralValidationError("accepted structural slice lacks an approved core code")
    return accepted, events


def evidence_backed_behavior(*, inventory: dict[str, Any], capacity: dict[str, Any], lag: dict[str, Any], substitution: dict[str, Any]) -> dict[str, Any]:
    records = [inventory, capacity, lag, substitution]
    if not all(row.get("stateType") == "OBS" and row.get("authority") and row.get("evidenceUrl") for row in records):
        raise StructuralValidationError("behavioral adjustment requires complete official OBS evidence")
    if inventory.get("assessment") not in {"BUFFER_AVAILABLE", "BUFFER_CONSTRAINED", "UNKNOWN"}:
        raise StructuralValidationError("inventory assessment is invalid")
    if capacity.get("assessment") not in {"HEADROOM_AVAILABLE", "HEADROOM_CONSTRAINED", "UNKNOWN"}:
        raise StructuralValidationError("capacity assessment is invalid")
    if lag.get("assessment") not in {"ORDINAL_DELAY", "NO_OBSERVED_DELAY", "UNKNOWN_NOT_ZERO"}:
        raise StructuralValidationError("lag assessment is invalid")
    if substitution.get("assessment") not in {"PROVEN_SUBSTITUTE", "NO_PROVEN_SUBSTITUTE", "UNKNOWN"}:
        raise StructuralValidationError("substitution assessment is invalid")
    return {
        "behaviorVersion": "phase4b-evidence-backed-behavior-1.0.0",
        "inventory": inventory["assessment"],
        "capacity": capacity["assessment"],
        "lag": lag["assessment"],
        "substitution": substitution["assessment"],
        "numericAttenuation": None,
        "transmissionBound": "UNQUANTIFIED_ORDINAL",
        "evidenceRefs": [row["stateId"] for row in records],
    }
