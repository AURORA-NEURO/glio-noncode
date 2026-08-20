"""Context compatibility and transport scoring."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ReferenceContext, SupportLevel


@dataclass(frozen=True, slots=True)
class ContextMatch:
    """Explain how evidence context maps to case context."""

    score: float
    distance: float
    support_level: SupportLevel
    matched_dimensions: tuple[str, ...]
    mismatched_dimensions: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "distance": self.distance,
            "support_level": self.support_level.value,
            "matched_dimensions": list(self.matched_dimensions),
            "mismatched_dimensions": list(self.mismatched_dimensions),
            "rationale": self.rationale,
        }


_DIMENSIONS = (
    "genome_build",
    "disease_class",
    "age_group",
    "cell_state",
    "territory",
    "treatment_phase",
)
_WEIGHTS = {
    "genome_build": 0.24,
    "disease_class": 0.22,
    "age_group": 0.14,
    "cell_state": 0.18,
    "territory": 0.10,
    "treatment_phase": 0.12,
}


def compare_context(case: ReferenceContext, evidence: ReferenceContext) -> ContextMatch:
    """Score evidence applicability without silently transferring context."""

    matched: list[str] = []
    mismatched: list[str] = []
    score = 0.0
    for dimension in _DIMENSIONS:
        if getattr(case, dimension) == getattr(evidence, dimension):
            matched.append(dimension)
            score += _WEIGHTS[dimension]
        else:
            mismatched.append(dimension)
    score = round(max(0.0, min(1.0, score)), 6)
    if score >= 0.86:
        level = SupportLevel.HIGH
    elif score >= 0.62:
        level = SupportLevel.MODERATE
    elif score >= 0.35:
        level = SupportLevel.LOW
    else:
        level = SupportLevel.UNKNOWN
    rationale = (
        "Exact context match."
        if not mismatched
        else "Matched dimensions: " + ", ".join(matched or ("none",)) + "; "
        + "transport required for: "
        + ", ".join(mismatched)
    )
    return ContextMatch(
        score=score,
        distance=round(1.0 - score, 6),
        support_level=level,
        matched_dimensions=tuple(matched),
        mismatched_dimensions=tuple(mismatched),
        rationale=rationale,
    )


def context_gate(match: ContextMatch, *, minimum: float = 0.35) -> bool:
    """Return whether evidence may be used as a bounded input."""

    return match.score >= minimum


def context_summary(match: ContextMatch) -> str:
    """Return a compact review label."""

    return f"{match.support_level.value} context support ({match.score:.3f})"
