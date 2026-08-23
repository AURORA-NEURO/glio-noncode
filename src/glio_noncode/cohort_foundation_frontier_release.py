"""Release manifest and explicit checks for the cohort foundation bundle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_bundle import CohortFoundationReleaseBundle
from .cohort_foundation_frontier_replay import CohortFoundationReplayReceipt
from .cohort_foundation_frontier_quality_gate import CohortFoundationQualityGate


class CohortFoundationReleaseState(StrEnum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CohortFoundationReleaseCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationReleaseManifest:
    release_id: str
    bundle_id: str
    state: CohortFoundationReleaseState
    checks: tuple[CohortFoundationReleaseCheck, ...]
    public_boundary: str
    prohibited_uses: tuple[str, ...]
    content_address: str

    @property
    def ready(self) -> bool:
        return self.state is CohortFoundationReleaseState.READY

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_release_manifest(bundle: CohortFoundationReleaseBundle, quality: CohortFoundationQualityGate, replay: CohortFoundationReplayReceipt, *, release_id: str = "cohort-foundation-frontier-release-v1") -> CohortFoundationReleaseManifest:
    values = (
        ("bundle-accepted", bundle.accepted, "bundle quality, reconciliation, and provenance"),
        ("quality-gate", quality.accepted, "blocking quality checks"),
        ("replay-deterministic", replay.deterministic, "content-addressed replay"),
        ("aggregate-boundary", bundle.fixture.boundary == "public_aggregate_non_patient", "public aggregate boundary"),
        ("review-exportable", bool(bundle.review.to_dict()), "review queue is retained"),
    )
    checks = tuple(CohortFoundationReleaseCheck(check_id, passed, detail, content_hash((check_id, passed, detail))) for check_id, passed, detail in values)
    state = CohortFoundationReleaseState.READY if all(item.passed for item in checks) else CohortFoundationReleaseState.BLOCKED if any(item.check_id in {"bundle-accepted", "quality-gate", "aggregate-boundary"} and not item.passed for item in checks) else CohortFoundationReleaseState.REVIEW_REQUIRED
    body = {"release_id": release_id, "bundle_id": bundle.bundle_id, "state": state, "checks": checks}
    return CohortFoundationReleaseManifest(release_id, bundle.bundle_id, state, checks, bundle.fixture.boundary, ("patient-level selection", "diagnosis", "prognosis", "treatment", "causal conclusion"), content_hash(body))


__all__ = ["CohortFoundationReleaseCheck", "CohortFoundationReleaseManifest", "CohortFoundationReleaseState", "build_cohort_foundation_frontier_release_manifest"]
