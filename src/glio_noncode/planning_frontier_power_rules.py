"""Power-input validity rules."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class PowerRuleResult:
    rule_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_power_rules(row: dict[str, Any]) -> tuple[PowerRuleResult, ...]:
    effect = row.get("effect_size")
    variance = row.get("variance")
    alpha = row.get("alpha")
    target = row.get("target_power")
    values = (("effect", isinstance(effect, (int, float)) and effect != 0, True, "effect must be finite and non-zero"), ("variance", isinstance(variance, (int, float)) and variance > 0, True, "variance must be positive"), ("alpha", isinstance(alpha, (int, float)) and 0 < alpha < 1, True, "alpha must be in the open unit interval"), ("target-power", isinstance(target, (int, float)) and 0 < target < 1, True, "target power must be in the open unit interval"))
    return tuple(PowerRuleResult(rule, observed == required, observed, required, detail, content_hash({"rule": rule, "observed": observed, "required": required}, prefix="power-rule")) for rule, observed, required, detail in values)
__all__ = ["PowerRuleResult", "evaluate_power_rules"]
