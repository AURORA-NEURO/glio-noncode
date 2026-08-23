"""Source receipt matrix showing how each operation is grounded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceReceiptCell:
    operation: str
    source_ids: tuple[str, ...]
    record_count: int
    all_receipted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceReceiptMatrix:
    cells: tuple[CohortAlphaFrontierSourceReceiptCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_source_receipt_matrix(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierSourceReceiptMatrix:
    available = {source.source_id for source in fixture.sources}
    cells = []
    for operation in fixture.operations:
        records = tuple(record for record in fixture.records if record.operation == operation)
        source_ids = tuple(sorted({source_id for record in records for source_id in record.source_ids}))
        accepted = bool(source_ids) and set(source_ids) <= available and all(source_id for source_id in source_ids)
        cells.append(CohortAlphaFrontierSourceReceiptCell(operation, source_ids, len(records), accepted, content_hash({"operation": operation, "sources": source_ids, "records": len(records), "accepted": accepted}, prefix="alpha-receipt-matrix")))
    values = tuple(cells)
    return CohortAlphaFrontierSourceReceiptMatrix(values, len(values) == 4 and all(item.record_count == 4 and item.all_receipted for item in values), content_hash(values, prefix="alpha-receipt-matrix-report"))


__all__ = ["CohortAlphaFrontierSourceReceiptCell", "CohortAlphaFrontierSourceReceiptMatrix", "build_cohort_alpha_frontier_source_receipt_matrix"]
