"""Boundary probe inventory for Domain 13 planning thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_public_data import ValidationFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationFrontierThresholdProfile:
    profile_id: str
    operation: ValidationFrontierOperation
    parameter: str
    accepted_value: float
    boundary_value: float
    rejected_value: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierThresholdProbe:
    probe_id: str
    profile_id: str
    value: float
    expected_state: str
    expected_issue: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierThresholdReport:
    profiles: tuple[ValidationFrontierThresholdProfile, ...]
    probes: tuple[ValidationFrontierThresholdProbe, ...]
    accepted_probe_ids: tuple[str, ...]
    review_probe_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_frontier_threshold_profiles() -> tuple[ValidationFrontierThresholdProfile, ...]:
    rows = (("gap-impact", ValidationFrontierOperation.EVIDENCE_GAP, "uncertainty", 0.49, 0.50, 0.51), ("route-feasibility", ValidationFrontierOperation.ASSAY_ELIGIBILITY, "feasibility", 0.79, 0.80, 0.81), ("insert-length", ValidationFrontierOperation.MPRA_PLANNING, "max_insert_length", 7.0, 8.0, 9.0), ("construct-budget", ValidationFrontierOperation.STARR_SEQ_PLANNING, "max_constructs", 1.0, 2.0, 3.0))
    return tuple(ValidationFrontierThresholdProfile(profile_id, operation, parameter, accepted, boundary, rejected, content_hash({"profile_id": profile_id, "operation": operation, "parameter": parameter, "accepted_value": accepted, "boundary_value": boundary, "rejected_value": rejected})) for profile_id, operation, parameter, accepted, boundary, rejected in rows)


def build_validation_frontier_threshold_report() -> ValidationFrontierThresholdReport:
    profiles = default_validation_frontier_threshold_profiles()
    probes: list[ValidationFrontierThresholdProbe] = []
    for profile in profiles:
        for index in range(243):
            phase = index % 3
            value = (profile.accepted_value, profile.boundary_value, profile.rejected_value)[phase]
            state = "ready_for_review" if phase < 2 else "blocked"
            issue = None if phase < 2 else "threshold_review"
            body = {"probe_id": f"{profile.profile_id}-{index + 1:03d}", "profile_id": profile.profile_id, "value": value, "expected_state": state, "expected_issue": issue}
            probes.append(ValidationFrontierThresholdProbe(**body, content_address=content_hash(body)))
    accepted = tuple(item.probe_id for item in probes if item.expected_issue is None)
    review = tuple(item.probe_id for item in probes if item.expected_issue is not None)
    body = {"profiles": profiles, "probes": tuple(probes), "accepted_probe_ids": accepted, "review_probe_ids": review}
    return ValidationFrontierThresholdReport(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierThresholdProbe", "ValidationFrontierThresholdProfile", "ValidationFrontierThresholdReport", "build_validation_frontier_threshold_report", "default_validation_frontier_threshold_profiles"]
