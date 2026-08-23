"""Threshold profiles and boundary probes for control construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationThresholdProfile:
    profile_id: str
    operation: CohortFoundationOperation
    maximum_controls: int
    maximum_distance: float
    purpose: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationThresholdProbe:
    probe_id: str
    profile_id: str
    parameter: str
    value: float
    expected_disposition: str
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationThresholdReport:
    report_id: str
    profiles: tuple[CohortFoundationThresholdProfile, ...]
    probes: tuple[CohortFoundationThresholdProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_threshold_profiles() -> tuple[CohortFoundationThresholdProfile, ...]:
    definitions = (
        ("cohort-query-default", CohortFoundationOperation.COHORT_QUERY, 0, 0.0, "exact selection"),
        ("background-default", CohortFoundationOperation.BACKGROUND_RATE, 0, 0.0, "callable-space summary"),
        ("sequence-strict", CohortFoundationOperation.SEQUENCE_CONTROL, 2, 0.0, "exact sequence controls"),
        ("chromatin-bounded", CohortFoundationOperation.CHROMATIN_CONTROL, 2, 0.06, "normalized chromatin controls"),
    )
    return tuple(CohortFoundationThresholdProfile(profile_id, operation, count, distance, purpose, content_hash((profile_id, operation, count, distance, purpose))) for profile_id, operation, count, distance, purpose in definitions)


def build_cohort_foundation_frontier_threshold_report() -> CohortFoundationThresholdReport:
    profiles = default_cohort_foundation_frontier_threshold_profiles()
    probes = []
    for profile in profiles:
        values = (("below", max(0.0, profile.maximum_distance - 0.01), "supported_or_partial", "inside declared boundary"), ("at", profile.maximum_distance, "supported_or_partial", "boundary is inclusive"), ("above", profile.maximum_distance + 0.01, "review", "outside declared boundary"))
        for label, value, disposition, reason in values:
            body = {"profile": profile.profile_id, "label": label, "value": value, "disposition": disposition}
            probes.append(CohortFoundationThresholdProbe(content_hash((profile.profile_id, label), prefix="probe"), profile.profile_id, "maximum_distance", round(value, 6), disposition, reason, content_hash(body)))
    body = {"report_id": "cohort-foundation-frontier-thresholds", "profiles": profiles, "probes": probes}
    return CohortFoundationThresholdReport(body["report_id"], profiles, tuple(probes), len(profiles) == 4 and len(probes) == 12, content_hash(body))


__all__ = ["CohortFoundationThresholdProbe", "CohortFoundationThresholdProfile", "CohortFoundationThresholdReport", "build_cohort_foundation_frontier_threshold_report", "default_cohort_foundation_frontier_threshold_profiles"]
