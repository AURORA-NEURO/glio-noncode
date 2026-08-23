"""Fine-grained rules for model-system eligibility review."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .planning_frontier_contracts import PLANNING_FRONTIER_CONTEXT_KEY
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EligibilityRuleResult:
    rule_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def check_eligibility_rule(rule_id: str, observed: Any, required: Any, detail: str) -> EligibilityRuleResult:
    body = {"rule_id": rule_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
    return EligibilityRuleResult(**body, content_address=content_hash(body, prefix="eligibility-rule"))

def evaluate_eligibility_rules(payload: dict[str, Any]) -> tuple[EligibilityRuleResult, ...]:
    context = payload.get("context_key", "")
    observations = tuple(payload.get("observations", ()))
    return (
        check_eligibility_rule("context", context, PLANNING_FRONTIER_CONTEXT_KEY, "exact context is required"),
        check_eligibility_rule("observation-count", bool(observations), True, "at least one observation is needed for a positive gate"),
        check_eligibility_rule("threshold", payload.get("minimum_evidence_strength", ""), "moderate", "moderate is the default review floor"),
    )
__all__ = ["EligibilityRuleResult", "check_eligibility_rule", "evaluate_eligibility_rules"]
