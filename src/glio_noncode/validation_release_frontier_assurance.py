"""Combined assurance projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_depth import ValidationReleaseDepthAudit
from .validation_release_frontier_quality_gate import ValidationReleaseQualityReport
from .validation_release_frontier_reconciliation import ValidationReleaseReconciliation


@dataclass(frozen=True, slots=True)
class ValidationReleaseAssuranceSummary:
    quality: bool
    depth: bool
    integrity: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_assurance_summary(quality: ValidationReleaseQualityReport, depth: ValidationReleaseDepthAudit, reconciliation: ValidationReleaseReconciliation) -> ValidationReleaseAssuranceSummary:
    body = {"quality": quality.accepted, "depth": depth.accepted, "integrity": reconciliation.accepted, "accepted": quality.accepted and depth.accepted and reconciliation.accepted}
    return ValidationReleaseAssuranceSummary(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseAssuranceSummary", "build_validation_release_assurance_summary"]
