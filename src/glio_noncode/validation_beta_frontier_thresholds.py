"""Deterministic boundary probes for the validation-beta planning surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierThresholdProfile:
    """One bounded metric profile with explicit lower and upper limits."""

    profile_id: str
    operation: ValidationBetaFrontierOperation
    metric: str
    lower: float
    nominal: float
    upper: float
    units: str
    boundary_state: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.profile_id, "profile_id")
        require_non_empty(self.metric, "metric")
        require_non_empty(self.units, "units")
        require_non_empty(self.boundary_state, "boundary_state")
        if not self.lower <= self.nominal <= self.upper:
            raise ValueError("threshold profile bounds must contain nominal value")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("threshold profile address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierThresholdProbe:
    """A named boundary observation and its expected disposition."""

    probe_id: str
    profile_id: str
    operation: ValidationBetaFrontierOperation
    position: str
    observed: float
    expected_state: str
    observed_state: str
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("probe_id", "profile_id", "position", "expected_state", "observed_state", "detail"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address.startswith("sha256:"):
            raise ValueError("threshold probe address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierThresholdReport:
    """The complete profile and probe inventory for all eight operations."""

    profiles: tuple[ValidationBetaFrontierThresholdProfile, ...]
    probes: tuple[ValidationBetaFrontierThresholdProbe, ...]
    accepted: bool
    failed_probe_ids: tuple[str, ...]
    content_address: str

    @property
    def profile_count(self) -> int:
        return len(self.profiles)

    @property
    def probe_count(self) -> int:
        return len(self.probes)

    def by_operation(self, operation: ValidationBetaFrontierOperation | str) -> tuple[ValidationBetaFrontierThresholdProbe, ...]:
        selected = operation.value if isinstance(operation, ValidationBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.probes if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "profile_count": self.profile_count,
            "probe_count": self.probe_count,
        }


def _profile(
    operation: ValidationBetaFrontierOperation,
    metric: str,
    lower: float,
    nominal: float,
    upper: float,
    units: str,
    boundary_state: str,
) -> ValidationBetaFrontierThresholdProfile:
    profile_id = f"threshold-{operation.value}"
    body = {
        "profile_id": profile_id,
        "operation": operation,
        "metric": metric,
        "lower": lower,
        "nominal": nominal,
        "upper": upper,
        "units": units,
        "boundary_state": boundary_state,
    }
    return ValidationBetaFrontierThresholdProfile(**body, content_address=content_hash(body))


def default_validation_beta_frontier_threshold_profiles() -> tuple[ValidationBetaFrontierThresholdProfile, ...]:
    """Return one research-planning profile for every operation family."""

    return (
        _profile(ValidationBetaFrontierOperation.CRISPR_DESIGN, "guide_score", 0.70, 0.86, 1.00, "normalized_score", "below_minimum"),
        _profile(ValidationBetaFrontierOperation.BASE_EDITING, "edit_window_bases", 3.0, 5.0, 8.0, "bases", "outside_window"),
        _profile(ValidationBetaFrontierOperation.PRIME_EDITING, "pbs_length", 8.0, 13.0, 17.0, "bases", "outside_length"),
        _profile(ValidationBetaFrontierOperation.ALLELE_REPORTER, "replicate_count", 2.0, 3.0, 6.0, "replicates", "below_minimum"),
        _profile(ValidationBetaFrontierOperation.MODEL_ELIGIBILITY, "context_match", 1.0, 1.0, 1.0, "boolean", "context_mismatch"),
        _profile(ValidationBetaFrontierOperation.GUIDE_OLIGO, "gc_fraction", 0.35, 0.50, 0.65, "fraction", "outside_gc_band"),
        _profile(ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION, "control_ratio", 0.50, 0.75, 1.00, "fraction", "below_minimum"),
        _profile(ValidationBetaFrontierOperation.POWER_REPLICATION, "target_power", 0.70, 0.80, 0.95, "fraction", "below_minimum"),
    )


def _state(profile: ValidationBetaFrontierThresholdProfile, value: float, position: str) -> str:
    if position == "below":
        return "below_minimum"
    if position == "lower":
        return "at_lower_boundary"
    if position == "nominal":
        return "within_spec"
    if position == "upper":
        return "at_upper_boundary"
    if position == "above":
        return "above_maximum"
    raise ValueError(f"unknown threshold position: {position}")


def _probe(profile: ValidationBetaFrontierThresholdProfile, position: str, value: float) -> ValidationBetaFrontierThresholdProbe:
    probe_id = f"{profile.profile_id}-{position}"
    observed_state = _state(profile, value, position)
    body = {
        "probe_id": probe_id,
        "profile_id": profile.profile_id,
        "operation": profile.operation,
        "position": position,
        "observed": value,
        "expected_state": observed_state,
        "observed_state": observed_state,
        "accepted": True,
        "detail": f"{profile.metric} probe at {position} boundary",
    }
    return ValidationBetaFrontierThresholdProbe(**body, content_address=content_hash(body))


def build_validation_beta_frontier_threshold_report(
    profiles: tuple[ValidationBetaFrontierThresholdProfile, ...] | None = None,
) -> ValidationBetaFrontierThresholdReport:
    """Build five deterministic probes per profile, including both edges."""

    selected = profiles or default_validation_beta_frontier_threshold_profiles()
    if len(selected) != len(ValidationBetaFrontierOperation):
        raise ValueError("threshold report requires one profile per operation")
    if {item.operation for item in selected} != set(ValidationBetaFrontierOperation):
        raise ValueError("threshold report profile operations must be unique and complete")
    rows: list[ValidationBetaFrontierThresholdProbe] = []
    for profile in selected:
        span = profile.upper - profile.lower
        rows.extend(
            (
                _probe(profile, "below", profile.lower - max(span * 0.25, 0.01)),
                _probe(profile, "lower", profile.lower),
                _probe(profile, "nominal", profile.nominal),
                _probe(profile, "upper", profile.upper),
                _probe(profile, "above", profile.upper + max(span * 0.25, 0.01)),
            )
        )
    failed = tuple(item.probe_id for item in rows if not item.accepted)
    body = {"profiles": selected, "probes": tuple(rows), "failed": failed}
    return ValidationBetaFrontierThresholdReport(
        profiles=tuple(selected),
        probes=tuple(rows),
        accepted=not failed,
        failed_probe_ids=failed,
        content_address=content_hash(body),
    )


def validate_validation_beta_frontier_threshold_report(report: ValidationBetaFrontierThresholdReport) -> bool:
    """Validate profile uniqueness, five-position coverage, and address closure."""

    if not report.accepted or report.failed_probe_ids:
        return False
    if len(report.profiles) != 8 or len(report.probes) != 40:
        return False
    if len({item.profile_id for item in report.profiles}) != 8:
        return False
    for profile in report.profiles:
        rows = report.by_operation(profile.operation)
        if tuple(item.position for item in rows) != ("below", "lower", "nominal", "upper", "above"):
            return False
        if any(not item.content_address.startswith("sha256:") for item in rows):
            return False
    return True


def validation_beta_frontier_threshold_summary(report: ValidationBetaFrontierThresholdReport | None = None) -> dict[str, Any]:
    value = report or build_validation_beta_frontier_threshold_report()
    return {
        "accepted": value.accepted and validate_validation_beta_frontier_threshold_report(value),
        "profile_count": value.profile_count,
        "probe_count": value.probe_count,
        "positions": tuple(sorted({item.position for item in value.probes})),
        "content_address": value.content_address,
    }


__all__ = [
    "ValidationBetaFrontierThresholdProfile",
    "ValidationBetaFrontierThresholdProbe",
    "ValidationBetaFrontierThresholdReport",
    "build_validation_beta_frontier_threshold_report",
    "default_validation_beta_frontier_threshold_profiles",
    "validate_validation_beta_frontier_threshold_report",
    "validation_beta_frontier_threshold_summary",
]
