"""Machine-readable scope statement for the C09-C12 surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import C09_C12_BOUNDARY, C09_C12_CONTEXT, C09_C12_FIXTURE_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierScopeStatement:
    scope_id: str
    context_key: str
    fixture_version: str
    boundary: str
    included_operations: tuple[str, ...]
    excluded_claims: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_scope_statement() -> CohortAlphaFrontierScopeStatement:
    excluded = ("causal evolution", "recurrence causation", "treatment effect", "prognosis", "resistance", "benefit", "transportability", "clinical validity")
    body = {"id": "cohort-alpha-frontier-scope", "context": C09_C12_CONTEXT, "version": C09_C12_FIXTURE_VERSION, "boundary": C09_C12_BOUNDARY, "operations": ("C09", "C10", "C11", "C12"), "excluded": excluded}
    return CohortAlphaFrontierScopeStatement(body["id"], body["context"], body["version"], body["boundary"], body["operations"], excluded, True, content_hash(body, prefix="alpha-scope"))


__all__ = ["CohortAlphaFrontierScopeStatement", "default_cohort_alpha_frontier_scope_statement"]
