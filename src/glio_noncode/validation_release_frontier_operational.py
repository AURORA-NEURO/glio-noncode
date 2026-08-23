"""Operational matrix from state and issue to bounded next action."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseOperationalRow:
    record_id: str
    state: str
    issue_codes: tuple[str, ...]
    action: str
    owner: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseOperationalMatrix:
    rows: tuple[ValidationReleaseOperationalRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_operational_matrix(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseOperationalMatrix:
    rows = []
    for item in evaluation.executions:
        if item.observed_state.value in {"ready", "packaged", "updated"}:
            action, owner = "retain_for_research_handoff", "release-review"
        elif "context_mismatch" in item.issue_codes:
            action, owner = "verify_context_boundary", "data-governance"
        elif item.observed_state.value == "rejected":
            action, owner = "repair_input_and_replay", "operation-owner"
        else:
            action, owner = "review_control", "domain-review"
        body = {"record_id": item.record_id, "state": item.observed_state.value, "issue_codes": item.issue_codes, "action": action, "owner": owner}
        rows.append(ValidationReleaseOperationalRow(**body, content_address=content_hash(body)))
    return ValidationReleaseOperationalMatrix(tuple(rows), all(item.action and item.owner for item in rows), content_hash(tuple(rows)))


__all__ = ["ValidationReleaseOperationalMatrix", "ValidationReleaseOperationalRow", "build_validation_release_operational_matrix"]
