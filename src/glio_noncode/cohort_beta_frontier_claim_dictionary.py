"""Controlled vocabulary for words permitted in bounded result reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable


class CohortBetaFrontierClaimClass(StrEnum):
    ALLOWED = "allowed"
    PROHIBITED = "prohibited"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierClaimTerm:
    term: str
    claim_class: CohortBetaFrontierClaimClass
    replacement: str
    rationale: str
    operations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierClaimDictionary:
    terms: tuple[CohortBetaFrontierClaimTerm, ...]
    accepted: bool
    content_address: str

    def lookup(self, term: str) -> CohortBetaFrontierClaimTerm:
        return next(item for item in self.terms if item.term == term)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_claim_dictionary() -> CohortBetaFrontierClaimDictionary:
    raw = (("recurs", CohortBetaFrontierClaimClass.ALLOWED, "is recurrent in the supplied aggregate rows", "descriptive count only", ("C05",)), ("burden", CohortBetaFrontierClaimClass.ALLOWED, "callable-space burden", "denominator must be retained", ("C06",)), ("converges", CohortBetaFrontierClaimClass.ALLOWED, "shows bounded feature or set convergence", "not causal proof", ("C07", "C08")), ("enriched", CohortBetaFrontierClaimClass.REVIEW, "exceeds the supplied descriptive comparator", "avoid uncalibrated significance wording", ("C06",)), ("driver", CohortBetaFrontierClaimClass.PROHIBITED, "bounded recurrence or convergence evidence", "mechanistic proof is outside the contract", ("C05", "C06", "C07", "C08")), ("significant", CohortBetaFrontierClaimClass.PROHIBITED, "supported by the declared comparator", "no calibrated p-value is emitted", ("C05", "C06", "C07", "C08")), ("clinical", CohortBetaFrontierClaimClass.PROHIBITED, "research-use aggregate summary", "clinical outcome evidence is outside the contract", ("C05", "C06", "C07", "C08")), ("treatment", CohortBetaFrontierClaimClass.PROHIBITED, "future validation requirement", "treatment effects are not evaluated", ("C05", "C06", "C07", "C08")))
    terms = tuple(CohortBetaFrontierClaimTerm(term, claim_class, replacement, rationale, operations, content_hash({"term": term, "class": claim_class, "replacement": replacement}, prefix="claim-term")) for term, claim_class, replacement, rationale, operations in raw)
    return CohortBetaFrontierClaimDictionary(terms, len(terms) == 8 and any(item.claim_class is CohortBetaFrontierClaimClass.PROHIBITED for item in terms), content_hash(terms, prefix="claim-dictionary"))


def scan_cohort_beta_frontier_claims(text: str, dictionary: CohortBetaFrontierClaimDictionary | None = None) -> Mapping[str, tuple[str, ...]]:
    selected = dictionary or default_cohort_beta_frontier_claim_dictionary()
    tokens = {term.term for term in selected.terms if term.term in text.lower()}
    return {claim_class.value: tuple(sorted(term for term in tokens if selected.lookup(term).claim_class is claim_class)) for claim_class in CohortBetaFrontierClaimClass}


__all__ = ["CohortBetaFrontierClaimClass", "CohortBetaFrontierClaimDictionary", "CohortBetaFrontierClaimTerm", "default_cohort_beta_frontier_claim_dictionary", "scan_cohort_beta_frontier_claims"]
