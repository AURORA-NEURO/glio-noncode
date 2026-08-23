"""Release manifest with explicit checks and public claim ceiling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_beta_frontier_bundle import CohortBetaFrontierReleaseBundle
from .cohort_beta_frontier_quality_gate import CohortBetaFrontierQualityGate
from .cohort_beta_frontier_replay import CohortBetaFrontierReplayReceipt
from .serialization import content_hash, jsonable


class CohortBetaFrontierReleaseState(StrEnum):
    READY = "ready"
    HELD = "held"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReleaseCheck:
    check_id: str
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReleaseManifest:
    release_id: str
    state: CohortBetaFrontierReleaseState
    checks: tuple[CohortBetaFrontierReleaseCheck, ...]
    claim_ceiling: str
    ready: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_release_manifest(bundle: CohortBetaFrontierReleaseBundle, quality: CohortBetaFrontierQualityGate, replay: CohortBetaFrontierReplayReceipt) -> CohortBetaFrontierReleaseManifest:
    checks_raw = (("bundle", bundle.accepted, "bundle is closed"), ("quality", quality.accepted, "quality gate is accepted"), ("replay", replay.deterministic, "replay is deterministic"))
    checks = tuple(CohortBetaFrontierReleaseCheck(check_id, accepted, detail, content_hash({"check_id": check_id, "accepted": accepted, "detail": detail}, prefix="release-check")) for check_id, accepted, detail in checks_raw)
    ready = all(item.accepted for item in checks)
    body = {"release_id": "cohort-beta-frontier-c05-c08-release", "state": CohortBetaFrontierReleaseState.READY if ready else CohortBetaFrontierReleaseState.HELD, "checks": checks, "claim_ceiling": "descriptive aggregate recurrence, burden, functional, and set convergence only", "ready": ready}
    return CohortBetaFrontierReleaseManifest(body["release_id"], body["state"], checks, body["claim_ceiling"], ready, content_hash(body, prefix="release"))


__all__ = ["CohortBetaFrontierReleaseCheck", "CohortBetaFrontierReleaseManifest", "CohortBetaFrontierReleaseState", "build_cohort_beta_frontier_release_manifest"]
