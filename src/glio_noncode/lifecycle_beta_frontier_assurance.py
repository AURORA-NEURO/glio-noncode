"""Assurance summary joining fixture, quality, replay, and policy receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_policy import LifecycleBetaFrontierPolicy
from .lifecycle_beta_frontier_quality_gate import LifecycleBetaFrontierQualityReport
from .lifecycle_beta_frontier_replay import LifecycleBetaFrontierReplayReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAssuranceSummary:
    fixture_id: str
    controls_total: int
    controls_preserved: bool
    quality_accepted: bool
    replay_deterministic: bool
    excluded_use_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_assurance_summary(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation, quality: LifecycleBetaFrontierQualityReport, replay: LifecycleBetaFrontierReplayReport, policy: LifecycleBetaFrontierPolicy) -> LifecycleBetaFrontierAssuranceSummary:
    body = {"fixture_id": fixture.fixture_id, "controls_total": len(fixture.control_records), "controls_preserved": sum(item.role.value == "control" for item in evaluation.executions) == len(fixture.control_records), "quality_accepted": quality.accepted, "replay_deterministic": replay.deterministic, "excluded_use_count": len(policy.excluded_uses)}
    body["accepted"] = bool(body["controls_preserved"] and quality.accepted and replay.deterministic and body["excluded_use_count"] == 5)
    return LifecycleBetaFrontierAssuranceSummary(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierAssuranceSummary", "build_lifecycle_beta_frontier_assurance_summary"]
