"""Release manifest and explicit non-clinical use boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle
from .causal_alpha_frontier_depth import CausalAlphaFrontierDepthAudit
from .causal_alpha_frontier_quality_gate import CausalAlphaFrontierQualityGate
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue
from .serialization import content_hash


class CausalAlphaFrontierReleaseState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReleaseCheck:
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
class CausalAlphaFrontierReleaseManifest:
    release_id: str
    version: str
    state: CausalAlphaFrontierReleaseState
    bundle_address: str
    gate_address: str
    depth_address: str
    review_address: str
    checks: tuple[CausalAlphaFrontierReleaseCheck, ...]
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


def build_causal_alpha_frontier_release_manifest(bundle: CausalAlphaFrontierReleaseBundle, gate: CausalAlphaFrontierQualityGate, depth: CausalAlphaFrontierDepthAudit, review: CausalAlphaFrontierReviewQueue, *, release_id: str = "causal-alpha-frontier-release", version: str = "2026.08.d11-c09-c12.v1") -> CausalAlphaFrontierReleaseManifest:
    allowed = ("descriptive aggregate evidence", "source-omission sensitivity", "confounder checklist status", "dependence-group summary", "negative-control review")
    excluded = ("causal identification", "clinical diagnosis", "treatment recommendation", "prognosis", "patient care")
    checks = tuple(CausalAlphaFrontierReleaseCheck(*item) for item in (
        ("bundle-ready", bundle.publishable, bundle.content_address, "all core outputs are bundled"),
        ("quality-gate", gate.accepted, gate.content_address, "quality checks are accepted"),
        ("depth-audit", depth.accepted, depth.content_address, "depth checks cover all four operations"),
        ("review-queue", review.accepted and len(review.items) >= 8, review.content_address, "partial and control rows remain visible"),
        ("boundary", all(item in excluded for item in ("clinical diagnosis", "patient care")), bundle.content_address, "clinical uses are excluded"),
    ))
    accepted = all(item.passed for item in checks)
    state = CausalAlphaFrontierReleaseState.READY if accepted else CausalAlphaFrontierReleaseState.BLOCKED if not gate.accepted else CausalAlphaFrontierReleaseState.REVIEW
    return CausalAlphaFrontierReleaseManifest(release_id, version, state, bundle.content_address, gate.content_address, depth.content_address, review.content_address, checks, allowed, excluded, accepted)


__all__ = ["CausalAlphaFrontierReleaseCheck", "CausalAlphaFrontierReleaseManifest", "CausalAlphaFrontierReleaseState", "build_causal_alpha_frontier_release_manifest"]
