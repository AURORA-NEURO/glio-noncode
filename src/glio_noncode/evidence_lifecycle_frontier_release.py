"""Release manifest for the Domain 14 evidence lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .evidence_lifecycle_frontier_bundle import EvidenceLifecycleReleaseBundle
from .evidence_lifecycle_frontier_quality_gate import EvidenceLifecycleQualityGate
from .evidence_lifecycle_frontier_replay import EvidenceLifecycleReplayReceipt
from .serialization import content_hash, jsonable


class EvidenceLifecycleReleaseState(StrEnum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReleaseCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReleaseManifest:
    release_id: str
    bundle_id: str
    state: EvidenceLifecycleReleaseState
    checks: tuple[EvidenceLifecycleReleaseCheck, ...]
    replay_id: str
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_lifecycle_release_manifest(bundle: EvidenceLifecycleReleaseBundle, gate: EvidenceLifecycleQualityGate, replay: EvidenceLifecycleReplayReceipt, *, release_id: str = "evidence-lifecycle-release-manifest") -> EvidenceLifecycleReleaseManifest:
    checks = tuple(EvidenceLifecycleReleaseCheck(check_id, passed, detail, content_hash({"check_id": check_id, "passed": passed, "detail": detail})) for check_id, passed, detail in (("bundle-publishable", bundle.publishable, "policy decisions allow all positive lifecycle paths"), ("quality-gate", gate.accepted, "quality gate has no failed checks"), ("replay", replay.accepted, "replay evaluation is accepted"), ("research-boundary", True, "release remains research scoped")))
    accepted = all(item.passed for item in checks)
    state = EvidenceLifecycleReleaseState.READY if accepted else EvidenceLifecycleReleaseState.BLOCKED
    body = {"release_id": release_id, "bundle_id": bundle.bundle_id, "state": state, "checks": checks, "replay_id": replay.replay_id, "allowed_uses": ("provenance review", "citation reconciliation", "research triage"), "excluded_uses": ("patient care", "diagnosis", "prognosis", "treatment selection", "individual risk"), "accepted": accepted}
    return EvidenceLifecycleReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleReleaseCheck", "EvidenceLifecycleReleaseManifest", "EvidenceLifecycleReleaseState", "build_evidence_lifecycle_release_manifest"]
