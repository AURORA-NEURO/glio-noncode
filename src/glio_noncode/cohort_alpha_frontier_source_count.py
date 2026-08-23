"""Source count oracle for fixture and operation receipt closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceCount:
    total_sources: int
    referenced_sources: int
    unreferenced_sources: int
    operation_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def count_cohort_alpha_frontier_sources(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierSourceCount:
    referenced = {source_id for record in fixture.records for source_id in record.source_ids}
    operations = {operation: len({source_id for record in fixture.records if record.operation == operation for source_id in record.source_ids}) for operation in fixture.operations}
    body = {"total": len(fixture.sources), "referenced": len(referenced), "unreferenced": len(fixture.sources) - len(referenced), "operations": operations}
    return CohortAlphaFrontierSourceCount(body["total"], body["referenced"], body["unreferenced"], operations, len(fixture.sources) == 6 and referenced <= {source.source_id for source in fixture.sources}, content_hash(body, prefix="alpha-source-count"))


__all__ = ["CohortAlphaFrontierSourceCount", "count_cohort_alpha_frontier_sources"]
