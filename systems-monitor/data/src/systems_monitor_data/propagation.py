from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal, InvalidOperation
from typing import Any

from .derivation import stable_id
from .relationships import can_traverse


OUTCOMES = {"BLOCKED", "ABSORBED", "PARTIALLY_ABSORBED", "DELAYED", "AMPLIFIED", "TRANSMITTED"}


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise ValueError("propagation value must be decimal") from error


def detect_cycle(relationships: list[dict[str, Any]]) -> bool:
    graph: dict[str, list[str]] = defaultdict(list)
    for edge in relationships:
        if edge.get("lifecycle") == "ACCEPTED":
            graph[edge["sourceNode"]].append(edge["targetNode"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in sorted(graph[node])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(graph))


def apply_fixture_mechanics(value: Any, mechanics: dict[str, Any]) -> dict[str, str]:
    if mechanics.get("fixtureClass") != "ENGINE_MECHANICS_TEST_NOT_REAL_ECONOMIC_EVIDENCE":
        raise ValueError("behavioral mechanics require an explicit synthetic-fixture label")
    outcome = mechanics.get("outcome")
    if outcome not in OUTCOMES:
        raise ValueError("unknown transmission outcome")
    source = _decimal(value)
    if outcome in {"BLOCKED", "ABSORBED", "DELAYED"}:
        transmitted = Decimal("0")
    elif outcome == "PARTIALLY_ABSORBED":
        absorbed = _decimal(mechanics.get("absorbed", 0))
        transmitted = max(Decimal("0"), source - absorbed)
    elif outcome == "AMPLIFIED":
        factor = _decimal(mechanics.get("fixtureFactor"))
        if factor <= 1:
            raise ValueError("amplifier fixture factor must exceed one")
        transmitted = source * factor
    else:
        transmitted = source
    return {
        "outcome": outcome,
        "input": str(source),
        "transmitted": str(transmitted),
        "bufferState": mechanics.get("bufferState", "UNKNOWN"),
        "substituteState": mechanics.get("substituteState", "UNKNOWN"),
        "lagState": mechanics.get("lagState", "UNKNOWN"),
        "capacityState": mechanics.get("capacityState", "UNKNOWN"),
    }


def reconcile_common_causes(contributions: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in contributions:
        key = (row["originStateId"], row.get("commonCauseId") or row["originStateId"], row["targetNode"])
        groups[key].append(row)
    reconciled = []
    for key in sorted(groups):
        rows = groups[key]
        unique_paths = {row["pathId"] for row in rows}
        values = [_decimal(row["value"]) for row in rows]
        reconciled.append({
            "originStateId": key[0],
            "commonCauseId": key[1],
            "targetNode": key[2],
            "pathIds": sorted(unique_paths),
            "positiveComponents": [str(value) for value in values if value > 0],
            "negativeComponents": [str(value) for value in values if value < 0],
            "overlapDisposition": "UNRESOLVED_EXPLICIT_NO_NAIVE_SUM" if len(unique_paths) > 1 else "SINGLE_PATH",
        })
    return {"version": "common-cause-reconciliation-1.0.0", "groups": reconciled}


class PropagationEngine:
    def __init__(self, profile: dict[str, Any]):
        self.profile = profile

    def run(
        self,
        seeds: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        *,
        replay_mode: str,
        knowledge_cutoff: str,
        source_snapshot_id: str,
    ) -> dict[str, Any]:
        accepted = [edge for edge in relationships if can_traverse(edge, knowledge_cutoff)]
        if detect_cycle(accepted):
            return self._empty_run(seeds, accepted, replay_mode, knowledge_cutoff, source_snapshot_id, "cycle_rejected")
        outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in accepted:
            outgoing[edge["sourceNode"]].append(edge)
        for edges in outgoing.values():
            edges.sort(key=lambda row: (row["edgeId"], row["version"]))
        queue = deque()
        for seed in sorted(seeds, key=lambda row: row["stateId"]):
            queue.append((seed, 0, 0, [], seed["stateId"], seed.get("commonCauseId") or seed["stateId"]))
        contributions: list[dict[str, Any]] = []
        stop_reasons: set[str] = set()
        paths: set[str] = set()
        nodes = {row["nodeId"] for row in seeds}
        rounds_used = 0
        max_depth = 0
        while queue:
            state, depth, round_number, path_edges, origin_id, common_cause_id = queue.popleft()
            rounds_used = max(rounds_used, round_number)
            max_depth = max(max_depth, depth)
            if depth >= self.profile["maxDepth"]:
                if outgoing.get(state["nodeId"]):
                    stop_reasons.add("max_depth")
                continue
            if round_number >= self.profile["maxRounds"]:
                stop_reasons.add("max_rounds")
                continue
            for edge in outgoing.get(state["nodeId"], []):
                if edge["sourceUnit"] != state["unit"] or edge["targetUnit"] != edge["sourceUnit"]:
                    stop_reasons.add("incompatible_units")
                    continue
                value = _decimal(state["value"])
                if edge.get("calibration") == "DIRECT_REQUIREMENT_COEFFICIENT":
                    coefficient = _decimal(edge.get("directCoefficient"))
                    if coefficient < 0:
                        stop_reasons.add("invalid_direct_coefficient")
                        continue
                    transmitted_value = value * coefficient
                    disposition = "BEA_DIRECT_REQUIREMENT_COEFFICIENT"
                elif edge.get("calibration") == "NONE_IDENTITY_ONLY" or (
                    edge.get("calibration") is None and edge.get("evidenceClass") == "TEST_FIXTURE"
                ):
                    transmitted_value = value
                    disposition = "TEST_FIXTURE_IDENTITY_MAPPING" if edge.get("calibration") is None else "DIRECT_IDENTITY_MAPPING"
                else:
                    stop_reasons.add("unsupported_calibration")
                    continue
                threshold = _decimal(self.profile["materiality"]["thresholds"][edge["stateFamily"]])
                if abs(transmitted_value) < threshold:
                    stop_reasons.add("below_materiality")
                    continue
                new_path_edges = [*path_edges, f"{edge['edgeId']}@{edge['version']}"]
                path_id = stable_id("path", {"origin": origin_id, "edges": new_path_edges})
                contribution = {
                    "contributionId": stable_id("contribution", {"pathId": path_id, "target": edge["targetNode"], "value": str(transmitted_value)}),
                    "originStateId": origin_id,
                    "commonCauseId": common_cause_id,
                    "pathId": path_id,
                    "relationshipIds": new_path_edges,
                    "sourceNode": edge["sourceNode"],
                    "targetNode": edge["targetNode"],
                    "polarity": edge["polarity"],
                    "evidenceClass": edge["evidenceClass"],
                    "outcome": "TRANSMITTED",
                    "disposition": disposition,
                    "directCoefficient": edge.get("directCoefficient"),
                    "value": str(transmitted_value),
                    "unit": edge["targetUnit"],
                    "depth": depth + 1,
                    "round": round_number + 1,
                }
                contributions.append(contribution)
                paths.add(path_id)
                nodes.add(edge["targetNode"])
                if len(nodes) > self.profile["budgets"]["maxNodes"]:
                    stop_reasons.add("node_budget")
                    break
                if len(paths) > self.profile["budgets"]["maxPaths"]:
                    stop_reasons.add("path_budget")
                    break
                if len(contributions) >= self.profile["budgets"]["maxContributions"]:
                    stop_reasons.add("contribution_budget")
                    break
                queue.append(({
                    "stateId": contribution["contributionId"],
                    "nodeId": edge["targetNode"],
                    "value": str(transmitted_value),
                    "unit": edge["targetUnit"],
                }, depth + 1, round_number + 1, new_path_edges, origin_id, common_cause_id))
            if {"node_budget", "path_budget", "contribution_budget"} & stop_reasons:
                break
        if not stop_reasons:
            stop_reasons.add("no_eligible_relationship")
        run_core = {
            "algorithmVersion": self.profile["propagationAlgorithmVersion"],
            "configurationVersion": self.profile["configurationVersion"],
            "replayMode": replay_mode,
            "knowledgeCutoff": knowledge_cutoff,
            "sourceSnapshotId": source_snapshot_id,
            "seedStateIds": sorted(row["stateId"] for row in seeds),
            "relationshipVersions": sorted(f"{row['edgeId']}@{row['version']}" for row in accepted),
            "thresholdVersion": self.profile["materiality"]["version"],
            "budgets": self.profile["budgets"],
            "maxDepth": self.profile["maxDepth"],
            "maxRounds": self.profile["maxRounds"],
            "stopReasons": sorted(stop_reasons),
        }
        return {
            **run_core,
            "propagationRunId": stable_id("propagation-run", {**run_core, "contributions": contributions}),
            "contributions": contributions,
            "reconciliation": reconcile_common_causes(contributions),
            "traversalCount": len(contributions),
            "contributionCount": len(contributions),
            "maxDepthReached": max_depth if not contributions else max(row["depth"] for row in contributions),
            "roundsUsed": rounds_used if not contributions else max(row["round"] for row in contributions),
        }

    def _empty_run(self, seeds, relationships, replay_mode, cutoff, source_snapshot_id, reason):
        core = {
            "algorithmVersion": self.profile["propagationAlgorithmVersion"],
            "configurationVersion": self.profile["configurationVersion"],
            "replayMode": replay_mode,
            "knowledgeCutoff": cutoff,
            "sourceSnapshotId": source_snapshot_id,
            "seedStateIds": sorted(row["stateId"] for row in seeds),
            "relationshipVersions": sorted(f"{row['edgeId']}@{row['version']}" for row in relationships),
            "thresholdVersion": self.profile["materiality"]["version"],
            "budgets": self.profile["budgets"],
            "maxDepth": self.profile["maxDepth"],
            "maxRounds": self.profile["maxRounds"],
            "stopReasons": [reason],
        }
        return {**core, "propagationRunId": stable_id("propagation-run", core), "contributions": [], "reconciliation": {"version": self.profile["reconciliationVersion"], "groups": []}, "traversalCount": 0, "contributionCount": 0, "maxDepthReached": 0, "roundsUsed": 0}
