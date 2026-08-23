"""Recovery plans for blocked or rejected validation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseRecoveryAction:
    action_id: str
    trigger: str
    action: str
    safe: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseRecoveryPlan:
    actions: tuple[ValidationReleaseRecoveryAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_recovery_plan(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseRecoveryPlan:
    actions = []
    for item in evaluation.executions:
        if item.observed_state.value in {"ready", "packaged", "updated"}:
            continue
        action = "inspect_context_and_source_receipts" if "context_mismatch" in item.issue_codes else "repair_input_and_replay" if "invalid_payload" in item.issue_codes else "route_to_domain_review"
        body = {"action_id": f"recover:{item.record_id}", "trigger": item.record_id, "action": action, "safe": True}
        actions.append(ValidationReleaseRecoveryAction(**body, content_address=content_hash(body)))
    return ValidationReleaseRecoveryPlan(tuple(actions), all(item.safe for item in actions), content_hash(tuple(actions)))


__all__ = ["ValidationReleaseRecoveryAction", "ValidationReleaseRecoveryPlan", "build_validation_release_recovery_plan"]
