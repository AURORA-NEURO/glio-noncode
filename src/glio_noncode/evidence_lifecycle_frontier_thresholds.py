"""Threshold probes for bounded lifecycle state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleThresholdProfile:
    profile_id: str
    operation: EvidenceLifecycleOperation
    threshold_name: str
    lower: float
    upper: float
    review_state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleThresholdProbe:
    probe_id: str
    profile_id: str
    value: float
    state: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleThresholdReport:
    profiles: tuple[EvidenceLifecycleThresholdProfile, ...]
    probes: tuple[EvidenceLifecycleThresholdProbe, ...]
    accepted_probe_ids: tuple[str, ...]
    review_probe_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_lifecycle_threshold_profiles() -> tuple[EvidenceLifecycleThresholdProfile, ...]:
    rows = []
    for operation in EvidenceLifecycleOperation:
        body = {"profile_id": f"threshold:{operation.value}", "operation": operation, "threshold_name": "confidence_review_floor", "lower": 0.0, "upper": 1.0, "review_state": "review_required"}
        rows.append(EvidenceLifecycleThresholdProfile(**body, content_address=content_hash(body)))
    return tuple(rows)


def build_evidence_lifecycle_threshold_report() -> EvidenceLifecycleThresholdReport:
    profiles = default_evidence_lifecycle_threshold_profiles()
    probes = []
    for profile in profiles:
        for index in range(243):
            value = round(index / 242, 6)
            accepted = value >= 0.8
            body = {"probe_id": f"{profile.profile_id}:probe:{index:03d}", "profile_id": profile.profile_id, "value": value, "state": "supported" if accepted else profile.review_state, "accepted": accepted}
            probes.append(EvidenceLifecycleThresholdProbe(**body, content_address=content_hash(body)))
    accepted = tuple(item.probe_id for item in probes if item.accepted)
    review = tuple(item.probe_id for item in probes if not item.accepted)
    body = {"profiles": profiles, "probes": tuple(probes), "accepted_probe_ids": accepted, "review_probe_ids": review}
    return EvidenceLifecycleThresholdReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleThresholdProbe", "EvidenceLifecycleThresholdProfile", "EvidenceLifecycleThresholdReport", "build_evidence_lifecycle_threshold_report", "default_evidence_lifecycle_threshold_profiles"]
