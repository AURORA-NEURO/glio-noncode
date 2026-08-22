"""Serializable schema declarations and shape validation for Domain 07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_frontier_fixture_eval import ChromatinFrontierEvaluationReport
from .chromatin_frontier_public_data import (
    ChromatinFrontierFixture,
    ChromatinFrontierOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ChromatinFrontierFieldSpec:
    name: str
    value_type: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierSchema:
    schema_id: str
    operation: ChromatinFrontierOperation
    common_fields: tuple[str, ...]
    output_fields: tuple[ChromatinFrontierFieldSpec, ...]
    review_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        if not self.common_fields or not self.output_fields:
            raise ValueError("chromatin frontier schema requires fields")

    @property
    def output_field_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierSchemaCheck:
    check_id: str
    operation: ChromatinFrontierOperation | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierSchemaReport:
    fixture_id: str
    schemas: tuple[ChromatinFrontierSchema, ...]
    checks: tuple[ChromatinFrontierSchemaCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.schemas) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _field(name: str, value_type: str, description: str) -> ChromatinFrontierFieldSpec:
    return ChromatinFrontierFieldSpec(name, value_type, description)


def default_chromatin_frontier_schemas() -> tuple[ChromatinFrontierSchema, ...]:
    common = (
        "state",
        "context_key",
        "source_ids",
        "issue_codes",
    )
    return (
        ChromatinFrontierSchema(
            "GNC-D07-C13-schema-v1",
            ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("observation_count", "integer", "parsed observations"),
                    ("segment_count", "integer", "atomic segments"),
                    ("ambiguous_segment_ids", "list[string]", "ambiguous segment IDs"),
                    ("state_labels", "list[string]", "declared or inferred labels"),
                    ("issue_codes", "list[string]", "issues"),
                )
            ),
            ("ambiguous", "partial", "out_of_domain", "abstained", "invalid"),
            ("truth", "clinical", "causal", "enhancer"),
            content_hash({"schema": "D07-C13"}),
        ),
        ChromatinFrontierSchema(
            "GNC-D07-C14-schema-v1",
            ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("variant_ids", "list[string]", "variant IDs"),
                    ("result_count", "integer", "allele comparison results"),
                    ("directions", "list[string]", "direction labels"),
                    ("median_deltas", "list[float|none]", "descriptive deltas"),
                    ("issue_codes", "list[string]", "issues"),
                )
            ),
            ("ambiguous", "partial", "out_of_domain", "abstained", "invalid"),
            ("causal", "binding", "clinical", "effect proof"),
            content_hash({"schema": "D07-C14"}),
        ),
        ChromatinFrontierSchema(
            "GNC-D07-C15-schema-v1",
            ChromatinFrontierOperation.EPIGENOMIC_PURITY,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("marker_count", "integer", "marker observations"),
                    ("estimate_count", "integer", "marker estimates"),
                    ("aggregate_purity", "float|none", "bounded aggregate estimate"),
                    ("purity_spread", "float|none", "marker spread"),
                    ("estimate_states", "list[string]", "marker states"),
                    ("issue_codes", "list[string]", "issues"),
                )
            ),
            ("ambiguous", "partial", "out_of_domain", "abstained", "invalid"),
            ("clinical", "purity call", "tumor fraction truth", "treatment"),
            content_hash({"schema": "D07-C15"}),
        ),
        ChromatinFrontierSchema(
            "GNC-D07-C16-schema-v1",
            ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("observation_count", "integer", "parsed observations"),
                    ("correction_count", "integer", "correction outputs"),
                    ("corrected_feature_ids", "list[string]", "corrected feature IDs"),
                    ("corrected_signals", "list[float]", "corrected signal values"),
                    ("issue_codes", "list[string]", "issues"),
                )
            ),
            ("ambiguous", "partial", "out_of_domain", "abstained", "invalid"),
            ("causal", "corrected truth", "clinical", "treatment"),
            content_hash({"schema": "D07-C16"}),
        ),
    )


def validate_chromatin_frontier_schema(
    fixture: ChromatinFrontierFixture,
    evaluation: ChromatinFrontierEvaluationReport,
    schemas: tuple[ChromatinFrontierSchema, ...] | None = None,
) -> ChromatinFrontierSchemaReport:
    selected = schemas or default_chromatin_frontier_schemas()
    by_operation = {item.operation: item for item in selected}
    checks: list[ChromatinFrontierSchemaCheck] = []

    def add(
        check_id: str,
        operation: ChromatinFrontierOperation | None,
        passed: bool,
        detail: str,
    ) -> None:
        body = {"check_id": check_id, "operation": operation, "passed": passed, "detail": detail}
        checks.append(ChromatinFrontierSchemaCheck(**body, content_address=content_hash(body)))

    add("schema-count", None, len(selected) == 4, "four schemas are declared")
    add(
        "schema-operations",
        None,
        set(by_operation) == set(ChromatinFrontierOperation),
        "all operations have schemas",
    )
    add(
        "fixture-context",
        None,
        all(item.context_key == fixture.context_key for item in evaluation.receipts),
        "receipts retain context",
    )
    allowed = {
        "context_mismatch",
        "invalid_segmentation_row",
        "invalid_segmentation_threshold",
        "invalid_allele_specific_row",
        "invalid_allele_threshold",
        "invalid_purity_marker",
        "invalid_purity_parameter",
        "invalid_batch_composition_row",
        "invalid_batch_parameter",
    }
    for operation in ChromatinFrontierOperation:
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
                item.adapter_state == "supported" or item.adapter_state in schema.review_states
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
            observed <= allowed,
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
    return ChromatinFrontierSchemaReport(
        fixture.fixture_id,
        selected,
        tuple(checks),
        content_hash(body),
    )


def chromatin_frontier_schema_manifest(
    schemas: tuple[ChromatinFrontierSchema, ...] | None = None,
) -> dict[str, Any]:
    selected = schemas or default_chromatin_frontier_schemas()
    return {
        "schemas": [item.to_dict() for item in selected],
        "content_address": content_hash({"schemas": selected}),
    }


__all__ = [
    "ChromatinFrontierFieldSpec",
    "ChromatinFrontierSchema",
    "ChromatinFrontierSchemaCheck",
    "ChromatinFrontierSchemaReport",
    "chromatin_frontier_schema_manifest",
    "default_chromatin_frontier_schemas",
    "validate_chromatin_frontier_schema",
]
