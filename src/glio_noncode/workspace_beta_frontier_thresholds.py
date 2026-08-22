"""Threshold probes for projection bounds and reconciliation tolerance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierThresholdProfile:
    profile_id: str
    operation: BetaFrontierOperation
    parameter: str
    lower: float
    nominal: float
    upper: float
    unit: str
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.profile_id, "profile_id")
        require_non_empty(self.parameter, "parameter")
        require_non_empty(self.unit, "unit")
        if not self.lower <= self.nominal <= self.upper:
            raise ValueError("beta frontier threshold ordering is invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierThresholdProbe:
    probe_id: str
    profile_id: str
    value: float
    position: str
    expected_behavior: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierThresholdReport:
    profiles: tuple[BetaFrontierThresholdProfile, ...]
    probes: tuple[BetaFrontierThresholdProbe, ...]
    boundary_count: int
    content_address: str

    def by_profile(self, profile_id: str) -> tuple[BetaFrontierThresholdProbe, ...]:
        return tuple(item for item in self.probes if item.profile_id == profile_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _profile(profile_id: str, operation: BetaFrontierOperation, parameter: str, lower: float, nominal: float, upper: float, unit: str, rationale: str) -> BetaFrontierThresholdProfile:
    body = {"profile_id": profile_id, "operation": operation, "parameter": parameter, "lower": lower, "nominal": nominal, "upper": upper, "unit": unit, "rationale": rationale}
    return BetaFrontierThresholdProfile(**body, content_address=content_hash(body))


def build_beta_frontier_threshold_report() -> BetaFrontierThresholdReport:
    profiles = (
        _profile("topology-focus", BetaFrontierOperation.TOPOLOGY_VIEWPORT, "max_edges", 1, 50, 1000, "edges", "viewport edges remain bounded"),
        _profile("chain-kinds", BetaFrontierOperation.CAUSAL_CHAIN, "required_kinds", 1, 3, 3, "kinds", "required mediator kinds are explicit"),
        _profile("posterior-tolerance", BetaFrontierOperation.POSTERIOR_DECOMPOSITION, "residual_tolerance", 0, 0.05, 1, "ratio", "support reconciliation tolerance is visible"),
        _profile("table-page", BetaFrontierOperation.EVIDENCE_TABLE, "limit", 1, 50, 500, "rows", "table page size remains bounded"),
        _profile("table-offset", BetaFrontierOperation.EVIDENCE_TABLE, "offset", 0, 1, 10000, "rows", "pagination offset is non-negative"),
        _profile("topology-nodes", BetaFrontierOperation.TOPOLOGY_VIEWPORT, "max_nodes", 1, 50, 10000, "nodes", "viewport node count remains bounded"),
    )
    probes: list[BetaFrontierThresholdProbe] = []
    index = 1
    for profile in profiles:
        values = (profile.lower, profile.nominal, profile.upper, (profile.lower + profile.nominal) / 2, (profile.nominal + profile.upper) / 2, profile.nominal - 0.001 if profile.nominal > profile.lower else profile.nominal, profile.nominal + 0.001 if profile.nominal < profile.upper else profile.nominal)
        for value in values:
            position = "lower" if value == profile.lower else "upper" if value == profile.upper else "nominal_band"
            probes.append(BetaFrontierThresholdProbe(f"beta-threshold-{index:03d}", profile.profile_id, value, position, "accept or retain boundary state", content_hash((profile.profile_id, value, position))))
            index += 1
    body = {"profiles": profiles, "probes": tuple(probes), "boundary_count": sum(item.position != "nominal_band" for item in probes)}
    return BetaFrontierThresholdReport(**body, content_address=content_hash(body))


def default_beta_frontier_threshold_profiles() -> tuple[BetaFrontierThresholdProfile, ...]:
    return build_beta_frontier_threshold_report().profiles


__all__ = ["BetaFrontierThresholdProbe", "BetaFrontierThresholdProfile", "BetaFrontierThresholdReport", "build_beta_frontier_threshold_report", "default_beta_frontier_threshold_profiles"]
