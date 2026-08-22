"""Stable compact fields for beta frontier review exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierRecord, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierProjectionField:
    name: str
    description: str
    required: bool
    source: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierProjectionSchema:
    name: str
    fields: tuple[LinkGraphBetaFrontierProjectionField, ...]
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
class LinkGraphBetaFrontierProjectionReport:
    schema: LinkGraphBetaFrontierProjectionSchema
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


def build_link_graph_beta_frontier_projection_schema() -> LinkGraphBetaFrontierProjectionSchema:
    fields = tuple(LinkGraphBetaFrontierProjectionField(name, description, True, source) for name, description, source in (("record_id", "stable fixture identity", "record.record_id"), ("operation", "beta evidence operation", "record.operation"), ("role", "positive or control", "record.role"), ("context_key", "aggregate context", "record.context_key"), ("expected_state", "declared replay state", "record.expected_state"), ("expected_issue_codes", "declared control issues", "record.expected_issue_codes"), ("source_ids", "receipt identifiers", "record.source_ids")))
    return LinkGraphBetaFrontierProjectionSchema("link_graph_beta_frontier_review", fields, "2026.08.beta-projection.v1")


def project_link_graph_beta_frontier_record(record: LinkGraphBetaFrontierRecord, schema: LinkGraphBetaFrontierProjectionSchema | None = None) -> dict[str, Any]:
    value = schema or build_link_graph_beta_frontier_projection_schema()
    source = {"record_id": record.record_id, "operation": record.operation.value, "role": record.role.value, "context_key": record.context_key, "expected_state": record.expected_state, "expected_issue_codes": record.expected_issue_codes, "source_ids": record.source_ids}
    return {field.name: source[field.name] for field in value.fields}


def project_link_graph_beta_frontier_fixture(fixture: LinkGraphBetaFrontierFixture | None = None, *, operation: str | None = None) -> LinkGraphBetaFrontierProjectionReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    schema = build_link_graph_beta_frontier_projection_schema()
    records = tuple(record for record in value.records if operation is None or record.operation.value == operation)
    rows = tuple(project_link_graph_beta_frontier_record(record, schema) for record in records)
    return LinkGraphBetaFrontierProjectionReport(schema, rows, len(rows) == len(records))


def project_link_graph_beta_frontier_evaluation(evaluation: LinkGraphBetaFrontierEvaluation) -> tuple[dict[str, Any], ...]:
    return tuple({"record_id": row.record_id, "operation": row.operation, "role": row.role, "observed_state": row.observed_state, "state_match": row.state_match, "observed_issue_codes": row.observed_issue_codes, "issue_match": row.issue_match} for row in evaluation.rows)


__all__ = ["LinkGraphBetaFrontierProjectionField", "LinkGraphBetaFrontierProjectionReport", "LinkGraphBetaFrontierProjectionSchema", "build_link_graph_beta_frontier_projection_schema", "project_link_graph_beta_frontier_evaluation", "project_link_graph_beta_frontier_fixture", "project_link_graph_beta_frontier_record"]
