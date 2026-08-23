"""Review protocol for blocked, rejected, and review-state rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_review_queue import ValidationReleaseReviewQueue


@dataclass(frozen=True, slots=True)
class ValidationReleaseReviewProtocolStep:
    sequence: int
    step_id: str
    instruction: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseReviewProtocol:
    steps: tuple[ValidationReleaseReviewProtocolStep, ...]
    target_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_review_protocol(queue: ValidationReleaseReviewQueue) -> ValidationReleaseReviewProtocol:
    instructions = ("confirm exact context and source receipts", "inspect operation-specific issue codes", "check whether missing inputs can be repaired", "record review decision without upgrading scientific claims", "replay only after the input change is addressed")
    steps = []
    for sequence, instruction in enumerate(instructions, start=1):
        body = {"sequence": sequence, "step_id": f"review-step-{sequence:02d}", "instruction": instruction, "required": True}
        steps.append(ValidationReleaseReviewProtocolStep(**body, content_address=content_hash(body)))
    return ValidationReleaseReviewProtocol(tuple(steps), len(queue.items), all(item.required for item in steps), content_hash(tuple(steps)))


__all__ = ["ValidationReleaseReviewProtocol", "ValidationReleaseReviewProtocolStep", "build_validation_release_review_protocol"]
