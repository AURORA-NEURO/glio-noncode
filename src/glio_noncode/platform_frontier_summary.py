"""Compact summary object for platform frontier reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .platform_frontier_metrics import PlatformFrontierMetrics
from .platform_frontier_release import PlatformFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierSummary:
    fixture_id: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    check_count: int
    passed_check_count: int
    release_accepted: bool
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_summary(evaluation: PlatformFrontierEvaluation, metrics: PlatformFrontierMetrics, release: PlatformFrontierReleaseManifest) -> PlatformFrontierSummary:
    body = {"fixture_id": evaluation.fixture_id, "record_count": metrics.record_count, "positive_count": metrics.positive_count, "control_count": metrics.control_count, "accepted_count": metrics.accepted_count, "check_count": metrics.check_count, "passed_check_count": metrics.passed_check_count, "release_accepted": release.accepted, "limitations": release.limitations}
    return PlatformFrontierSummary(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierSummary", "build_platform_frontier_summary"]
