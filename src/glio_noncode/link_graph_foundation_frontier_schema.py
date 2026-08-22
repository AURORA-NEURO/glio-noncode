"""Record field manifest and envelope validation for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierField:
    name: str
    value_type: str
    required: bool
    meaning: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierSchemaReport:
    fields: tuple[LinkGraphFoundationFrontierField, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def field(self, name: str) -> LinkGraphFoundationFrontierField:
        for item in self.fields:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": [item.to_dict() for item in self.fields], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_foundation_frontier_fields() -> tuple[LinkGraphFoundationFrontierField, ...]:
    return tuple(LinkGraphFoundationFrontierField(name, kind, required, meaning) for name, kind, required, meaning in (("record_id", "string", True, "stable record identity"), ("operation", "enum", True, "primitive routing"), ("role", "enum", True, "positive or control"), ("context_key", "string", True, "context gate"), ("source_ids", "array[string]", True, "receipt linkage"), ("payload", "object", True, "primitive input"), ("expected_state", "enum", True, "replay state"), ("expected_issue_codes", "array[string]", False, "control behavior"), ("expected_measurements", "object", False, "quantitative control")))


def validate_link_graph_foundation_frontier_schema(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierSchemaReport:
    fields = default_link_graph_foundation_frontier_fields()
    checks = (check("field_names", len({item.name for item in fields}) == len(fields), "schema names are unique"), check("operations", all(record.operation in tuple(LinkGraphFoundationFrontierOperation) for record in fixture.records), "operation enum is closed"), check("record_ids", len({record.record_id for record in fixture.records}) == len(fixture.records), "record IDs are unique"), check("payloads", all(record.payload for record in fixture.records), "payloads are non-empty"), check("evaluation_rows", evaluation is None or len(evaluation.rows) == len(fixture.records), "evaluation rows align"))
    return LinkGraphFoundationFrontierSchemaReport(fields, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierField", "LinkGraphFoundationFrontierSchemaReport", "default_link_graph_foundation_frontier_fields", "validate_link_graph_foundation_frontier_schema"]
