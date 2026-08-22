"""Declared threshold profiles for runtime and release monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierThresholdProfile:
    """Lower, nominal, and upper bound for a declared quantity."""

    profile_id: str
    operation: GammaFrontierOperation
    parameter: str
    lower: float
    nominal: float
    upper: float
    unit: str
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        if not self.lower <= self.nominal <= self.upper:
            raise ValueError("gamma threshold bounds must be ordered")

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierThresholdProbe:
    """Observed value against one profile."""

    profile_id: str
    observed: float
    within_bounds: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierThresholdReport:
    """Threshold profile and probe report."""

    profiles: tuple[GammaFrontierThresholdProfile, ...]
    probes: tuple[GammaFrontierThresholdProbe, ...]
    accepted: bool
    content_address: str

    def by_profile(self, profile_id: str) -> tuple[GammaFrontierThresholdProbe, ...]:
        return tuple(item for item in self.probes if item.profile_id == profile_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _profile(
    profile_id: str,
    operation: GammaFrontierOperation,
    parameter: str,
    lower: float,
    nominal: float,
    upper: float,
    unit: str,
    rationale: str,
) -> GammaFrontierThresholdProfile:
    body = {
        "profile_id": profile_id,
        "operation": operation,
        "parameter": parameter,
        "lower": lower,
        "nominal": nominal,
        "upper": upper,
        "unit": unit,
        "rationale": rationale,
    }
    return GammaFrontierThresholdProfile(
        **body, content_address=content_hash(body, prefix="threshold-profile")
    )


def default_gamma_frontier_threshold_profiles() -> tuple[GammaFrontierThresholdProfile, ...]:
    """Return operational bounds for every surface."""

    return (
        _profile(
            "board-card-count",
            GammaFrontierOperation.EXPERIMENT_BOARD,
            "cards",
            1,
            8,
            100,
            "cards",
            "review boards remain inspectable",
        ),
        _profile(
            "launch-count",
            GammaFrontierOperation.LAUNCH_PLAN,
            "launches",
            1,
            4,
            32,
            "launches",
            "launch batches remain bounded",
        ),
        _profile(
            "snapshot-audience",
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "audience",
            1,
            4,
            64,
            "members",
            "sharing audience remains explicit",
        ),
        _profile(
            "access-request-count",
            GammaFrontierOperation.COLLABORATION_ACCESS,
            "requests",
            1,
            8,
            128,
            "requests",
            "access decisions remain reviewable",
        ),
    )


def build_gamma_frontier_threshold_report() -> GammaFrontierThresholdReport:
    """Probe nominal values and retain each bound."""

    profiles = default_gamma_frontier_threshold_profiles()
    probes = tuple(
        GammaFrontierThresholdProbe(
            profile_id=item.profile_id,
            observed=item.nominal,
            within_bounds=item.contains(item.nominal),
            detail="nominal fixture probe is within declared bounds",
            content_address=content_hash(
                {"profile_id": item.profile_id, "observed": item.nominal}, prefix="threshold-probe"
            ),
        )
        for item in profiles
    )
    body = {
        "profiles": profiles,
        "probes": probes,
        "accepted": all(item.within_bounds for item in probes),
    }
    return GammaFrontierThresholdReport(
        **body, content_address=content_hash(body, prefix="threshold-report")
    )


__all__ = [
    "GammaFrontierThresholdProbe",
    "GammaFrontierThresholdProfile",
    "GammaFrontierThresholdReport",
    "build_gamma_frontier_threshold_report",
    "default_gamma_frontier_threshold_profiles",
]
