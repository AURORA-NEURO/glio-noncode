"""Release manifest for cohort convergence evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_frontier_bundle import CohortFrontierReleaseBundle
from .cohort_frontier_quality_gate import CohortFrontierQualityGate
from .cohort_frontier_replay import CohortFrontierReplayReceipt
from .serialization import content_hash, jsonable


class CohortFrontierReleaseState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class CohortFrontierReleaseCheck:
    check_id: str
    passed: bool
    evidence_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierReleaseManifest:
    release_id: str
    version: str
    state: CohortFrontierReleaseState
    bundle_address: str
    quality_gate_address: str
    replay_address: str
    checks: tuple[CohortFrontierReleaseCheck, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state in {CohortFrontierReleaseState.READY, CohortFrontierReleaseState.PUBLISHED} and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_cohort_frontier_release_manifest(bundle: CohortFrontierReleaseBundle, gate: CohortFrontierQualityGate, replay: CohortFrontierReplayReceipt, *, release_id: str = "cohort-frontier-release", version: str = "2026.08.d12.v1") -> CohortFrontierReleaseManifest:
    raw = (("bundle", bool(bundle.content_address), bundle.content_address, "bundle is addressed"), ("quality-gate", gate.accepted, gate.content_address, "quality gate passes"), ("replay", replay.accepted, replay.content_address, "replay passes"), ("bundle-publishable", bundle.publishable, bundle.content_address, "positive paths are publishable"))
    checks = tuple(CohortFrontierReleaseCheck(item[0], item[1], item[2], item[3], content_hash(item)) for item in raw)
    state = CohortFrontierReleaseState.READY if all(item.passed for item in checks) else CohortFrontierReleaseState.REVIEW
    body = {"release_id": release_id, "version": version, "state": state, "bundle_address": bundle.content_address, "quality_gate_address": gate.content_address, "replay_address": replay.content_address, "checks": checks, "allowed_uses": ("aggregate cohort review", "method development", "reproducibility testing", "research triage"), "excluded_uses": ("patient care", "diagnosis", "prognosis", "treatment selection", "individual risk", "clinical cohort claims")}
    return CohortFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierReleaseCheck", "CohortFrontierReleaseManifest", "CohortFrontierReleaseState", "build_cohort_frontier_release_manifest"]
