"""Release manifest, review gates, and artifact references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_frontier_bundle import CausalFrontierReleaseBundle
from .causal_frontier_quality_gate import CausalFrontierQualityGate
from .causal_frontier_replay import CausalFrontierReplayReceipt
from .serialization import content_hash, jsonable


class CausalFrontierReleaseState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class CausalFrontierReleaseCheck:
    check_id: str
    passed: bool
    evidence_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierReleaseManifest:
    release_id: str
    version: str
    state: CausalFrontierReleaseState
    bundle_address: str
    quality_gate_address: str
    replay_address: str
    checks: tuple[CausalFrontierReleaseCheck, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state in {CausalFrontierReleaseState.READY, CausalFrontierReleaseState.PUBLISHED} and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_causal_frontier_release_manifest(
    bundle: CausalFrontierReleaseBundle,
    gate: CausalFrontierQualityGate,
    replay: CausalFrontierReplayReceipt,
    *,
    release_id: str = "causal-frontier-release",
    version: str = "2026.08.d11.v1",
) -> CausalFrontierReleaseManifest:
    checks_raw = (
        ("bundle", bool(bundle.content_address), bundle.content_address, "bundle is content addressed"),
        ("quality-gate", gate.accepted, gate.content_address, "quality gate has no blocking check"),
        ("replay", replay.accepted, replay.content_address, "replay passes all checks"),
        ("bundle-publishable", bundle.publishable, bundle.content_address, "positive operation decisions are releasable"),
    )
    checks = tuple(
        CausalFrontierReleaseCheck(
            check_id=item[0],
            passed=item[1],
            evidence_address=item[2],
            detail=item[3],
            content_address=content_hash(item),
        )
        for item in checks_raw
    )
    state = CausalFrontierReleaseState.READY if all(item.passed for item in checks) else CausalFrontierReleaseState.REVIEW
    body = {
        "release_id": release_id,
        "version": version,
        "state": state,
        "bundle_address": bundle.content_address,
        "quality_gate_address": gate.content_address,
        "replay_address": replay.content_address,
        "checks": checks,
        "allowed_uses": ("aggregate evidence review", "method development", "reproducibility testing", "research triage"),
        "excluded_uses": ("patient care", "diagnostic determination", "treatment selection", "pathogenicity declaration"),
    }
    return CausalFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierReleaseCheck", "CausalFrontierReleaseManifest", "CausalFrontierReleaseState", "build_causal_frontier_release_manifest"]
