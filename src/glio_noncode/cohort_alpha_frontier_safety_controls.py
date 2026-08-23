"""Safety controls that constrain publication and downstream interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSafetyControl:
    control_id: str
    rule: str
    observed: bool
    response: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSafetyReport:
    controls: tuple[CohortAlphaFrontierSafetyControl, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_safety(policy: CohortAlphaFrontierPolicy, quality: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierSafetyReport:
    raw = (("claim-ceiling", "descriptive claim ceiling is present", True, "retain limitation in report"), ("quarantine", "foreign and abstained paths are not publishable", policy.quarantine_count >= 8, "retain quarantine disposition"), ("review", "partial and ambiguous paths remain visible for review", policy.review_count >= 4, "retain review queue"), ("quality", "quality gate must pass before package release", quality.accepted, "block package"), ("no-intervention", "output does not prescribe treatment or clinical action", True, "retain descriptive framing"), ("traceability", "every publishable record retains a content address", all(item.content_address for item in policy.decisions), "block unreceipted output"))
    controls = tuple(CohortAlphaFrontierSafetyControl(control_id, rule, observed, response, content_hash({"id": control_id, "rule": rule, "observed": observed, "response": response}, prefix="alpha-safety")) for control_id, rule, observed, response in raw)
    return CohortAlphaFrontierSafetyReport(controls, all(item.observed for item in controls), content_hash(controls, prefix="alpha-safety-report"))


__all__ = ["CohortAlphaFrontierSafetyControl", "CohortAlphaFrontierSafetyReport", "evaluate_cohort_alpha_frontier_safety"]
