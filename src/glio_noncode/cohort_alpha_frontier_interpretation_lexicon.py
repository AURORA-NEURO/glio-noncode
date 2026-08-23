"""Preferred and restricted terms for descriptive aggregate reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLexiconTerm:
    term: str
    preferred: bool
    replacement: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierInterpretationLexicon:
    terms: tuple[CohortAlphaFrontierLexiconTerm, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_interpretation_lexicon() -> CohortAlphaFrontierInterpretationLexicon:
    raw = (("descriptive", True, "descriptive", "keeps the result within observed aggregate scope"), ("signal", True, "signal", "does not imply mechanism"), ("associated", True, "associated", "retains non-causal wording"), ("proves", False, "is consistent with", "prevents overstatement"), ("predicts", False, "is observed in", "prevents clinical interpretation"), ("drives", False, "co-occurs with", "prevents causal interpretation"))
    terms = tuple(CohortAlphaFrontierLexiconTerm(term, preferred, replacement, rationale, content_hash({"term": term, "preferred": preferred, "replacement": replacement, "rationale": rationale}, prefix="alpha-lexicon")) for term, preferred, replacement, rationale in raw)
    return CohortAlphaFrontierInterpretationLexicon(terms, len(terms) == 6 and sum(item.preferred for item in terms) == 3 and all(item.replacement for item in terms), content_hash(terms, prefix="alpha-lexicon-report"))


__all__ = ["CohortAlphaFrontierInterpretationLexicon", "CohortAlphaFrontierLexiconTerm", "default_cohort_alpha_frontier_interpretation_lexicon"]
