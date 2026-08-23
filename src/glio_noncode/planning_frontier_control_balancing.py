"""Balance summary for deterministic control assignments."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ControlBalanceSummary:
    target_count: int
    control_type_count: int
    biological_replicates: int
    technical_replicates: int
    expected_assignment_count: int
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def summarize_control_balance(target_count: int, control_type_count: int, biological_replicates: int, technical_replicates: int) -> ControlBalanceSummary:
    expected = target_count * control_type_count * biological_replicates * technical_replicates
    accepted = all(value > 0 for value in (target_count, control_type_count, biological_replicates, technical_replicates))
    body = {"target_count": target_count, "control_type_count": control_type_count, "biological_replicates": biological_replicates, "technical_replicates": technical_replicates, "expected_assignment_count": expected, "accepted": accepted}
    return ControlBalanceSummary(**body, content_address=content_hash(body, prefix="control-balance"))
__all__ = ["ControlBalanceSummary", "summarize_control_balance"]
