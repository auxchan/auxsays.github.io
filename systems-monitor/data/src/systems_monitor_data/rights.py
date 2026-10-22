from __future__ import annotations

from dataclasses import dataclass


class RightsDenied(PermissionError):
    pass


@dataclass(frozen=True)
class RightsDecision:
    source_id: str
    operation: str
    decision: str
    evidence: str


class RightsEngine:
    def __init__(self, registry: dict):
        self.operations = set(registry["operations"])
        self.policies = {row["source_id"]: row for row in registry["policies"]}

    def decide(self, source_id: str, operation: str) -> RightsDecision:
        if operation not in self.operations:
            return RightsDecision(source_id, operation, "UNKNOWN", "operation not registered")
        policy = self.policies.get(source_id)
        if not policy:
            return RightsDecision(source_id, operation, "UNKNOWN", "source not registered")
        return RightsDecision(source_id, operation, policy["decisions"].get(operation, "UNKNOWN"), policy["evidence"])

    def require(self, source_id: str, operation: str) -> RightsDecision:
        decision = self.decide(source_id, operation)
        if decision.decision != "ALLOW":
            raise RightsDenied(f"{source_id}:{operation} is {decision.decision}")
        return decision

