"""Research-only policy boundary for validation release surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY


@dataclass(frozen=True, slots=True)
class ValidationReleasePolicy:
    policy_id: str
    context_key: str
    allowed_operations: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    review_required_states: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_release_policy() -> ValidationReleasePolicy:
    body = {"policy_id": "validation-release-research-only-v1", "context_key": VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY, "allowed_operations": ("off_target_risk", "value_of_information", "experiment_package", "claim_update"), "prohibited_claims": ("clinical efficacy", "treatment recommendation", "causal authorization", "patient-level conclusion"), "review_required_states": ("review", "blocked", "rejected", "abstained")}
    return ValidationReleasePolicy(**body, content_address=content_hash(body))


def evaluate_validation_release_policy(policy: ValidationReleasePolicy, evaluation) -> tuple[str, ...]:
    errors = []
    if policy.context_key != VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY:
        errors.append("policy-context-mismatch")
    if any(item.operation.value not in policy.allowed_operations for item in evaluation.executions):
        errors.append("operation-not-allowed")
    return tuple(errors)


__all__ = ["ValidationReleasePolicy", "default_validation_release_policy", "evaluate_validation_release_policy"]
