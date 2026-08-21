"""Source-to-receipt lineage for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import SequenceFrontierEvaluationReport
from .sequence_frontier_public_data import SequenceFrontierFixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierLineageEdge:
    edge_id: str
    record_id: str
    source_ids: tuple[str, ...]
    operation: str
    output_state: str
    output_address: str
    transformation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "edge_id",
            "record_id",
            "operation",
            "output_state",
            "output_address",
            "transformation",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("lineage edge requires sources")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierLineageReport:
    fixture_id: str
    fixture_address: str
    edges: tuple[SequenceFrontierLineageEdge, ...]
    source_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.edges) and all(item.source_ids for item in self.edges)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_sequence_frontier_lineage(
    fixture: SequenceFrontierFixture, evaluation: SequenceFrontierEvaluationReport
) -> SequenceFrontierLineageReport:
    records = fixture.record_map()
    edges: list[SequenceFrontierLineageEdge] = []
    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        body = {
            "record_id": receipt.record_id,
            "source_ids": record.source_ids,
            "operation": receipt.operation.value,
            "output_state": receipt.adapter_state,
            "output_address": receipt.content_address,
            "transformation": "parse public aggregate sequence payload, apply declared sequence adapter, emit sanitized receipt",
        }
        address = content_hash(body)
        edges.append(
            SequenceFrontierLineageEdge(
                "edge:" + address.split(":", 1)[1][:24], **body, content_address=address
            )
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "edges": edges,
        "source_ids": tuple(item.source_id for item in fixture.sources),
    }
    return SequenceFrontierLineageReport(
        fixture.fixture_id,
        fixture.content_address,
        tuple(edges),
        body["source_ids"],
        content_hash(body),
    )


def verify_sequence_frontier_lineage(
    lineage: SequenceFrontierLineageReport,
    fixture: SequenceFrontierFixture,
    evaluation: SequenceFrontierEvaluationReport,
) -> tuple[str, ...]:
    failures: list[str] = []
    if (
        lineage.fixture_id != fixture.fixture_id
        or lineage.fixture_address != fixture.content_address
    ):
        failures.append("fixture-identity")
    if set(lineage.source_ids) != {item.source_id for item in fixture.sources}:
        failures.append("source-closure")
    if tuple(item.record_id for item in lineage.edges) != tuple(
        item.record_id for item in evaluation.receipts
    ):
        failures.append("record-order")
    if any(not item.output_address.startswith("sha256:") for item in lineage.edges):
        failures.append("output-addresses")
    if any(
        "input_text" in item.transformation or "patient" in item.transformation.lower()
        for item in lineage.edges
    ):
        failures.append("sanitized-transformation")
    return tuple(failures)


__all__ = [
    "SequenceFrontierLineageEdge",
    "SequenceFrontierLineageReport",
    "build_sequence_frontier_lineage",
    "verify_sequence_frontier_lineage",
]
