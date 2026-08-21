"""Source-to-receipt lineage for the C09-C12 evidence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_public_data import AtlasAlphaEvidenceFixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceLineageEdge:
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
class AtlasAlphaEvidenceLineageReport:
    fixture_id: str
    fixture_address: str
    edges: tuple[AtlasAlphaEvidenceLineageEdge, ...]
    source_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.edges) and all(edge.source_ids for edge in self.edges)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_atlas_alpha_evidence_lineage(
    fixture: AtlasAlphaEvidenceFixture, evaluation: AtlasAlphaEvidenceEvaluationReport
) -> AtlasAlphaEvidenceLineageReport:
    """Create one explicit source-to-sanitized-receipt edge per record."""

    records = fixture.record_map()
    edges: list[AtlasAlphaEvidenceLineageEdge] = []
    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        body = {
            "record_id": receipt.record_id,
            "source_ids": record.source_ids,
            "operation": receipt.operation,
            "output_state": receipt.adapter_state,
            "output_address": receipt.content_address,
            "transformation": "parse public aggregate payload, apply declared adapter, emit sanitized receipt",
        }
        edges.append(
            AtlasAlphaEvidenceLineageEdge(
                "edge:" + content_hash(body).split(":", 1)[1][:24],
                **body,
                content_address=content_hash(body),
            )
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "edges": edges,
        "source_ids": tuple(source.source_id for source in fixture.sources),
    }
    return AtlasAlphaEvidenceLineageReport(
        fixture.fixture_id,
        fixture.content_address,
        tuple(edges),
        body["source_ids"],
        content_hash(body),
    )


def verify_atlas_alpha_evidence_lineage(
    lineage: AtlasAlphaEvidenceLineageReport,
    fixture: AtlasAlphaEvidenceFixture,
    evaluation: AtlasAlphaEvidenceEvaluationReport,
) -> tuple[str, ...]:
    """Return failed lineage checks; an empty tuple is accepted."""

    failures: list[str] = []
    if (
        lineage.fixture_id != fixture.fixture_id
        or lineage.fixture_address != fixture.content_address
    ):
        failures.append("fixture-identity")
    if set(lineage.source_ids) != {source.source_id for source in fixture.sources}:
        failures.append("source-closure")
    if tuple(edge.record_id for edge in lineage.edges) != tuple(
        item.record_id for item in evaluation.receipts
    ):
        failures.append("record-order")
    if any(not edge.output_address.startswith("sha256:") for edge in lineage.edges):
        failures.append("output-addresses")
    if any(
        "input_text" in edge.transformation or "patient" in edge.transformation.lower()
        for edge in lineage.edges
    ):
        failures.append("sanitized-transformation")
    return tuple(failures)


__all__ = [
    "AtlasAlphaEvidenceLineageEdge",
    "AtlasAlphaEvidenceLineageReport",
    "build_atlas_alpha_evidence_lineage",
    "verify_atlas_alpha_evidence_lineage",
]
