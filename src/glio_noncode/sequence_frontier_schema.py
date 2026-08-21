"""Typed output schemas for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import SequenceFrontierEvaluationReport
from .sequence_frontier_public_data import SequenceFrontierFixture, SequenceFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierFieldSpec:
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
class SequenceFrontierSchema:
    schema_id: str
    operation: SequenceFrontierOperation
    input_fields: tuple[SequenceFrontierFieldSpec, ...]
    output_fields: tuple[SequenceFrontierFieldSpec, ...]
    review_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        if not self.input_fields or not self.output_fields or not self.review_states:
            raise ValueError("sequence frontier schema requires fields and review states")

    @property
    def output_field_names(self) -> tuple[str, ...]:
        return tuple(item.field_name for item in self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"output_field_names": list(self.output_field_names)}


@dataclass(frozen=True, slots=True)
class SequenceFrontierSchemaCheck:
    check_id: str
    operation: SequenceFrontierOperation | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierSchemaReport:
    fixture_id: str
    schemas: tuple[SequenceFrontierSchema, ...]
    checks: tuple[SequenceFrontierSchemaCheck, ...]
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
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed],
        }


def _field(name: str, field_type: str, interpretation: str) -> SequenceFrontierFieldSpec:
    body = {
        "field_name": name,
        "field_type": field_type,
        "required": True,
        "interpretation": interpretation,
    }
    return SequenceFrontierFieldSpec(**body, content_address=content_hash(body))


def default_sequence_frontier_schemas() -> tuple[SequenceFrontierSchema, ...]:
    common = tuple(
        _field(*item)
        for item in (
            ("input_text", "serialized aggregate text", "local records"),
            ("input_format", "enum", "explicit parser format"),
            ("source_id", "string", "source receipt identity"),
            ("source_version", "string", "source-shaped version"),
            ("context_key", "string", "exact context"),
        )
    )
    return (
        SequenceFrontierSchema(
            "GNC-D06-C13-schema-v1",
            SequenceFrontierOperation.ENHANCER_GRAMMAR,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("pair_count", "integer", "declared pair rules"),
                    ("compatible_pair_count", "integer", "compatible pairs"),
                    ("coverage", "float", "declared coverage"),
                    ("supported_ids", "tuple[string]", "accepted IDs"),
                    ("review_ids", "tuple[string]", "review IDs"),
                    ("issue_codes", "tuple[string]", "issues"),
                )
            ),
            ("review", "out_of_domain", "abstained", "invalid"),
            ("activity", "causality", "clinical"),
            content_hash({"schema": "C13"}),
        ),
        SequenceFrontierSchema(
            "GNC-D06-C14-schema-v1",
            SequenceFrontierOperation.ALLELE_SATURATION,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("point_count", "integer", "alternate allele points"),
                    ("positive_effect_ids", "tuple[string]", "positive delta IDs"),
                    ("review_ids", "tuple[string]", "review IDs"),
                    ("mean_delta", "float", "mean descriptive delta"),
                    ("issue_codes", "tuple[string]", "issues"),
                )
            ),
            ("review", "out_of_domain", "abstained", "invalid"),
            ("effect proof", "clinical", "causality"),
            content_hash({"schema": "C14"}),
        ),
        SequenceFrontierSchema(
            "GNC-D06-C15-schema-v1",
            SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "adapter state"),
                    ("prediction_count", "integer", "prediction values"),
                    ("stable_ids", "tuple[string]", "stable IDs"),
                    ("review_ids", "tuple[string]", "review IDs"),
                    ("mean", "float|none", "descriptive mean"),
                    ("disagreement", "float|none", "range disagreement"),
                    ("issue_codes", "tuple[string]", "issues"),
                )
            ),
            ("review", "out_of_domain", "abstained", "invalid"),
            ("probability", "calibration", "clinical"),
            content_hash({"schema": "C15"}),
        ),
        SequenceFrontierSchema(
            "GNC-D06-C16-schema-v1",
            SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,
            common,
            tuple(
                _field(*item)
                for item in (
                    ("state", "state", "publication state"),
                    ("sequence_ids", "tuple[string]", "published sequence IDs"),
                    ("records_address", "string|none", "record address"),
                    ("bundle_address", "string|none", "bundle address"),
                    ("model_ids", "tuple[string]", "model receipt IDs"),
                    ("issue_codes", "tuple[string]", "issues"),
                )
            ),
            ("review", "out_of_domain", "abstained", "invalid"),
            ("clinical", "causality", "treatment"),
            content_hash({"schema": "C16"}),
        ),
    )


def validate_sequence_frontier_schema(
    fixture: SequenceFrontierFixture,
    evaluation: SequenceFrontierEvaluationReport,
    schemas: tuple[SequenceFrontierSchema, ...] | None = None,
) -> SequenceFrontierSchemaReport:
    selected = schemas or default_sequence_frontier_schemas()
    by_operation = {item.operation: item for item in selected}
    checks: list[SequenceFrontierSchemaCheck] = []

    def add(
        check_id: str, operation: SequenceFrontierOperation | None, passed: bool, detail: str
    ) -> None:
        body = {"check_id": check_id, "operation": operation, "passed": passed, "detail": detail}
        checks.append(SequenceFrontierSchemaCheck(**body, content_address=content_hash(body)))

    add("schema-count", None, len(selected) == 4, "four schemas are declared")
    add(
        "schema-operations",
        None,
        set(by_operation) == set(SequenceFrontierOperation),
        "all operations have schemas",
    )
    add(
        "fixture-context",
        None,
        all(item.context_key == fixture.context_key for item in evaluation.receipts),
        "receipts retain context",
    )
    allowed = {
        "grammar_no_motif_hits",
        "grammar_coverage_below_floor",
        "saturation_uncertainty_above_floor",
        "saturation_no_positive_effect",
        "ensemble_disagreement_above_floor",
        "ensemble_insufficient_predictions",
        "empty_sequence_records",
        "publish_metadata_invalid",
        "sequence_context_mismatch",
    }
    for operation in SequenceFrontierOperation:
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
                item.adapter_state in {"accepted", "published"}
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
            bool(observed) and observed <= allowed,
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
    return SequenceFrontierSchemaReport(
        fixture.fixture_id, selected, tuple(checks), content_hash(body)
    )


def sequence_frontier_schema_manifest(
    schemas: tuple[SequenceFrontierSchema, ...] | None = None,
) -> dict[str, Any]:
    selected = schemas or default_sequence_frontier_schemas()
    return {
        "schemas": [item.to_dict() for item in selected],
        "content_address": content_hash({"schemas": selected}),
    }


__all__ = [
    "SequenceFrontierFieldSpec",
    "SequenceFrontierSchema",
    "SequenceFrontierSchemaCheck",
    "SequenceFrontierSchemaReport",
    "default_sequence_frontier_schemas",
    "sequence_frontier_schema_manifest",
    "validate_sequence_frontier_schema",
]
