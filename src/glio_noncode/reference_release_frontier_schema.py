"""Field-level schemas and deterministic payload validation for C13-C16."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_release_frontier_contracts import (
    ReferenceReleaseContract,
    default_reference_release_contracts,
)
from .reference_release_frontier_public_data import ReferenceReleaseOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseField:
    """One typed field rule with a visibility and retention boundary."""

    name: str
    value_type: str
    required: bool
    nullable: bool
    description: str
    visibility: str
    max_items: int | None
    content_address: str

    def __post_init__(self) -> None:
        for name in ("name", "value_type", "description", "visibility", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.visibility not in {"public", "derived", "internal"}:
            raise ValidationError("field visibility must be public, derived, or internal")
        if self.max_items is not None and self.max_items < 1:
            raise ValidationError("field max_items must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseSchema:
    """Schema for one operation, including output projection limits."""

    operation: ReferenceReleaseOperation
    version: str
    input_fields: tuple[ReferenceReleaseField, ...]
    output_fields: tuple[ReferenceReleaseField, ...]
    forbidden_output_fields: tuple[str, ...]
    contract_address: str
    content_address: str

    def __post_init__(self) -> None:
        if not self.input_fields or not self.output_fields:
            raise ValidationError("schema requires input and output fields")
        input_names = [field.name for field in self.input_fields]
        output_names = [field.name for field in self.output_fields]
        if len(input_names) != len(set(input_names)) or len(output_names) != len(set(output_names)):
            raise ValidationError("schema field names must be unique")
        if set(self.forbidden_output_fields) & set(output_names):
            raise ValidationError("forbidden output field is declared as output")

    @property
    def input_map(self) -> dict[str, ReferenceReleaseField]:
        return {field.name: field for field in self.input_fields}

    @property
    def output_map(self) -> dict[str, ReferenceReleaseField]:
        return {field.name: field for field in self.output_fields}

    def validate_input(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        """Return stable field-level validation codes for an input mapping."""

        if not isinstance(payload, Mapping):
            return ("payload_not_object",)
        failures: list[str] = []
        for field in self.input_fields:
            if field.name not in payload and not field.required:
                continue
            value = payload.get(field.name)
            if field.required and field.name not in payload:
                failures.append(f"missing:{field.name}")
                continue
            if value is None and not field.nullable:
                failures.append(f"null:{field.name}")
                continue
            if value is not None and not _matches(value, field.value_type):
                failures.append(f"type:{field.name}")
                continue
            if (
                field.max_items is not None
                and isinstance(value, (list, tuple, set))
                and len(value) > field.max_items
            ):
                failures.append(f"max_items:{field.name}")
        return tuple(failures)

    def project_output(self, output: Mapping[str, Any]) -> dict[str, Any]:
        """Project only declared output fields and reject hidden fields."""

        if not isinstance(output, Mapping):
            raise ValidationError("schema output must be an object")
        hidden = set(output) & set(self.forbidden_output_fields)
        if hidden:
            raise ValidationError(f"forbidden output fields: {sorted(hidden)}")
        return {
            field.name: output[field.name] for field in self.output_fields if field.name in output
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _matches(value: Any, value_type: str) -> bool:
    if value_type == "text":
        return isinstance(value, str)
    if value_type == "mapping":
        return isinstance(value, Mapping)
    if value_type == "list":
        return isinstance(value, (list, tuple))
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "text_or_list":
        return isinstance(value, (str, list, tuple))
    return True


def _field(
    name: str,
    value_type: str,
    required: bool,
    nullable: bool,
    description: str,
    visibility: str = "public",
    max_items: int | None = None,
) -> ReferenceReleaseField:
    body = {
        "name": name,
        "value_type": value_type,
        "required": required,
        "nullable": nullable,
        "description": description,
        "visibility": visibility,
        "max_items": max_items,
    }
    return ReferenceReleaseField(**body, content_address=content_hash(body))


class ReferenceReleaseSchemaRegistry:
    """Operation-indexed schema registry with contract address linkage."""

    def __init__(self, schemas: Iterable[ReferenceReleaseSchema]) -> None:
        values = tuple(schemas)
        if len(values) != len(set(schema.operation for schema in values)):
            raise ValidationError("duplicate release schema operation")
        if not values:
            raise ValidationError("release schema registry cannot be empty")
        self._schemas = {schema.operation: schema for schema in values}

    @property
    def schemas(self) -> tuple[ReferenceReleaseSchema, ...]:
        return tuple(self._schemas.values())

    def by_operation(self, operation: ReferenceReleaseOperation | str) -> ReferenceReleaseSchema:
        try:
            key = (
                operation
                if isinstance(operation, ReferenceReleaseOperation)
                else ReferenceReleaseOperation(operation)
            )
            return self._schemas[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown release schema operation: {operation}") from exc

    def validate_all(
        self, payloads: Mapping[ReferenceReleaseOperation | str, Mapping[str, Any]]
    ) -> dict[str, tuple[str, ...]]:
        results: dict[str, tuple[str, ...]] = {}
        for operation, schema in self._schemas.items():
            payload = payloads.get(operation, payloads.get(operation.value, {}))
            results[operation.value] = schema.validate_input(payload)
        return results

    def manifest(self) -> dict[str, Any]:
        body = {"schemas": self.schemas}
        return {
            "schemas": [schema.to_dict() for schema in self.schemas],
            "content_address": content_hash(body),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.manifest()


def _schema(
    operation: ReferenceReleaseOperation,
    contract: ReferenceReleaseContract,
    inputs: tuple[ReferenceReleaseField, ...],
    outputs: tuple[ReferenceReleaseField, ...],
    forbidden: tuple[str, ...],
) -> ReferenceReleaseSchema:
    body = {
        "operation": operation,
        "version": "2026.08.d04-c13-c16.schema.v1",
        "input_fields": inputs,
        "output_fields": outputs,
        "forbidden_output_fields": forbidden,
        "contract_address": contract.content_address,
    }
    return ReferenceReleaseSchema(**body, content_address=content_hash(body))


def default_reference_release_schema() -> ReferenceReleaseSchemaRegistry:
    """Build the complete field schema for all four operations."""

    contracts = default_reference_release_contracts()
    common = (
        _field(
            "context_key",
            "text",
            True,
            False,
            "Exact assembly, disease, age, specimen, territory, and phase context.",
        ),
    )
    provenance = _schema(
        ReferenceReleaseOperation.PROVENANCE_CHECK,
        contracts.by_operation(ReferenceReleaseOperation.PROVENANCE_CHECK),
        common
        + (
            _field("records", "list", True, False, "Public source receipt rows.", max_items=64),
            _field(
                "require_checksum_match",
                "boolean",
                False,
                False,
                "Whether an observed checksum must match.",
                visibility="derived",
            ),
        ),
        (
            _field("state", "text", True, False, "Accepted or review state."),
            _field("check_count", "number", True, False, "Number of source receipt checks."),
            _field("compatible_ids", "list", True, False, "Source IDs that pass all checks."),
            _field("review_ids", "list", True, False, "Source IDs retained for review."),
            _field("checksum_matches", "list", True, False, "Per-source checksum results."),
            _field("issue_codes", "list", True, False, "Stable issue vocabulary."),
        ),
        ("records", "raw_records", "old_values", "new_values"),
    )
    drift = _schema(
        ReferenceReleaseOperation.ANNOTATION_DRIFT,
        contracts.by_operation(ReferenceReleaseOperation.ANNOTATION_DRIFT),
        common
        + (
            _field(
                "previous", "list", True, False, "Previous version annotation rows.", max_items=64
            ),
            _field(
                "current", "list", True, False, "Current version annotation rows.", max_items=64
            ),
            _field("identity_field", "text", False, False, "Stable annotation identity field."),
            _field("ignored_fields", "list", False, False, "Receipt fields excluded from drift."),
            _field("drift_threshold", "number", False, False, "Normalized drift threshold."),
        ),
        (
            _field("state", "text", True, False, "Accepted or drift state."),
            _field("finding_count", "number", True, False, "Number of comparison findings."),
            _field("drifted_ids", "list", True, False, "Annotation IDs classified as drift."),
            _field("stable_ids", "list", True, False, "Annotation IDs classified as stable."),
            _field(
                "changed_fields", "list", True, False, "Field names and scores, without raw rows."
            ),
            _field(
                "report_address", "text", True, False, "Content address of the comparison report."
            ),
        ),
        ("previous", "current", "old_values", "new_values"),
    )
    bundle = _schema(
        ReferenceReleaseOperation.REFERENCE_BUNDLE,
        contracts.by_operation(ReferenceReleaseOperation.REFERENCE_BUNDLE),
        common
        + (
            _field("records", "list", True, False, "Reference metadata rows.", max_items=64),
            _field("bundle_id", "text", True, False, "Stable bundle identity."),
            _field("schema_hash", "text", True, False, "Declared metadata schema address."),
            _field("require_available", "boolean", False, False, "Availability gate."),
        ),
        (
            _field("state", "text", True, False, "Published or blocked state."),
            _field("bundle_id", "text", True, False, "Stable bundle identity."),
            _field("reference_ids", "list", True, False, "Sorted reference IDs."),
            _field("record_count", "number", True, False, "Number of included metadata rows."),
            _field("schema_hash", "text", True, False, "Declared metadata schema address."),
            _field("bundle_address", "text", True, False, "Content address of the bundle."),
        ),
        ("records", "raw_records", "checksum_bytes"),
    )
    gate = _schema(
        ReferenceReleaseOperation.RELEASE_GATE,
        contracts.by_operation(ReferenceReleaseOperation.RELEASE_GATE),
        common
        + (
            _field("release_id", "text", True, False, "Release decision identity."),
            _field("bundle_address", "text", True, False, "Input bundle address."),
            _field("checks", "mapping", True, False, "Named Boolean integrity checks."),
            _field("required_checks", "list", False, False, "Required check names."),
        ),
        (
            _field("state", "text", True, False, "Published or blocked state."),
            _field("release_id", "text", True, False, "Release decision identity."),
            _field("bundle_address", "text", True, False, "Input bundle address."),
            _field("checks", "mapping", True, False, "Normalized check map."),
            _field("failed_checks", "list", True, False, "Failed required checks."),
            _field("issue_codes", "list", True, False, "Stable issue vocabulary."),
        ),
        ("checks_raw", "secret_material", "private_keys"),
    )
    return ReferenceReleaseSchemaRegistry((provenance, drift, bundle, gate))


__all__ = [
    "ReferenceReleaseField",
    "ReferenceReleaseSchema",
    "ReferenceReleaseSchemaRegistry",
    "default_reference_release_schema",
]
