"""Controlled vocabulary for claims emitted by C09-C12 reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_claim_boundary import CohortAlphaFrontierClaimBoundary
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimTerm:
    term: str
    class_name: str
    permitted_context: str
    forbidden_extension: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimDictionary:
    terms: tuple[CohortAlphaFrontierClaimTerm, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_claim_dictionary(boundary: CohortAlphaFrontierClaimBoundary) -> CohortAlphaFrontierClaimDictionary:
    terms = tuple(CohortAlphaFrontierClaimTerm(term, "allowed", "exact-context aggregate summary", "causal, prognostic, or clinical interpretation", content_hash({"term": term, "class": "allowed", "context": "exact-context aggregate summary", "forbidden": "causal, prognostic, or clinical interpretation"}, prefix="alpha-claim-term")) for term in boundary.allowed_claims)
    return CohortAlphaFrontierClaimDictionary(terms, boundary.accepted and len(terms) == 4 and all(item.forbidden_extension for item in terms), content_hash(terms, prefix="alpha-claim-dictionary"))


__all__ = ["CohortAlphaFrontierClaimDictionary", "CohortAlphaFrontierClaimTerm", "build_cohort_alpha_frontier_claim_dictionary"]
