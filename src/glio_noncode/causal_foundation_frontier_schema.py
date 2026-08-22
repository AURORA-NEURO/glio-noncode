"""Schema manifest and envelope checks for causal foundation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture, CausalFoundationFrontierOperation
from .causal_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierField:
    name: str
    value_type: str
    required: bool
    meaning: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierSchemaReport:
    fields: tuple[CausalFoundationFrontierField, ...]
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def field(self, name: str) -> CausalFoundationFrontierField:
        return next(item for item in self.fields if item.name == name)

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": [item.to_dict() for item in self.fields], "checks": self.checks, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_causal_foundation_frontier_fields() -> tuple[CausalFoundationFrontierField, ...]:
    return tuple(CausalFoundationFrontierField(name, value_type, required, meaning) for name, value_type, required, meaning in (
        ("record_id", "string", True, "stable record identity"),
        ("operation", "enum", True, "four-module routing"),
        ("role", "enum", True, "positive or control"),
        ("context_key", "string", True, "exact context gate"),
        ("source_ids", "array[string]", True, "public receipt linkage"),
        ("payload", "object", True, "primitive input envelope"),
        ("expected_state", "enum", True, "replay state"),
        ("expected_issue_codes", "array[string]", False, "control floor"),
        ("description", "string", True, "row purpose"),
        ("content_address", "string", True, "record receipt"),
    ))


def validate_causal_foundation_frontier_schema(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation | None = None) -> CausalFoundationFrontierSchemaReport:
    fields = default_causal_foundation_frontier_fields()
    checks = (
        check("field_names", len({item.name for item in fields}) == len(fields), "schema field names unique"),
        check("operations", all(item.operation in tuple(CausalFoundationFrontierOperation) for item in fixture.records), "operation enum closed"),
        check("record_ids", len(fixture.record_map()) == len(fixture.records), "record IDs unique"),
        check("source_ids", all(item.source_ids for item in fixture.records), "source receipts present"),
        check("payloads", all(item.payload for item in fixture.records), "payloads present"),
        check("addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), "record addresses present"),
        check("evaluation_rows", evaluation is None or len(evaluation.rows) == len(fixture.records), "evaluation aligns"),
    )
    return CausalFoundationFrontierSchemaReport(fields, checks, all(item["passed"] for item in checks))


__all__ = ["CausalFoundationFrontierField", "CausalFoundationFrontierSchemaReport", "default_causal_foundation_frontier_fields", "validate_causal_foundation_frontier_schema"]
