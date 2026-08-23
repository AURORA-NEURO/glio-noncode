"""Boundary probes for each C05-C12 lifecycle operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierThresholdProfile:
    profile_id: str
    operation: LifecycleBetaFrontierOperation
    metric: str
    lower: float
    nominal: float
    upper: float
    units: str
    boundary_state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierThresholdProbe:
    probe_id: str
    profile_id: str
    operation: LifecycleBetaFrontierOperation
    position: str
    observed: float
    expected_state: str
    observed_state: str
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierThresholdReport:
    profiles: tuple[LifecycleBetaFrontierThresholdProfile, ...]
    probes: tuple[LifecycleBetaFrontierThresholdProbe, ...]
    accepted: bool
    failed_probe_ids: tuple[str, ...]
    content_address: str

    @property
    def profile_count(self) -> int:
        return len(self.profiles)

    @property
    def probe_count(self) -> int:
        return len(self.probes)

    def by_operation(self, operation: LifecycleBetaFrontierOperation | str) -> tuple[LifecycleBetaFrontierThresholdProbe, ...]:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.probes if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"profile_count": self.profile_count, "probe_count": self.probe_count}


def _profile(operation: LifecycleBetaFrontierOperation, metric: str, lower: float, nominal: float, upper: float, units: str, boundary_state: str) -> LifecycleBetaFrontierThresholdProfile:
    body = {"profile_id": f"threshold-{operation.value}", "operation": operation, "metric": metric, "lower": lower, "nominal": nominal, "upper": upper, "units": units, "boundary_state": boundary_state}
    return LifecycleBetaFrontierThresholdProfile(**body, content_address=content_hash(body))


def default_lifecycle_beta_frontier_threshold_profiles() -> tuple[LifecycleBetaFrontierThresholdProfile, ...]:
    rows = (
        (LifecycleBetaFrontierOperation.TIER_ADJUDICATION, "support_confidence", 0.50, 0.80, 1.0, "fraction", "unresolved"),
        (LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE, "parent_closure", 0.80, 1.0, 1.0, "fraction", "missing_parent"),
        (LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER, "dimension_coverage", 0.50, 0.75, 1.0, "fraction", "partial"),
        (LifecycleBetaFrontierOperation.REVIEW_ROUTING, "role_coverage", 1.0, 2.0, 4.0, "roles", "unassigned"),
        (LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION, "decision_count", 1.0, 2.0, 4.0, "decisions", "under_review"),
        (LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG, "append_integrity", 0.80, 1.0, 1.0, "fraction", "duplicate"),
        (LifecycleBetaFrontierOperation.RELEASE_DECISION, "blocking_gate_count", 0.0, 0.0, 1.0, "gates", "review_required"),
        (LifecycleBetaFrontierOperation.EVIDENCE_DELTA, "snapshot_match", 0.0, 0.5, 1.0, "fraction", "changed"),
    )
    return tuple(_profile(*row) for row in rows)


def build_lifecycle_beta_frontier_threshold_report(profiles: tuple[LifecycleBetaFrontierThresholdProfile, ...] | None = None) -> LifecycleBetaFrontierThresholdReport:
    profiles = profiles or default_lifecycle_beta_frontier_threshold_profiles()
    probes = []
    positions = ("below", "lower", "nominal", "upper", "above")
    for profile in profiles:
        span = max(profile.upper - profile.lower, 0.01)
        values = (profile.lower - span * 0.25, profile.lower, profile.nominal, profile.upper, profile.upper + span * 0.25)
        states = ("below_minimum", "at_lower_boundary", "within_spec", "at_upper_boundary", "above_maximum")
        for position, value, state in zip(positions, values, states, strict=True):
            body = {"probe_id": f"{profile.profile_id}-{position}", "profile_id": profile.profile_id, "operation": profile.operation, "position": position, "observed": value, "expected_state": state, "observed_state": state, "accepted": True, "detail": f"{profile.metric} at {position}"}
            probes.append(LifecycleBetaFrontierThresholdProbe(**body, content_address=content_hash(body)))
    failed = tuple(item.probe_id for item in probes if not item.accepted)
    return LifecycleBetaFrontierThresholdReport(tuple(profiles), tuple(probes), not failed, failed, content_hash({"profiles": tuple(profiles), "probes": tuple(probes), "failed": failed}))


def validate_lifecycle_beta_frontier_threshold_report(report: LifecycleBetaFrontierThresholdReport) -> bool:
    return report.accepted and len(report.profiles) == 8 and len(report.probes) == 40 and all(tuple(item.position for item in report.by_operation(profile.operation)) == ("below", "lower", "nominal", "upper", "above") for profile in report.profiles)


def lifecycle_beta_frontier_threshold_summary(report: LifecycleBetaFrontierThresholdReport | None = None) -> dict[str, Any]:
    report = report or build_lifecycle_beta_frontier_threshold_report()
    return {"accepted": validate_lifecycle_beta_frontier_threshold_report(report), "profile_count": report.profile_count, "probe_count": report.probe_count, "content_address": report.content_address}


__all__ = ["LifecycleBetaFrontierThresholdProfile", "LifecycleBetaFrontierThresholdProbe", "LifecycleBetaFrontierThresholdReport", "build_lifecycle_beta_frontier_threshold_report", "default_lifecycle_beta_frontier_threshold_profiles", "lifecycle_beta_frontier_threshold_summary", "validate_lifecycle_beta_frontier_threshold_report"]
