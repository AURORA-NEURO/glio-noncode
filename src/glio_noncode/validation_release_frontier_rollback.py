"""Rollback plan for a research planning release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseRollbackAction:
    action_id: str
    trigger: str
    target_release: str
    reversible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseRollbackPlan:
    actions: tuple[ValidationReleaseRollbackAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_rollback_plan(current_release: str, previous_release: str) -> ValidationReleaseRollbackPlan:
    body = {"action_id": "rollback-validation-release", "trigger": "quality-regression", "target_release": previous_release, "reversible": True}
    return ValidationReleaseRollbackPlan((ValidationReleaseRollbackAction(**body, content_address=content_hash(body)),), bool(current_release and previous_release), content_hash(body))


__all__ = ["ValidationReleaseRollbackAction", "ValidationReleaseRollbackPlan", "build_validation_release_rollback_plan"]
