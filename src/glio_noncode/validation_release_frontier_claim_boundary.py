"""Explicit wording boundary for research planning outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseClaimBoundary:
    allowed_claims: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    observed_operations: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_claim_boundary(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseClaimBoundary:
    body = {"allowed_claims": ("declared score calculation", "dependency-safe planning projection", "content-addressed package manifest", "exact-context result receipt"), "prohibited_claims": ("clinical efficacy", "treatment recommendation", "causal authorization", "patient benefit", "diagnosis"), "observed_operations": tuple(sorted({item.operation.value for item in evaluation.executions})), "accepted": evaluation.accepted}
    return ValidationReleaseClaimBoundary(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseClaimBoundary", "evaluate_validation_release_claim_boundary"]
