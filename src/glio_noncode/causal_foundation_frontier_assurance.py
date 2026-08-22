"""Compact assurance summary for handoff and continuous integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_claim_boundary import CausalFoundationFrontierClaimBoundaryReport
from .causal_foundation_frontier_depth import CausalFoundationFrontierDepthAudit
from .causal_foundation_frontier_quality_gate import CausalFoundationFrontierQualityGate
from .causal_foundation_frontier_release import CausalFoundationFrontierReleaseManifest
from .causal_foundation_frontier_runtime import CausalFoundationFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierAssuranceSummary:
    run_id: str
    accepted: bool
    stage_count: int
    record_count: int
    positive_count: int
    control_count: int
    passed_quality_checks: int
    failed_quality_checks: int
    depth_passed: int
    depth_required: int
    release_state: str
    claim_boundary_accepted: bool
    retained_count: int
    blocked_count: int
    key_limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "accepted": self.accepted, "stage_count": self.stage_count, "record_count": self.record_count, "positive_count": self.positive_count, "control_count": self.control_count, "passed_quality_checks": self.passed_quality_checks, "failed_quality_checks": self.failed_quality_checks, "depth_passed": self.depth_passed, "depth_required": self.depth_required, "release_state": self.release_state, "claim_boundary_accepted": self.claim_boundary_accepted, "retained_count": self.retained_count, "blocked_count": self.blocked_count, "key_limitations": self.key_limitations}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_foundation_frontier_assurance_summary(runtime: CausalFoundationFrontierRuntimeReport, boundary: CausalFoundationFrontierClaimBoundaryReport | None = None) -> CausalFoundationFrontierAssuranceSummary:
    claim_boundary = boundary or CausalFoundationFrontierClaimBoundaryReport((), False)
    limitations = ("bounded proxies are not calibrated clinical probabilities", "public aggregate evidence does not establish individual causality", "foreign contexts remain quarantined")
    return CausalFoundationFrontierAssuranceSummary(runtime.run_id, runtime.accepted, runtime.stage_count, runtime.metrics.record_count, runtime.metrics.positive_count, runtime.metrics.control_count, runtime.gate.passed_count, runtime.gate.failed_count, runtime.depth.passed_count, runtime.depth.required_count, runtime.release.state.value, claim_boundary.accepted, runtime.review.retained_count, runtime.review.blocked_count, limitations)


__all__ = ["CausalFoundationFrontierAssuranceSummary", "build_causal_foundation_frontier_assurance_summary"]
