"""Threshold profiles and probes for cohort convergence boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierThresholdProfile:
    profile_id: str
    operation: CohortFrontierOperation
    minimum_overlap: float
    maximum_shift: float
    maximum_parity_gap: float
    privacy_floor: int
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.profile_id, "profile_id")
        require_non_empty(self.rationale, "rationale")
        if not 0 <= self.minimum_overlap <= 1 or not 0 <= self.maximum_parity_gap <= 1 or self.maximum_shift < 0 or self.privacy_floor < 1:
            raise ValueError("cohort thresholds are out of range")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierThresholdProbe:
    probe_id: str
    operation: CohortFrontierOperation
    overlap: float
    shift: float
    parity_gap: float
    site_count: int
    privacy_floor: int
    passes_overlap: bool
    passes_shift: bool
    passes_parity: bool
    passes_privacy: bool
    expected_review: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierThresholdReport:
    profiles: tuple[CohortFrontierThresholdProfile, ...]
    probes: tuple[CohortFrontierThresholdProbe, ...]
    content_address: str

    @property
    def accepted_probe_ids(self) -> tuple[str, ...]:
        return tuple(item.probe_id for item in self.probes if not item.expected_review)

    @property
    def review_probe_ids(self) -> tuple[str, ...]:
        return tuple(item.probe_id for item in self.probes if item.expected_review)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted_probe_ids": list(self.accepted_probe_ids), "review_probe_ids": list(self.review_probe_ids)}


def default_cohort_frontier_threshold_profiles() -> tuple[CohortFrontierThresholdProfile, ...]:
    rows = (("cohort-threshold-c13", CohortFrontierOperation.SUBGROUP_FAIRNESS, 0.75, 0.25, 0.20, 5, "parity gap remains bounded"), ("cohort-threshold-c14", CohortFrontierOperation.TRANSPORTABILITY, 0.75, 0.25, 0.20, 5, "overlap and shift remain visible"), ("cohort-threshold-c15", CohortFrontierOperation.FEDERATED_SUMMARY, 0.75, 0.25, 0.20, 5, "privacy floor protects small site summaries"), ("cohort-threshold-c16", CohortFrontierOperation.COHORT_DISCOVERY, 0.75, 0.25, 0.20, 5, "discovery requires addressed aggregate evidence"))
    return tuple(CohortFrontierThresholdProfile(*row, content_hash(row)) for row in rows)


def build_cohort_frontier_threshold_report() -> CohortFrontierThresholdReport:
    profiles = default_cohort_frontier_threshold_profiles()
    probes: list[CohortFrontierThresholdProbe] = []
    index = 0
    for profile, overlap, shift, parity, site_count, privacy in product(profiles, (0.50, 0.75, 1.0), (0.10, 0.25, 0.80), (0.10, 0.20, 0.60), (1, 2, 3), (2, 5, 10)):
        index += 1
        flags = (overlap >= profile.minimum_overlap, shift <= profile.maximum_shift, parity <= profile.maximum_parity_gap, site_count > 0 and privacy >= profile.privacy_floor)
        body = {"probe_id": f"cohort-threshold-probe-{index:03d}", "operation": profile.operation, "overlap": overlap, "shift": shift, "parity_gap": parity, "site_count": site_count, "privacy_floor": privacy, "passes_overlap": flags[0], "passes_shift": flags[1], "passes_parity": flags[2], "passes_privacy": flags[3], "expected_review": not all(flags)}
        probes.append(CohortFrontierThresholdProbe(**body, content_address=content_hash(body)))
    body = {"profiles": profiles, "probes": tuple(probes)}
    return CohortFrontierThresholdReport(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierThresholdProbe", "CohortFrontierThresholdProfile", "CohortFrontierThresholdReport", "build_cohort_frontier_threshold_report", "default_cohort_frontier_threshold_profiles"]
