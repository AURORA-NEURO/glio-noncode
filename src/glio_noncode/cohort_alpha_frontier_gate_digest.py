"""One-line digest of all blocking and non-blocking gate outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierQualityGate
from .cohort_alpha_frontier_safety_controls import CohortAlphaFrontierSafetyReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierGateDigest:
    quality_passed: int
    quality_total: int
    safety_passed: int
    safety_total: int
    blocking_failures: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_gate_digest(quality: CohortAlphaFrontierQualityGate, safety: CohortAlphaFrontierSafetyReport) -> CohortAlphaFrontierGateDigest:
    body = {"quality_passed": sum(item.accepted for item in quality.checks), "quality_total": len(quality.checks), "safety_passed": sum(item.observed for item in safety.controls), "safety_total": len(safety.controls), "blocking": quality.blocking_failures}
    return CohortAlphaFrontierGateDigest(body["quality_passed"], body["quality_total"], body["safety_passed"], body["safety_total"], body["blocking"], quality.accepted and safety.accepted, content_hash(body, prefix="alpha-gate-digest"))


__all__ = ["CohortAlphaFrontierGateDigest", "build_cohort_alpha_frontier_gate_digest"]
