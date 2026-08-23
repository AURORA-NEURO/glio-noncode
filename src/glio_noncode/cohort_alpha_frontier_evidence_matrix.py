"""Evidence matrix linking each operation to source, state, and gate receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierLineage, CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEvidenceCell:
    operation: str
    source_count: int
    record_count: int
    supported_count: int
    boundary_count: int
    publish_count: int
    lineage_closed: bool
    quality_accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEvidenceMatrix:
    cells: tuple[CohortAlphaFrontierEvidenceCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_evidence_matrix(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy, lineage: CohortAlphaFrontierLineage, quality: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierEvidenceMatrix:
    cells = []
    for operation in fixture.operations:
        records = tuple(record for record in fixture.records if record.operation == operation)
        rows = tuple(row for row in evaluation.rows if row.operation == operation)
        cell = CohortAlphaFrontierEvidenceCell(operation, len({source for record in records for source in record.source_ids}), len(records), sum(row.expected_state.value == "supported" for row in rows), sum(row.expected_state.value != "supported" for row in rows), sum(policy.for_record(row.record_id).disposition.value == "publish" for row in rows), lineage.closed, quality.accepted, "")
        address = content_hash({"operation": operation, "source_count": cell.source_count, "record_count": cell.record_count, "supported": cell.supported_count, "boundary": cell.boundary_count, "publish": cell.publish_count, "lineage": cell.lineage_closed, "quality": cell.quality_accepted}, prefix="alpha-evidence-cell")
        cells.append(CohortAlphaFrontierEvidenceCell(operation, cell.source_count, cell.record_count, cell.supported_count, cell.boundary_count, cell.publish_count, cell.lineage_closed, cell.quality_accepted, address))
    values = tuple(cells)
    return CohortAlphaFrontierEvidenceMatrix(values, len(values) == 4 and all(item.record_count == 4 and item.lineage_closed and item.quality_accepted for item in values), content_hash(values, prefix="alpha-evidence-matrix"))


__all__ = ["CohortAlphaFrontierEvidenceCell", "CohortAlphaFrontierEvidenceMatrix", "build_cohort_alpha_frontier_evidence_matrix"]
