"""Declared threshold profiles and boundary probes."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierThresholdProfile:
    profile_id: str
    operation: CausalFrontierOperation
    minimum_score: float
    maximum_uncertainty: float
    minimum_support: float
    minimum_evidence_count: int
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.profile_id, "profile_id")
        require_non_empty(self.rationale, "rationale")
        for name in ("minimum_score", "minimum_support"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be bounded")
        if self.maximum_uncertainty < 0 or self.minimum_evidence_count < 0:
            raise ValueError("uncertainty and evidence count must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierThresholdProbe:
    probe_id: str
    operation: CausalFrontierOperation
    score: float
    uncertainty: float
    support: float
    evidence_count: int
    passes_score: bool
    passes_uncertainty: bool
    passes_support: bool
    passes_evidence: bool
    expected_review: bool
    content_address: str

    @property
    def accepted(self) -> bool:
        return not self.expected_review

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class CausalFrontierThresholdReport:
    profiles: tuple[CausalFrontierThresholdProfile, ...]
    probes: tuple[CausalFrontierThresholdProbe, ...]
    content_address: str

    @property
    def accepted_probes(self) -> tuple[str, ...]:
        return tuple(item.probe_id for item in self.probes if item.accepted)

    @property
    def review_probes(self) -> tuple[str, ...]:
        return tuple(item.probe_id for item in self.probes if item.expected_review)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted_probes": list(self.accepted_probes), "review_probes": list(self.review_probes)}


def default_causal_frontier_threshold_profiles() -> tuple[CausalFrontierThresholdProfile, ...]:
    rows = (
        ("threshold-c13", CausalFrontierOperation.POSTERIOR_DECOMPOSITION, 0.0, 0.25, 0.20, 1, "positive mass is required"),
        ("threshold-c14", CausalFrontierOperation.DRIVER_POSTERIOR, 0.60, 0.25, 0.20, 2, "support and evidence paths are reviewed"),
        ("threshold-c15", CausalFrontierOperation.SELECTIVE_PREDICTION, 0.60, 0.25, 0.20, 1, "weak or uncertain prediction abstains"),
        ("threshold-c16", CausalFrontierOperation.DOSSIER_PUBLICATION, 0.60, 0.25, 0.20, 1, "manifest needs named evidence addresses"),
    )
    return tuple(CausalFrontierThresholdProfile(*row, content_hash(row)) for row in rows)


def build_causal_frontier_threshold_report() -> CausalFrontierThresholdReport:
    profiles = default_causal_frontier_threshold_profiles()
    probes: list[CausalFrontierThresholdProbe] = []
    index = 0
    for profile, score, uncertainty, support, evidence_count in product(
        profiles,
        (0.0, 0.60, 0.90),
        (0.05, 0.25, 0.80),
        (0.05, 0.20, 0.80),
        (0, 1, 2),
    ):
        index += 1
        passes_score = score >= profile.minimum_score
        passes_uncertainty = uncertainty <= profile.maximum_uncertainty
        passes_support = support >= profile.minimum_support
        passes_evidence = evidence_count >= profile.minimum_evidence_count
        expected_review = not (passes_score and passes_uncertainty and passes_support and passes_evidence)
        body = {
            "probe_id": f"threshold-probe-{index:03d}",
            "operation": profile.operation,
            "score": score,
            "uncertainty": uncertainty,
            "support": support,
            "evidence_count": evidence_count,
            "passes_score": passes_score,
            "passes_uncertainty": passes_uncertainty,
            "passes_support": passes_support,
            "passes_evidence": passes_evidence,
            "expected_review": expected_review,
        }
        probes.append(CausalFrontierThresholdProbe(**body, content_address=content_hash(body)))
    body = {"profiles": profiles, "probes": tuple(probes)}
    return CausalFrontierThresholdReport(**body, content_address=content_hash(body))


__all__ = [
    "CausalFrontierThresholdProbe",
    "CausalFrontierThresholdProfile",
    "CausalFrontierThresholdReport",
    "build_causal_frontier_threshold_report",
    "default_causal_frontier_threshold_profiles",
]
