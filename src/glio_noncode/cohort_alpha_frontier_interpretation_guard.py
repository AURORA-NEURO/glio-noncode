"""Text-level interpretation guard for descriptive release wording."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_report import CohortAlphaFrontierReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierInterpretationCheck:
    check_id: str
    forbidden_term: str
    present: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierInterpretationGuard:
    checks: tuple[CohortAlphaFrontierInterpretationCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_interpretation(report: CohortAlphaFrontierReport) -> CohortAlphaFrontierInterpretationGuard:
    text = report.to_markdown().lower()
    forbidden = ("causal conclusion", "clinical recommendation", "treatment prescription", "prognostic certainty", "statistical significance claim", "transportability claim")
    checks = tuple(
        CohortAlphaFrontierInterpretationCheck(
            f"wording-{index}",
            term,
            term in text,
            term not in text,
            content_hash({"term": term, "present": term in text, "accepted": term not in text}, prefix="alpha-interpretation"),
        )
        for index, term in enumerate(forbidden, 1)
    )
    return CohortAlphaFrontierInterpretationGuard(checks, all(item.accepted for item in checks), content_hash(checks, prefix="alpha-interpretation-guard"))


__all__ = ["CohortAlphaFrontierInterpretationCheck", "CohortAlphaFrontierInterpretationGuard", "evaluate_cohort_alpha_frontier_interpretation"]
