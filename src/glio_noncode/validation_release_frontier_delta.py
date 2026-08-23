"""Evaluation delta projection for release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseDelta:
    identical: bool
    changed_record_ids: tuple[str, ...]
    before_address: str
    after_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compare_validation_release_evaluations(before: ValidationReleaseEvaluation, after: ValidationReleaseEvaluation) -> ValidationReleaseDelta:
    old = {item.record_id: item.content_address for item in before.executions}
    new = {item.record_id: item.content_address for item in after.executions}
    changed = tuple(sorted(item for item in set(old) | set(new) if old.get(item) != new.get(item)))
    body = {"identical": before.content_address == after.content_address, "changed_record_ids": changed, "before_address": before.content_address, "after_address": after.content_address}
    return ValidationReleaseDelta(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseDelta", "compare_validation_release_evaluations"]
