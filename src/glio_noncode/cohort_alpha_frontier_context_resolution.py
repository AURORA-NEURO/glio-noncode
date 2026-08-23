"""Context resolution and mismatch receipts for fixture records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierContextResolution:
    record_id: str
    declared_context: str
    resolved_context: str
    exact_match: bool
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierContextResolutionReport:
    rows: tuple[CohortAlphaFrontierContextResolution, ...]
    exact_count: int
    foreign_count: int
    empty_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def resolve_cohort_alpha_frontier_context(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierContextResolutionReport:
    rows = []
    for record in fixture.records:
        if record.control_class == "foreign_context":
            resolved, disposition = fixture.foreign_context_key, "quarantine"
        elif record.control_class == "empty_control":
            resolved, disposition = "", "abstain"
        else:
            resolved, disposition = fixture.context_key, "target"
        exact = resolved == fixture.context_key
        rows.append(CohortAlphaFrontierContextResolution(record.record_id, resolved, resolved, exact, disposition, content_hash({"record_id": record.record_id, "context": resolved, "exact": exact, "disposition": disposition}, prefix="alpha-context")))
    values = tuple(rows)
    return CohortAlphaFrontierContextResolutionReport(values, sum(item.exact_match for item in values), sum(item.disposition == "quarantine" for item in values), sum(item.disposition == "abstain" for item in values), len(values) == 16 and sum(item.exact_match for item in values) == 8, content_hash(values, prefix="alpha-context-report"))


__all__ = ["CohortAlphaFrontierContextResolution", "CohortAlphaFrontierContextResolutionReport", "resolve_cohort_alpha_frontier_context"]
