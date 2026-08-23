"""Provenance receipts and exact-context source closure for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


@dataclass(frozen=True, slots=True)
class CohortFoundationProvenanceReceipt:
    receipt_id: str
    record_id: str
    operation: str
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    context_key: str
    input_address: str
    output_address: str
    aggregate_boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationProvenanceGraph:
    receipts: tuple[CohortFoundationProvenanceReceipt, ...]
    source_count: int
    closed: bool
    content_address: str

    def for_record(self, record_id: str) -> CohortFoundationProvenanceReceipt:
        return next(item for item in self.receipts if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_provenance(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation) -> CohortFoundationProvenanceGraph:
    source_map = {item.source_id: item for item in fixture.sources}
    receipts = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        versions = tuple(sorted(source_map[source_id].version for source_id in record.source_ids if source_id in source_map))
        body = {"record_id": record.record_id, "operation": record.operation.value, "source_ids": record.source_ids, "versions": versions, "context_key": fixture.context_key, "input": record.payload, "output": execution.output}
        receipts.append(CohortFoundationProvenanceReceipt(content_hash((record.record_id, "provenance"), prefix="receipt"), record.record_id, record.operation.value, record.source_ids, versions, fixture.context_key, content_hash(record.payload), execution.content_address, fixture.boundary, content_hash(body)))
    graph = CohortFoundationProvenanceGraph(tuple(receipts), len(source_map), all(set(item.source_ids) <= set(source_map) for item in fixture.records), "")
    return CohortFoundationProvenanceGraph(graph.receipts, graph.source_count, graph.closed, content_hash(graph.to_dict()))


__all__ = ["CohortFoundationProvenanceGraph", "CohortFoundationProvenanceReceipt", "build_cohort_foundation_frontier_provenance"]
