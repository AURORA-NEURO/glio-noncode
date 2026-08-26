"""Field-level schema validation for the module certification public contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_certification import module_certification_schema
from .module_certification_contracts import (
    MODULE_CERTIFICATION_VERSION,
    ModuleCertificationMatrix,
)
from .module_certification_packet import module_certification_packet_schema
from .module_certification_policy import module_certification_policy_schema
from .module_certification_tasks import module_certification_tasks_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleCertificationSchemaField:
    """One schema field with a stable type and requirement declaration."""

    path: str
    value_type: str
    required: bool
    description: str
    content_address: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in ("path", "value_type", "description", "content_address")
        ):
            raise ValidationError("certification schema field identifiers are required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationSchemaCheck:
    """One validation result for a declared certification schema field."""

    path: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not self.path.strip() or not self.detail.strip() or not self.content_address.strip():
            raise ValidationError("certification schema check identifiers are required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationSchemaReport:
    """Complete deterministic schema validation report."""

    version: str
    fields: tuple[ModuleCertificationSchemaField, ...]
    checks: tuple[ModuleCertificationSchemaCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.fields or not self.checks:
            raise ValidationError("certification schema report is incomplete")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("certification schema report acceptance does not conserve checks")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "field_count": len(self.fields),
            "check_count": len(self.checks),
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
            "fields": [item.to_dict() for item in self.fields],
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _field(
    path: str, value_type: str, required: bool, description: str
) -> ModuleCertificationSchemaField:
    body = {
        "path": path,
        "value_type": value_type,
        "required": required,
        "description": description,
    }
    return ModuleCertificationSchemaField(
        **body, content_address=content_hash(body, prefix="module-certification-schema-field")
    )


def default_module_certification_fields() -> tuple[ModuleCertificationSchemaField, ...]:
    """Return the field registry for every public certification object."""

    fields = (
        _field("matrix.inventory_address", "string", True, "address of the source inventory"),
        _field("matrix.rows", "array", True, "one conserved row per source module"),
        _field("matrix.gaps", "array", True, "actionable failed-check queue"),
        _field("matrix.check_kind_count", "integer", True, "checks represented per module"),
        _field("matrix.overall_score", "number", True, "aggregate score in the zero-to-one range"),
        _field(
            "matrix.overall_percent",
            "number",
            True,
            "aggregate percentage in the zero-to-one-hundred range",
        ),
        _field("matrix.accepted", "boolean", True, "upstream inventory acceptance"),
        _field("row.module_id", "string", True, "stable package-qualified module ID"),
        _field("row.checks", "array", True, "ordered check kinds"),
        _field("row.score", "number", True, "module score"),
        _field("row.state", "enum", True, "certified, review, blocked, or uncovered"),
        _field("check.kind", "enum", True, "static certification check kind"),
        _field("check.state", "enum", True, "passed, failed, or not_applicable"),
        _field("check.evidence", "array", True, "sorted static evidence tokens"),
        _field("gap.next_action", "string", True, "deterministic remediation direction"),
        _field("policy.minimum_score", "number", True, "minimum aggregate score"),
        _field("gate.checks", "array", True, "independent aggregate checks"),
        _field("task.gap_ids", "array", True, "known gap references"),
        _field("runtime.stages", "array", True, "ordered timestamp-free stages"),
        _field("packet.artifacts", "array", True, "fixed exact-byte artifact set"),
        _field("packet.manifest", "object", True, "offline manifest projection"),
    )
    return fields


def _check(
    path: str, passed: bool, observed: Any, required: Any, detail: str
) -> ModuleCertificationSchemaCheck:
    body = {
        "path": path,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleCertificationSchemaCheck(
        **body, content_address=content_hash(body, prefix="module-certification-schema-check")
    )


def validate_module_certification_schema(
    value: ModuleCertificationMatrix,
    schema: Mapping[str, Any] | None = None,
) -> ModuleCertificationSchemaReport:
    """Validate a typed matrix against field, range, count, and enum contracts."""

    if not isinstance(value, ModuleCertificationMatrix):
        raise ValidationError("certification schema validation requires a typed matrix")
    selected = schema or module_certification_schema()
    fields = default_module_certification_fields()
    field_names = {item.path for item in fields}
    checks = (
        _check(
            "version",
            selected.get("version") == MODULE_CERTIFICATION_VERSION,
            selected.get("version"),
            MODULE_CERTIFICATION_VERSION,
            "schema version matches",
        ),
        _check(
            "boundary",
            selected.get("boundary") == "public_aggregate_module_certification",
            selected.get("boundary"),
            "public_aggregate_module_certification",
            "schema boundary matches",
        ),
        _check(
            "field-registry",
            bool(field_names) and len(field_names) == len(fields),
            len(field_names),
            len(fields),
            "field registry is unique",
        ),
        _check(
            "module-count",
            value.module_count == len(value.rows),
            value.module_count,
            len(value.rows),
            "module rows conserve aggregate count",
        ),
        _check(
            "check-kind-count",
            value.check_kind_count == len(value.rows[0].checks)
            if value.rows
            else value.check_kind_count > 0,
            value.check_kind_count,
            len(value.rows[0].checks) if value.rows else ">0",
            "check kind count matches rows",
        ),
        _check(
            "score-range",
            0.0 <= value.overall_score <= 1.0 and 0.0 <= value.overall_percent <= 100.0,
            (value.overall_score, value.overall_percent),
            "0..1 and 0..100",
            "aggregate scores are bounded",
        ),
        _check(
            "row-order",
            tuple(row.module_id for row in value.rows)
            == tuple(sorted(row.module_id for row in value.rows)),
            len(value.rows),
            len(value.rows),
            "module rows are sorted",
        ),
        _check(
            "gap-conservation",
            value.gap_count == sum(row.gap_count for row in value.rows),
            value.gap_count,
            sum(row.gap_count for row in value.rows),
            "gap counts conserve rows",
        ),
        _check(
            "public-fields",
            all(item.required for item in fields),
            sum(item.required for item in fields),
            len(fields),
            "required field declarations are explicit",
        ),
        _check(
            "packet-schema",
            module_certification_packet_schema()["artifact_count"] == 10,
            module_certification_packet_schema()["artifact_count"],
            10,
            "packet artifact count is fixed",
        ),
        _check(
            "policy-schema",
            "minimum_score" in module_certification_policy_schema()["policy_fields"],
            True,
            True,
            "policy threshold is declared",
        ),
        _check(
            "tasks-schema",
            "gap_ids" in module_certification_tasks_schema()["task_fields"],
            True,
            True,
            "task gap linkage is declared",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "version": MODULE_CERTIFICATION_VERSION,
        "fields": fields,
        "checks": checks,
        "accepted": accepted,
    }
    return ModuleCertificationSchemaReport(
        **body, content_address=content_hash(body, prefix="module-certification-schema-report")
    )


def module_certification_schema_capabilities() -> dict[str, Any]:
    operations = (
        "list_matrix_fields",
        "list_row_fields",
        "list_check_fields",
        "list_gap_fields",
        "list_policy_fields",
        "list_task_fields",
        "list_runtime_fields",
        "list_packet_fields",
        "validate_versions",
        "validate_boundaries",
        "validate_ranges",
        "validate_conservation",
        "validate_ordering",
    )
    return {
        "version": "module-certification-schema-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
    }


def module_certification_schema_report_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-schema-report-v1",
        "boundary": "public_aggregate_module_certification_schema_report",
        "field_fields": ["path", "value_type", "required", "description", "content_address"],
        "check_fields": ["path", "passed", "observed", "required", "detail", "content_address"],
        "report_fields": ["version", "fields", "checks", "accepted", "content_address"],
        "accepted_rule": "all schema checks pass",
    }


__all__ = [
    "ModuleCertificationSchemaCheck",
    "ModuleCertificationSchemaField",
    "ModuleCertificationSchemaReport",
    "default_module_certification_fields",
    "module_certification_schema_capabilities",
    "module_certification_schema_report_schema",
    "validate_module_certification_schema",
]
