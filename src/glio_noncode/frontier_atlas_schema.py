"""Typed output schemas and validation for C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_fixture_eval import FrontierAtlasEvaluationReport
from .frontier_atlas_public_data import FrontierAtlasFixture, FrontierAtlasOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasFieldSpec:
    field_name: str
    field_type: str
    required: bool
    interpretation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("field_name", "field_type", "interpretation", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasSchema:
    schema_id: str
    operation: FrontierAtlasOperation
    input_fields: tuple[FrontierAtlasFieldSpec, ...]
    output_fields: tuple[FrontierAtlasFieldSpec, ...]
    review_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        if not self.input_fields or not self.output_fields or not self.review_states:
            raise ValueError("frontier atlas schema requires input, output, and review fields")
        if len({field.field_name for field in self.input_fields}) != len(self.input_fields) or len(
            {field.field_name for field in self.output_fields}
        ) != len(self.output_fields):
            raise ValueError("frontier atlas schema fields must be unique")

    @property
    def output_field_names(self) -> tuple[str, ...]:
        return tuple(field.field_name for field in self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"output_field_names": list(self.output_field_names)}


@dataclass(frozen=True, slots=True)
class FrontierAtlasSchemaCheck:
    check_id: str
    operation: FrontierAtlasOperation | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasSchemaReport:
    fixture_id: str
    schemas: tuple[FrontierAtlasSchema, ...]
    checks: tuple[FrontierAtlasSchemaCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.schemas) and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _field(name: str, field_type: str, interpretation: str) -> FrontierAtlasFieldSpec:
    body = {
        "field_name": name,
        "field_type": field_type,
        "required": True,
        "interpretation": interpretation,
    }
    return FrontierAtlasFieldSpec(**body, content_address=content_hash(body))


def _schema(
    operation: FrontierAtlasOperation,
    suffix: str,
    outputs: tuple[tuple[str, str, str], ...],
    claims: tuple[str, ...],
) -> FrontierAtlasSchema:
    common = tuple(
        _field(name, field_type, interpretation)
        for name, field_type, interpretation in (
            ("input_text", "serialized aggregate text", "local records"),
            ("input_format", "enum", "explicit parser format"),
            ("source_id", "string", "source receipt identity"),
            ("source_version", "string", "source-shaped version"),
            ("context_key", "string", "exact context"),
        )
    )
    return_body = {
        "schema_id": f"GNC-D05-{suffix}-schema-v1",
        "operation": operation,
        "input_fields": common,
        "output_fields": tuple(_field(*item) for item in outputs),
        "review_states": ("review", "out_of_domain", "abstained", "invalid"),
        "prohibited_claims": claims,
    }
    return FrontierAtlasSchema(**return_body, content_address=content_hash(return_body))


def default_frontier_atlas_schemas() -> tuple[FrontierAtlasSchema, ...]:
    return (
        _schema(
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            "C13",
            (
                ("state", "state", "adapter state"),
                ("observation_count", "integer", "observations"),
                ("strong_boundary_ids", "tuple[string]", "accepted IDs"),
                ("review_ids", "tuple[string]", "review IDs"),
                ("issue_codes", "tuple[string]", "issues"),
            ),
            ("causality", "clinical effect"),
        ),
        _schema(
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            "C14",
            (
                ("state", "state", "adapter state"),
                ("observation_count", "integer", "hotspot observations"),
                ("supported_ids", "tuple[string]", "supported IDs"),
                ("review_ids", "tuple[string]", "review IDs"),
                ("issue_codes", "tuple[string]", "issues"),
            ),
            ("mechanism", "causality", "clinical effect"),
        ),
        _schema(
            FrontierAtlasOperation.EVIDENCE_TIER,
            "C15",
            (
                ("state", "state", "adapter state"),
                ("decision_count", "integer", "tier decisions"),
                ("high_confidence_ids", "tuple[string]", "high-tier IDs"),
                ("review_ids", "tuple[string]", "review IDs"),
                ("evidence_tiers", "tuple[string]", "declared tier labels"),
                ("issue_codes", "tuple[string]", "issues"),
            ),
            ("probability", "clinical confidence"),
        ),
        _schema(
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            "C16",
            (
                ("state", "state", "adapter state"),
                ("record_count", "integer", "published records"),
                ("records_address", "string|none", "content address of records"),
                ("snapshot_address", "string|none", "content address of manifest"),
                ("schema_version", "string|none", "snapshot schema"),
                ("issue_codes", "tuple[string]", "issues"),
            ),
            ("clinical", "causality", "treatment"),
        ),
    )


def validate_frontier_atlas_schema(
    fixture: FrontierAtlasFixture,
    evaluation: FrontierAtlasEvaluationReport,
    schemas: tuple[FrontierAtlasSchema, ...] | None = None,
) -> FrontierAtlasSchemaReport:
    selected = schemas or default_frontier_atlas_schemas()
    by_operation = {schema.operation: schema for schema in selected}
    checks: list[FrontierAtlasSchemaCheck] = []

    def add(
        check_id: str, operation: FrontierAtlasOperation | None, passed: bool, detail: str
    ) -> None:
        body = {"check_id": check_id, "operation": operation, "passed": passed, "detail": detail}
        checks.append(FrontierAtlasSchemaCheck(**body, content_address=content_hash(body)))

    add("schema-count", None, len(selected) == 4, "four schemas are declared")
    add(
        "schema-operations",
        None,
        set(by_operation) == set(FrontierAtlasOperation),
        "all operations have schemas",
    )
    add(
        "fixture-context",
        None,
        all(item.context_key == fixture.context_key for item in evaluation.receipts),
        "receipts retain context",
    )
    allowed_issues = {
        "boundary_low_support",
        "invalid_boundary_interval",
        "boundary_context_mismatch",
        "insufficient_hotspot_sources",
        "hotspot_direction_disagreement",
        "hotspot_context_mismatch",
        "low_evidence_tier",
        "no_evidence_sources",
        "tier_context_mismatch",
        "empty_snapshot_records",
        "snapshot_context_mismatch",
        "snapshot_metadata_invalid",
    }
    for operation in FrontierAtlasOperation:
        schema = by_operation.get(operation)
        receipts = tuple(item for item in evaluation.receipts if item.operation is operation)
        add(
            f"{operation.value}:records",
            operation,
            schema is not None and len(receipts) == 4,
            "one positive and three controls",
        )
        if schema is None:
            continue
        add(
            f"{operation.value}:states",
            operation,
            all(
                item.adapter_state == "accepted"
                or item.adapter_state == "published"
                or item.adapter_state in schema.review_states
                for item in receipts
            ),
            "states are declared",
        )
        summary_keys = (
            set().union(*(item.summary.keys() for item in receipts)) if receipts else set()
        )
        add(
            f"{operation.value}:outputs",
            operation,
            set(schema.output_field_names) <= summary_keys,
            "summary outputs are declared",
        )
        observed = {code for item in receipts for code in item.observed_issue_codes}
        add(
            f"{operation.value}:issues",
            operation,
            bool(observed) and observed <= allowed_issues,
            "issue vocabulary is bounded",
        )
        add(
            f"{operation.value}:claims",
            operation,
            all(
                not any(claim in str(item.summary).lower() for claim in schema.prohibited_claims)
                for item in receipts
            ),
            "prohibited claims are absent",
        )
    body = {"fixture_id": fixture.fixture_id, "schemas": selected, "checks": checks}
    return FrontierAtlasSchemaReport(
        fixture.fixture_id, selected, tuple(checks), content_hash(body)
    )


def frontier_atlas_schema_manifest(
    schemas: tuple[FrontierAtlasSchema, ...] | None = None,
) -> dict[str, Any]:
    selected = schemas or default_frontier_atlas_schemas()
    return {
        "schemas": [schema.to_dict() for schema in selected],
        "content_address": content_hash({"schemas": selected}),
    }


__all__ = [
    "FrontierAtlasFieldSpec",
    "FrontierAtlasSchema",
    "FrontierAtlasSchemaCheck",
    "FrontierAtlasSchemaReport",
    "default_frontier_atlas_schemas",
    "frontier_atlas_schema_manifest",
    "validate_frontier_atlas_schema",
]
