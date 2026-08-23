"""Assurance summary combining depth and integrity surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .platform_frontier_depth import PlatformFrontierDepthAudit
from .platform_frontier_integrity import PlatformFrontierIntegrityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierAssuranceSummary:
    fixture_id: str
    depth_accepted: bool
    integrity_accepted: bool
    evaluation_accepted: bool
    control_count: int
    positive_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_assurance_summary(evaluation: PlatformFrontierEvaluation, depth: PlatformFrontierDepthAudit, integrity: PlatformFrontierIntegrityReport) -> PlatformFrontierAssuranceSummary:
    controls = sum(item.role.value == "control" for item in evaluation.executions)
    positives = sum(item.role.value == "positive" for item in evaluation.executions)
    body = {"fixture_id": evaluation.fixture_id, "depth_accepted": depth.accepted, "integrity_accepted": integrity.accepted, "evaluation_accepted": evaluation.accepted, "control_count": controls, "positive_count": positives, "accepted": depth.accepted and integrity.accepted and evaluation.accepted}
    return PlatformFrontierAssuranceSummary(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierAssuranceSummary", "build_platform_frontier_assurance_summary"]
