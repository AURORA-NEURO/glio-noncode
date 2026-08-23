"""Control-plan dimensional rules."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ControlRuleResult:
    rule_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_control_rules(payload: dict[str, Any]) -> tuple[ControlRuleResult, ...]:
    values = (
        ("plan-id", bool(payload.get("plan_id")), True, "plan identity is required"),
        ("seed", bool(payload.get("randomization_seed")), True, "seed is required"),
        ("controls", bool(payload.get("control_types")), True, "control classes are required"),
        ("targets", bool(payload.get("targets")), True, "target inventory is required"),
    )
    return tuple(ControlRuleResult(rule_id, observed == required, observed, required, detail, content_hash({"rule_id": rule_id, "observed": observed, "required": required, "detail": detail}, prefix="control-rule")) for rule_id, observed, required, detail in values)
__all__ = ["ControlRuleResult", "evaluate_control_rules"]
