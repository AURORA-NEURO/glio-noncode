"""Schema manifest for C05-C08 records and replay output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, CausalBetaFrontierOperation
from .causal_beta_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierField:
    name: str
    value_type: str
    required: bool
    meaning: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierSchemaReport:
    fields: tuple[CausalBetaFrontierField, ...]
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def field(self, name: str) -> CausalBetaFrontierField:
        return next(item for item in self.fields if item.name == name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": [item.to_dict() for item in self.fields], "checks": self.checks, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_causal_beta_frontier_fields() -> tuple[CausalBetaFrontierField, ...]:
    return tuple(CausalBetaFrontierField(*item) for item in (
        ("record_id", "string", True, "stable row identity"),
        ("operation", "enum", True, "four capability routing key"),
        ("role", "enum", True, "positive or control"),
        ("context_key", "string", True, "exact context gate"),
        ("source_ids", "array[string]", True, "public receipt linkage"),
        ("payload", "object", True, "typed primitive envelope"),
        ("expected_state", "enum", True, "replay state floor"),
        ("expected_issue_codes", "array[string]", False, "control issue floor"),
        ("description", "string", True, "row intent"),
        ("content_address", "string", True, "row receipt"),
    ))


def validate_causal_beta_frontier_schema(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation | None = None) -> CausalBetaFrontierSchemaReport:
    fields = default_causal_beta_frontier_fields()
    checks = (
        check("field_names", len(fields) == len({item.name for item in fields}), "field names unique"),
        check("operations", all(item.operation in tuple(CausalBetaFrontierOperation) for item in fixture.records), "operation enum closed"),
        check("record_ids", len(fixture.record_map()) == len(fixture.records), "record IDs unique"),
        check("source_ids", all(item.source_ids for item in fixture.records), "source receipts present"),
        check("payloads", all(item.payload for item in fixture.records), "payloads present"),
        check("addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), "row addresses present"),
        check("evaluation_rows", evaluation is None or len(evaluation.rows) == len(fixture.records), "evaluation aligns"),
    )
    return CausalBetaFrontierSchemaReport(fields, checks, all(item["passed"] for item in checks))


__all__ = ["CausalBetaFrontierField", "CausalBetaFrontierSchemaReport", "default_causal_beta_frontier_fields", "validate_causal_beta_frontier_schema"]
