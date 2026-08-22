"""Source-to-receipt lineage for Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_public_data import TopologyFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyFrontierLineageEdge:
    edge_id: str
    record_id: str
    source_ids: tuple[str, ...]
    operation: str
    output_state: str
    output_address: str
    transformation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "record_id", "operation", "output_state", "output_address", "transformation", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("topology lineage edge requires sources")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierLineageReport:
    fixture_id: str
    fixture_address: str
    edges: tuple[TopologyFrontierLineageEdge, ...]
    source_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.edges) and all(item.source_ids for item in self.edges)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_topology_frontier_lineage(
    fixture: TopologyFrontierFixture,
    evaluation: TopologyFrontierEvaluationReport,
) -> TopologyFrontierLineageReport:
    records = fixture.record_map()
    edges: list[TopologyFrontierLineageEdge] = []
    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        body = {
            "record_id": receipt.record_id,
            "source_ids": record.source_ids,
            "operation": receipt.operation.value,
            "output_state": receipt.adapter_state,
            "output_address": receipt.content_address,
            "transformation": "parse public aggregate topology rows, apply declared adapter, emit sanitized receipt",
        }
        address = content_hash(body)
        edges.append(TopologyFrontierLineageEdge("edge:" + address.split(":", 1)[1][:24], **body, content_address=address))
    body = {"fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "edges": edges, "source_ids": tuple(item.source_id for item in fixture.sources)}
    return TopologyFrontierLineageReport(fixture.fixture_id, fixture.content_address, tuple(edges), body["source_ids"], content_hash(body))


def verify_topology_frontier_lineage(
    lineage: TopologyFrontierLineageReport,
    fixture: TopologyFrontierFixture,
    evaluation: TopologyFrontierEvaluationReport,
) -> tuple[str, ...]:
    failures: list[str] = []
    if lineage.fixture_id != fixture.fixture_id or lineage.fixture_address != fixture.content_address:
        failures.append("fixture-identity")
    if set(lineage.source_ids) != {item.source_id for item in fixture.sources}:
        failures.append("source-closure")
    if {item.record_id for item in lineage.edges} != {item.record_id for item in evaluation.receipts}:
        failures.append("record-closure")
    receipt_map = {item.record_id: item for item in evaluation.receipts}
    for edge in lineage.edges:
        receipt = receipt_map.get(edge.record_id)
        if receipt is None:
            failures.append(f"missing-receipt:{edge.record_id}")
            continue
        if edge.operation != receipt.operation.value or edge.output_state != receipt.adapter_state:
            failures.append(f"receipt-match:{edge.record_id}")
        if edge.output_address != receipt.content_address:
            failures.append(f"output-address:{edge.record_id}")
        if not set(edge.source_ids) <= set(lineage.source_ids):
            failures.append(f"edge-source:{edge.record_id}")
        if not edge.content_address.startswith("sha256:"):
            failures.append(f"edge-address:{edge.record_id}")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "TopologyFrontierLineageEdge",
    "TopologyFrontierLineageReport",
    "build_topology_frontier_lineage",
    "verify_topology_frontier_lineage",
]
