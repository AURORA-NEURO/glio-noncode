"""Schema registry and output-shape validation for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_public_data import AtlasAlphaEvidenceFixture, AtlasAlphaEvidenceOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceFieldSpec:
    """One field's type and interpretation contract."""

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
class AtlasAlphaEvidenceSchema:
    """Input/output schema for one operation family."""

    schema_id: str
    operation: AtlasAlphaEvidenceOperation
    input_fields: tuple[AtlasAlphaEvidenceFieldSpec, ...]
    output_fields: tuple[AtlasAlphaEvidenceFieldSpec, ...]
    review_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        if not self.input_fields or not self.output_fields:
            raise ValueError("schema requires input and output fields")
        if len({field.field_name for field in self.input_fields}) != len(self.input_fields):
            raise ValueError("schema input fields must be unique")
        if len({field.field_name for field in self.output_fields}) != len(self.output_fields):
            raise ValueError("schema output fields must be unique")
        if not self.review_states:
            raise ValueError("schema requires review states")

    @property
    def required_input_fields(self) -> tuple[str, ...]:
        return tuple(field.field_name for field in self.input_fields if field.required)

    @property
    def output_field_names(self) -> tuple[str, ...]:
        return tuple(field.field_name for field in self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "required_input_fields": list(self.required_input_fields),
            "output_field_names": list(self.output_field_names),
        }


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceSchemaCheck:
    """One schema validation result."""

    check_id: str
    operation: AtlasAlphaEvidenceOperation | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceSchemaReport:
    """Schema manifest and validation result."""

    fixture_id: str
    schemas: tuple[AtlasAlphaEvidenceSchema, ...]
    checks: tuple[AtlasAlphaEvidenceSchemaCheck, ...]
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


def _field(
    name: str, field_type: str, required: bool, interpretation: str
) -> AtlasAlphaEvidenceFieldSpec:
    body = {
        "field_name": name,
        "field_type": field_type,
        "required": required,
        "interpretation": interpretation,
    }
    return AtlasAlphaEvidenceFieldSpec(**body, content_address=content_hash(body))


def _schema(
    operation: AtlasAlphaEvidenceOperation,
    suffix: str,
    inputs: tuple[AtlasAlphaEvidenceFieldSpec, ...],
    outputs: tuple[AtlasAlphaEvidenceFieldSpec, ...],
    claims: tuple[str, ...],
) -> AtlasAlphaEvidenceSchema:
    body = {
        "schema_id": f"GNC-D05-{suffix}-schema-v1",
        "operation": operation,
        "input_fields": inputs,
        "output_fields": outputs,
        "review_states": ("partial", "ambiguous", "abstained", "out_of_domain", "invalid"),
        "prohibited_claims": claims,
    }
    return AtlasAlphaEvidenceSchema(**body, content_address=content_hash(body))


def _common_inputs() -> tuple[AtlasAlphaEvidenceFieldSpec, ...]:
    return (
        _field(
            "input_text", "serialized aggregate text", True, "serialized records are parsed locally"
        ),
        _field("input_format", "enum", True, "format is explicit and versioned"),
        _field("source_id", "string", True, "local fixture source identity"),
        _field("source_version", "string", True, "local fixture source version"),
        _field(
            "context_key",
            "string",
            True,
            "exact genome, disease, age, state, territory, treatment context",
        ),
    )


def default_atlas_alpha_evidence_schemas() -> tuple[AtlasAlphaEvidenceSchema, ...]:
    """Return complete input/output schemas for all C09-C12 adapters."""

    common = _common_inputs()
    return (
        _schema(
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            "C09",
            common
            + (
                _field(
                    "spread_tolerance",
                    "non-negative float",
                    True,
                    "replicate signal disagreement threshold",
                ),
                _field("minimum_signal", "non-negative float", True, "descriptive signal floor"),
            ),
            tuple(
                _field(name, field_type, True, interpretation)
                for name, field_type, interpretation in (
                    ("state", "state", "adapter state"),
                    ("observation_count", "integer", "accepted observations"),
                    ("interval_count", "integer", "atomic observed intervals"),
                    ("signal_spreads", "tuple[float]", "replicate spread per interval"),
                    ("replicate_counts", "tuple[integer]", "replicate identity cardinality"),
                    ("issue_codes", "tuple[string]", "row and review issue vocabulary"),
                )
            ),
            ("activity", "causality", "clinical effect"),
        ),
        _schema(
            AtlasAlphaEvidenceOperation.METHYLATION,
            "C10",
            common
            + (
                _field(
                    "spread_tolerance",
                    "non-negative float",
                    True,
                    "replicate fraction disagreement threshold",
                ),
            ),
            tuple(
                _field(name, field_type, True, interpretation)
                for name, field_type, interpretation in (
                    ("state", "state", "adapter state"),
                    ("observation_count", "integer", "accepted observations"),
                    ("interval_count", "integer", "atomic observed intervals"),
                    ("coverage_totals", "tuple[integer]", "retained total counts"),
                    ("fraction_spreads", "tuple[float|none]", "replicate fraction spread"),
                    ("issue_codes", "tuple[string]", "coverage and review issue vocabulary"),
                )
            ),
            ("silencing", "negative regulation", "clinical effect"),
        ),
        _schema(
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            "C11",
            common
            + (
                _field("role_threshold", "unit interval float", True, "role score threshold"),
                _field(
                    "methylation_silencer_threshold",
                    "unit interval float",
                    True,
                    "candidate threshold",
                ),
            ),
            tuple(
                _field(name, field_type, True, interpretation)
                for name, field_type, interpretation in (
                    ("state", "state", "adapter state"),
                    ("classification_count", "integer", "classified elements"),
                    ("roles", "tuple[tuple[string]]", "declared role labels"),
                    ("missing_channels", "tuple[tuple[string]]", "missing evidence channels"),
                    ("target_gene_ids", "tuple[string]", "declared targets"),
                    ("issue_codes", "tuple[string]", "role review issue vocabulary"),
                )
            ),
            ("causality", "binding certainty", "clinical effect"),
        ),
        _schema(
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            "C12",
            common
            + (
                _field(
                    "minimum_constituents", "positive integer", True, "candidate constituent floor"
                ),
                _field(
                    "merge_gap_bp", "non-negative integer", True, "interval proximity threshold"
                ),
                _field("rank_quantile", "unit interval float", True, "rank selection quantile"),
            ),
            tuple(
                _field(name, field_type, True, interpretation)
                for name, field_type, interpretation in (
                    ("state", "state", "adapter state"),
                    ("constituent_count", "integer", "accepted enhancer constituents"),
                    ("candidate_count", "integer", "ranked candidate groups"),
                    ("candidate_ids", "tuple[string]", "candidate identities"),
                    ("target_gene_ids", "tuple[string]", "declared targets"),
                    ("issue_codes", "tuple[string]", "candidate review issue vocabulary"),
                )
            ),
            ("causality", "enhancer activity probability", "clinical effect"),
        ),
    )


def validate_atlas_alpha_evidence_schema(
    fixture: AtlasAlphaEvidenceFixture,
    evaluation: AtlasAlphaEvidenceEvaluationReport,
    schemas: tuple[AtlasAlphaEvidenceSchema, ...] | None = None,
) -> AtlasAlphaEvidenceSchemaReport:
    """Validate operation coverage, output keys, context, and issue vocabulary."""

    selected = schemas or default_atlas_alpha_evidence_schemas()
    by_operation = {schema.operation: schema for schema in selected}
    checks: list[AtlasAlphaEvidenceSchemaCheck] = []

    def add(
        check_id: str, operation: AtlasAlphaEvidenceOperation | None, passed: bool, detail: str
    ) -> None:
        body = {"check_id": check_id, "operation": operation, "passed": passed, "detail": detail}
        checks.append(AtlasAlphaEvidenceSchemaCheck(**body, content_address=content_hash(body)))

    add("schema-count", None, len(selected) == 4, "four operation schemas are declared")
    add(
        "schema-operations",
        None,
        set(by_operation) == set(AtlasAlphaEvidenceOperation),
        "all operations have schemas",
    )
    add(
        "fixture-context",
        None,
        fixture.context_key
        and all(item.context_key == fixture.context_key for item in evaluation.receipts),
        "all receipts use the fixture context",
    )
    for operation in AtlasAlphaEvidenceOperation:
        schema = by_operation.get(operation)
        receipts = tuple(item for item in evaluation.receipts if item.operation is operation)
        add(
            f"{operation.value}:records",
            operation,
            schema is not None and len(receipts) == 4,
            "operation has one positive and three controls",
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
            "states are in the declared vocabulary",
        )
        summary_keys = (
            set().union(*(item.summary.keys() for item in receipts)) if receipts else set()
        )
        add(
            f"{operation.value}:outputs",
            operation,
            set(schema.output_field_names) <= summary_keys,
            "sanitized summaries expose declared outputs",
        )
        observed_codes = set(code for item in receipts for code in item.observed_issue_codes)
        add(
            f"{operation.value}:issues",
            operation,
            bool(observed_codes)
            and all(
                code
                in {
                    "context_mismatch",
                    "invalid_open_chromatin_row",
                    "open_chromatin_signal_disagreement",
                    "invalid_methylation_row",
                    "methylation_zero_coverage",
                    "methylation_fraction_disagreement",
                    "invalid_regulatory_role_row",
                    "regulatory_role_missing_channels",
                    "regulatory_role_ambiguity",
                    "invalid_enhancer_row",
                    "no_super_enhancer_candidate",
                    "super_enhancer_partial_activity",
                }
                for code in observed_codes
            ),
            "observed issues use the declared public vocabulary",
        )
        add(
            f"{operation.value}:claims",
            operation,
            all(
                not any(claim in str(item.summary).lower() for claim in schema.prohibited_claims)
                for item in receipts
            ),
            "summaries avoid prohibited biological claims",
        )
    body = {"fixture_id": fixture.fixture_id, "schemas": selected, "checks": checks}
    return AtlasAlphaEvidenceSchemaReport(
        fixture.fixture_id, selected, tuple(checks), content_hash(body)
    )


def atlas_alpha_evidence_schema_manifest(
    schemas: tuple[AtlasAlphaEvidenceSchema, ...] | None = None,
) -> dict[str, Any]:
    """Return a stable machine-readable schema manifest."""

    selected = schemas or default_atlas_alpha_evidence_schemas()
    body = {"schemas": selected}
    return {
        "schemas": [schema.to_dict() for schema in selected],
        "content_address": content_hash(body),
    }


__all__ = [
    "AtlasAlphaEvidenceFieldSpec",
    "AtlasAlphaEvidenceSchema",
    "AtlasAlphaEvidenceSchemaCheck",
    "AtlasAlphaEvidenceSchemaReport",
    "atlas_alpha_evidence_schema_manifest",
    "default_atlas_alpha_evidence_schemas",
    "validate_atlas_alpha_evidence_schema",
]
