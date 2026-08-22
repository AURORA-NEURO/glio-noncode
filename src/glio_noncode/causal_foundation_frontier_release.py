"""Release manifest and explicit use boundaries for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_foundation_frontier_bundle import CausalFoundationFrontierReleaseBundle
from .causal_foundation_frontier_depth import CausalFoundationFrontierDepthAudit
from .causal_foundation_frontier_quality_gate import CausalFoundationFrontierQualityGate
from .causal_foundation_frontier_review import CausalFoundationFrontierReviewQueue
from .serialization import content_hash, jsonable


class CausalFoundationFrontierReleaseState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReleaseCheck:
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
class CausalFoundationFrontierReleaseManifest:
    release_id: str
    version: str
    state: CausalFoundationFrontierReleaseState
    bundle_address: str
    gate_address: str
    depth_address: str
    review_address: str
    checks: tuple[CausalFoundationFrontierReleaseCheck, ...]
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


def build_causal_foundation_frontier_release_manifest(bundle: CausalFoundationFrontierReleaseBundle, gate: CausalFoundationFrontierQualityGate, depth: CausalFoundationFrontierDepthAudit, review: CausalFoundationFrontierReviewQueue, *, release_id: str = "causal-foundation-frontier-release", version: str = "2026.08.d11-c01-c04.v1") -> CausalFoundationFrontierReleaseManifest:
    raw = (
        ("bundle-ready", bundle.publishable, bundle.content_address, "bundle includes every content-addressed output"),
        ("quality-gate", gate.accepted, gate.content_address, "no blocking quality gate check remains"),
        ("depth-audit", depth.accepted, depth.content_address, "depth checks cover four operations and controls"),
        ("review-queue", review.accepted and review.blocked_count >= 5, review.content_address, "every row has a disposition and blocking controls remain visible"),
        ("boundary", not any("patient" in item for item in bundle.allowed_uses), bundle.content_address, "allowed uses remain aggregate and research bounded"),
    )
    checks = tuple(CausalFoundationFrontierReleaseCheck(check_id, passed, address, detail) for check_id, passed, address, detail in raw)
    accepted = all(item.passed for item in checks)
    state = CausalFoundationFrontierReleaseState.READY if accepted else (CausalFoundationFrontierReleaseState.BLOCKED if gate.blocking_check_ids else CausalFoundationFrontierReleaseState.REVIEW)
    return CausalFoundationFrontierReleaseManifest(release_id, version, state, bundle.content_address, gate.content_address, depth.content_address, review.content_address, checks, bundle.allowed_uses, bundle.excluded_uses, accepted)


__all__ = ["CausalFoundationFrontierReleaseCheck", "CausalFoundationFrontierReleaseManifest", "CausalFoundationFrontierReleaseState", "build_causal_foundation_frontier_release_manifest"]
