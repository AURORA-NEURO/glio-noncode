"""Field-level schema manifest and fixture envelope validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture, LinkGraphAlphaFrontierOperation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierFieldSpec:
    name: str
    value_type: str
    required: bool
    semantic_role: str
    null_policy: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierSchemaReport:
    fields: tuple[LinkGraphAlphaFrontierFieldSpec, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def field(self, name: str) -> LinkGraphAlphaFrontierFieldSpec:
        for item in self.fields:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": [item.to_dict() for item in self.fields], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_schema() -> tuple[LinkGraphAlphaFrontierFieldSpec, ...]:
    return (
        LinkGraphAlphaFrontierFieldSpec("record_id", "string", True, "stable row identity", "reject"),
        LinkGraphAlphaFrontierFieldSpec("operation", "enum", True, "capability routing", "reject"),
        LinkGraphAlphaFrontierFieldSpec("role", "enum", True, "positive or control role", "reject"),
        LinkGraphAlphaFrontierFieldSpec("context_key", "string", True, "context gate", "reject"),
        LinkGraphAlphaFrontierFieldSpec("source_ids", "array[string]", True, "receipt linkage", "reject"),
        LinkGraphAlphaFrontierFieldSpec("payload", "object", True, "primitive input", "reject"),
        LinkGraphAlphaFrontierFieldSpec("expected_state", "enum", True, "replay expectation", "reject"),
        LinkGraphAlphaFrontierFieldSpec("expected_issue_codes", "array[string]", False, "control expectations", "empty"),
        LinkGraphAlphaFrontierFieldSpec("expected_measurements", "object", False, "quantitative expectations", "empty"),
    )


def validate_link_graph_alpha_frontier_schema(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation | None = None) -> LinkGraphAlphaFrontierSchemaReport:
    fields = default_link_graph_alpha_frontier_schema()
    checks = [
        check("field_ids_unique", len({item.name for item in fields}) == len(fields), "schema field names are unique"),
        check("operation_values_known", all(record.operation in tuple(LinkGraphAlphaFrontierOperation) for record in fixture.records), "all operations use the closed enum"),
        check("record_ids_unique", len({record.record_id for record in fixture.records}) == len(fixture.records), "record identifiers are unique"),
        check("context_present", all(record.context_key for record in fixture.records), "context keys are required"),
        check("payload_present", all(record.payload for record in fixture.records), "primitive payloads are non-empty"),
        check("evaluation_rows_aligned", evaluation is None or len(evaluation.rows) == len(fixture.records), "evaluation row count aligns with fixture"),
    ]
    return LinkGraphAlphaFrontierSchemaReport(fields, tuple(checks), all(item.passed for item in checks))


def link_graph_alpha_frontier_schema_manifest() -> dict[str, Any]:
    report = validate_link_graph_alpha_frontier_schema(default_fixture := __import__("glio_noncode.link_graph_alpha_frontier_public_data", fromlist=["default_link_graph_alpha_frontier_fixture"]).default_link_graph_alpha_frontier_fixture())
    return report.to_dict()


__all__ = ["LinkGraphAlphaFrontierFieldSpec", "LinkGraphAlphaFrontierSchemaReport", "default_link_graph_alpha_frontier_schema", "link_graph_alpha_frontier_schema_manifest", "validate_link_graph_alpha_frontier_schema"]
