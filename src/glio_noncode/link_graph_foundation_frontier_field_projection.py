"""Stable field projections for compact review and export surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierRecord, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProjectionField:
    name: str
    description: str
    required: bool
    source: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProjectionSchema:
    name: str
    fields: tuple[LinkGraphFoundationFrontierProjectionField, ...]
    version: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"name": self.name, "version": self.version, "fields": [item.to_dict() for item in self.fields]}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProjectionReport:
    schema: LinkGraphFoundationFrontierProjectionSchema
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"schema": self.schema.to_dict(), "rows": self.rows, "row_count": len(self.rows), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_projection_schema() -> LinkGraphFoundationFrontierProjectionSchema:
    fields = (LinkGraphFoundationFrontierProjectionField("record_id", "stable fixture record identifier", True, "record.record_id"), LinkGraphFoundationFrontierProjectionField("operation", "link operation name", True, "record.operation"), LinkGraphFoundationFrontierProjectionField("role", "positive or control role", True, "record.role"), LinkGraphFoundationFrontierProjectionField("context_key", "aggregate reference context", True, "record.context_key"), LinkGraphFoundationFrontierProjectionField("expected_state", "declared state", True, "record.expected_state"), LinkGraphFoundationFrontierProjectionField("expected_issue_codes", "declared issue set", True, "record.expected_issue_codes"), LinkGraphFoundationFrontierProjectionField("source_ids", "receipt identifiers", True, "record.source_ids"))
    return LinkGraphFoundationFrontierProjectionSchema("link_graph_foundation_frontier_review", fields, "2026.08.projection.v1")


def project_link_graph_foundation_frontier_record(record: LinkGraphFoundationFrontierRecord, schema: LinkGraphFoundationFrontierProjectionSchema | None = None) -> dict[str, Any]:
    value = schema or build_link_graph_foundation_frontier_projection_schema()
    source = {"record_id": record.record_id, "operation": record.operation.value, "role": record.role.value, "context_key": record.context_key, "expected_state": record.expected_state, "expected_issue_codes": record.expected_issue_codes, "source_ids": record.source_ids}
    return {field.name: source[field.name] for field in value.fields if field.name in source}


def project_link_graph_foundation_frontier_fixture(fixture: LinkGraphFoundationFrontierFixture | None = None, *, operation: str | None = None, role: str | None = None) -> LinkGraphFoundationFrontierProjectionReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    schema = build_link_graph_foundation_frontier_projection_schema()
    records: Iterable[LinkGraphFoundationFrontierRecord] = value.records
    if operation is not None:
        records = tuple(item for item in records if item.operation.value == operation)
    if role is not None:
        records = tuple(item for item in records if item.role.value == role)
    rows = tuple(project_link_graph_foundation_frontier_record(record, schema) for record in records)
    return LinkGraphFoundationFrontierProjectionReport(schema, rows, len(rows) == len(tuple(records)))


def project_link_graph_foundation_frontier_evaluation(evaluation: LinkGraphFoundationFrontierEvaluation) -> tuple[dict[str, Any], ...]:
    return tuple({"record_id": row.record_id, "operation": row.operation, "role": row.role, "observed_state": row.observed_state, "state_match": row.state_match, "observed_issue_codes": row.observed_issue_codes, "issue_match": row.issue_match} for row in evaluation.rows)


__all__ = ["LinkGraphFoundationFrontierProjectionField", "LinkGraphFoundationFrontierProjectionReport", "LinkGraphFoundationFrontierProjectionSchema", "build_link_graph_foundation_frontier_projection_schema", "project_link_graph_foundation_frontier_evaluation", "project_link_graph_foundation_frontier_fixture", "project_link_graph_foundation_frontier_record"]
