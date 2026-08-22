"""Release manifest and use boundaries for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle
from .causal_beta_frontier_depth import CausalBetaFrontierDepthAudit
from .causal_beta_frontier_quality_gate import CausalBetaFrontierQualityGate
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


class CausalBetaFrontierReleaseState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReleaseCheck:
    check_id: str
    passed: bool
    evidence_address: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"check_id": self.check_id, "passed": self.passed, "evidence_address": self.evidence_address, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReleaseManifest:
    release_id: str
    version: str
    state: CausalBetaFrontierReleaseState
    bundle_address: str
    gate_address: str
    depth_address: str
    review_address: str
    checks: tuple[CausalBetaFrontierReleaseCheck, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "version": self.version, "state": self.state, "bundle_address": self.bundle_address, "gate_address": self.gate_address, "depth_address": self.depth_address, "review_address": self.review_address, "checks": [item.to_dict() for item in self.checks], "allowed_uses": self.allowed_uses, "excluded_uses": self.excluded_uses, "accepted": self.accepted, "passed_count": self.passed_count, "failed_check_ids": self.failed_check_ids}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_release_manifest(bundle: CausalBetaFrontierReleaseBundle, gate: CausalBetaFrontierQualityGate, depth: CausalBetaFrontierDepthAudit, review: CausalBetaFrontierReviewQueue, *, release_id: str = "causal-beta-frontier-release", version: str = "2026.08.d11-c05-c08.v1") -> CausalBetaFrontierReleaseManifest:
    checks = tuple(CausalBetaFrontierReleaseCheck(*item) for item in (
        ("bundle-ready", bundle.publishable, bundle.content_address, "all core outputs are bundled"),
        ("quality-gate", gate.accepted, gate.content_address, "no blocking quality check remains"),
        ("depth-audit", depth.accepted, depth.content_address, "depth checks cover all four operations"),
        ("review-queue", review.accepted and review.blocked_count >= 8, review.content_address, "controls remain visible in review"),
        ("boundary", "patient care" in bundle.excluded_uses and "diagnostic determination" in bundle.excluded_uses, bundle.content_address, "clinical uses are excluded"),
    ))
    accepted = all(item.passed for item in checks)
    state = CausalBetaFrontierReleaseState.READY if accepted else (CausalBetaFrontierReleaseState.BLOCKED if gate.blocking_check_ids else CausalBetaFrontierReleaseState.REVIEW)
    return CausalBetaFrontierReleaseManifest(release_id, version, state, bundle.content_address, gate.content_address, depth.content_address, review.content_address, checks, bundle.allowed_uses, bundle.excluded_uses, accepted)


__all__ = ["CausalBetaFrontierReleaseCheck", "CausalBetaFrontierReleaseManifest", "CausalBetaFrontierReleaseState", "build_causal_beta_frontier_release_manifest"]
