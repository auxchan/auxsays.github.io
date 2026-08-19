from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .derivation import stable_id


def _number(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise ValueError("allocation input must be numeric") from error


def allocate(supply: Any, demands: list[dict[str, Any]], *, capacity: Any | None = None, tolerance: Any = "0.000001") -> dict[str, Any]:
    if supply is None or any(row.get("quantity") is None for row in demands):
        return {"status": "UNKNOWN_INPUT", "allocations": []}
    available = max(Decimal("0"), _number(supply))
    capacity_value = available if capacity is None else max(Decimal("0"), min(available, _number(capacity)))
    remaining = capacity_value
    allocations = []
    total_demand = Decimal("0")
    for row in sorted(demands, key=lambda item: item["id"]):
        demand = max(Decimal("0"), _number(row["quantity"]))
        total_demand += demand
        granted = min(demand, remaining)
        remaining -= granted
        allocations.append({"id": row["id"], "demand": str(demand), "allocated": str(granted), "unmet": str(demand - granted)})
    allocated = sum((_number(row["allocated"]) for row in allocations), Decimal("0"))
    absorbed = max(Decimal("0"), available - capacity_value)
    residual = max(Decimal("0"), capacity_value - allocated)
    unmet = sum((_number(row["unmet"]) for row in allocations), Decimal("0"))
    if abs(available - (allocated + absorbed + residual)) > _number(tolerance):
        raise ValueError("allocation conservation failed")
    status = "FULL" if unmet == 0 else "PARTIAL"
    core = {"supply": str(available), "totalDemand": str(total_demand), "capacity": str(capacity_value), "allocated": str(allocated), "absorbed": str(absorbed), "unmet": str(unmet), "residual": str(residual), "allocations": allocations, "status": status}
    return {**core, "allocationId": stable_id("allocation", core)}
