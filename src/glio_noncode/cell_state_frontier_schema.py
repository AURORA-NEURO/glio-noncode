"""Serializable schema declarations and shape validation for Domain 08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_fixture_eval import CellStateFrontierEvaluationReport
from .cell_state_frontier_public_data import CellStateFrontierFixture, CellStateFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CellStateFrontierFieldSpec:
    name: str
    value_type: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierSchema:
    schema_id: str
    operation: CellStateFrontierOperation
    common_fields: tuple[str, ...]
    output_fields: tuple[CellStateFrontierFieldSpec, ...]
    review_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        if not self.common_fields or not self.output_fields:
            raise ValueError("cell state schema requires fields")

    @property
    def output_field_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierSchemaCheck:
    check_id: str
    operation: CellStateFrontierOperation | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierSchemaReport:
    fixture_id: str
    schemas: tuple[CellStateFrontierSchema, ...]
    checks: tuple[CellStateFrontierSchemaCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.schemas) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def _field(name: str, value_type: str, description: str) -> CellStateFrontierFieldSpec:
    return CellStateFrontierFieldSpec(name, value_type, description)


def default_cell_state_frontier_schemas() -> tuple[CellStateFrontierSchema, ...]:
    common = ("state", "context_key", "source_ids", "issue_codes")
    return (
        CellStateFrontierSchema(
            "GNC-D08-C13-schema-v1",
            CellStateFrontierOperation.ABUNDANCE_INTERVAL,
            common,
            tuple(_field(*item) for item in (("state", "state", "adapter state"), ("estimate_count", "integer", "estimates"), ("stable_ids", "list[string]", "stable estimate IDs"), ("review_ids", "list[string]", "review IDs"), ("abundances", "list[float]", "bounded abundance values"), ("intervals", "list[list[float]]", "uncertainty intervals"), ("issue_codes", "list[string]", "issues"))),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("clinical", "diagnostic", "truth"),
            content_hash({"schema": "D08-C13"}),
        ),
        CellStateFrontierSchema(
            "GNC-D08-C14-schema-v1",
            CellStateFrontierOperation.REFERENCE_MAPPING,
            common,
            tuple(_field(*item) for item in (("state", "state", "adapter state"), ("mapping_count", "integer", "mapping rows"), ("mapped_ids", "list[string]", "mapped cell IDs"), ("review_ids", "list[string]", "review IDs"), ("reference_state_ids", "list[string|none]", "reference state IDs"), ("margins", "list[float]", "top-second margins"), ("issue_codes", "list[string]", "issues"))),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("clinical", "diagnostic", "identity truth"),
            content_hash({"schema": "D08-C14"}),
        ),
        CellStateFrontierSchema(
            "GNC-D08-C15-schema-v1",
            CellStateFrontierOperation.OOD_DETECTION,
            common,
            tuple(_field(*item) for item in (("state", "state", "adapter state"), ("finding_count", "integer", "findings"), ("in_domain_ids", "list[string]", "in-domain IDs"), ("ood_ids", "list[string]", "out-of-domain IDs"), ("review_ids", "list[string]", "review IDs"), ("distances", "list[float]", "distances"), ("support_scores", "list[float]", "support scores"), ("issue_codes", "list[string]", "issues"))),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("clinical", "diagnostic", "diagnosis", "truth"),
            content_hash({"schema": "D08-C15"}),
        ),
        CellStateFrontierSchema(
            "GNC-D08-C16-schema-v1",
            CellStateFrontierOperation.CONTEXT_PUBLICATION,
            common,
            tuple(_field(*item) for item in (("state", "state", "adapter state"), ("cell_count", "integer", "published cell IDs"), ("receipt_count", "integer", "upstream receipt count"), ("envelope_address", "string|none", "published envelope address"), ("issue_codes", "list[string]", "issues"))),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("clinical", "diagnostic", "treatment", "actionability"),
            content_hash({"schema": "D08-C16"}),
        ),
    )


def validate_cell_state_frontier_schema(
    fixture: CellStateFrontierFixture,
    evaluation: CellStateFrontierEvaluationReport,
    schemas: tuple[CellStateFrontierSchema, ...] | None = None,
) -> CellStateFrontierSchemaReport:
    selected = schemas or default_cell_state_frontier_schemas()
    by_operation = {item.operation: item for item in selected}
    checks: list[CellStateFrontierSchemaCheck] = []

    def add(check_id: str, operation: CellStateFrontierOperation | None, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "operation": operation, "passed": passed, "detail": detail}
        checks.append(CellStateFrontierSchemaCheck(**body, content_address=content_hash(body)))

    add("schema-count", None, len(selected) == 4, "four schemas are declared")
    add("schema-operations", None, set(by_operation) == set(CellStateFrontierOperation), "all operations have schemas")
    add("fixture-context", None, all(item.context_key == fixture.context_key for item in evaluation.receipts), "receipts retain context")
    allowed = {"context_mismatch", "invalid_cell_count", "invalid_interval_multiplier", "ambiguous_reference_mapping", "no_reference_scores", "cell_state_out_of_domain", "invalid_cell_state_row", "empty_cell_ids", "missing_receipt_address"}
    for operation in CellStateFrontierOperation:
        schema = by_operation.get(operation)
        receipts = tuple(item for item in evaluation.receipts if item.operation is operation)
        add(f"{operation.value}:records", operation, schema is not None and len(receipts) == 4, "one positive and three controls")
        if schema is None:
            continue
        add(f"{operation.value}:states", operation, all(item.adapter_state == "supported" or item.adapter_state in schema.review_states for item in receipts), "states are declared")
        summary_keys = set().union(*(item.summary.keys() for item in receipts)) if receipts else set()
        add(f"{operation.value}:outputs", operation, set(schema.output_field_names) <= summary_keys, "summary outputs are declared")
        observed = {code for item in receipts for code in item.observed_issue_codes}
        add(f"{operation.value}:issues", operation, observed <= allowed, "issue vocabulary is bounded")
        add(f"{operation.value}:claims", operation, all(not any(claim in str(item.summary).lower() for claim in schema.prohibited_claims) for item in receipts), "prohibited claims are absent")
    body = {"fixture_id": fixture.fixture_id, "schemas": selected, "checks": checks}
    return CellStateFrontierSchemaReport(fixture.fixture_id, selected, tuple(checks), content_hash(body))


def cell_state_frontier_schema_manifest(schemas: tuple[CellStateFrontierSchema, ...] | None = None) -> dict[str, Any]:
    selected = schemas or default_cell_state_frontier_schemas()
    return {"schemas": [item.to_dict() for item in selected], "content_address": content_hash({"schemas": selected})}


__all__ = [
    "CellStateFrontierFieldSpec",
    "CellStateFrontierSchema",
    "CellStateFrontierSchemaCheck",
    "CellStateFrontierSchemaReport",
    "cell_state_frontier_schema_manifest",
    "default_cell_state_frontier_schemas",
    "validate_cell_state_frontier_schema",
]
