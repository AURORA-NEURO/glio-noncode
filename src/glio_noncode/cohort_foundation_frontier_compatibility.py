"""Compatibility checks for release consumers and serialized surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest


@dataclass(frozen=True, slots=True)
class CohortFoundationCompatibilityCheck:
    consumer_id: str
    required_release_state: str
    observed_release_state: str
    required_boundary: str
    observed_boundary: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationCompatibilityReport:
    report_id: str
    checks: tuple[CohortFoundationCompatibilityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_foundation_frontier_compatibility(release: CohortFoundationReleaseManifest) -> CohortFoundationCompatibilityReport:
    consumers = (("review-console", "ready", "public_aggregate_non_patient"), ("research-export", "ready", "public_aggregate_non_patient"), ("quarantine-store", "ready", "public_aggregate_non_patient"), ("offline-replay", "ready", "public_aggregate_non_patient"))
    checks = []
    for consumer_id, required_state, required_boundary in consumers:
        accepted = release.state.value == required_state and release.public_boundary == required_boundary
        body = {"consumer": consumer_id, "required_state": required_state, "observed_state": release.state.value, "required_boundary": required_boundary, "observed_boundary": release.public_boundary}
        checks.append(CohortFoundationCompatibilityCheck(consumer_id, required_state, release.state.value, required_boundary, release.public_boundary, accepted, content_hash(body)))
    body = {"report_id": "cohort-foundation-frontier-compatibility", "checks": checks}
    return CohortFoundationCompatibilityReport(body["report_id"], tuple(checks), all(item.accepted for item in checks), content_hash(body))


__all__ = ["CohortFoundationCompatibilityCheck", "CohortFoundationCompatibilityReport", "evaluate_cohort_foundation_frontier_compatibility"]
