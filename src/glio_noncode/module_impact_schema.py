"""Field-level schema declarations for module impact artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    MODULE_IMPACT_BOUNDARY,
    ModuleImpactDiff,
    ModuleImpactGate,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleImpactSchemaField:
    """One field in the public module-impact schema."""

    name: str
    value_type: str
    required: bool
    description: str
    content_address: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in ("name", "value_type", "description", "content_address")
        ):
            raise ValidationError("module impact schema field is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactSchemaReport:
    """Schema validation result that keeps every finding visible."""

    version: str
    checks: tuple[Mapping[str, Any], ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.content_address.strip():
            raise ValidationError("module impact schema report requires an address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "checks": [dict(item) for item in self.checks],
            "check_count": len(self.checks),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _fields() -> tuple[ModuleImpactSchemaField, ...]:
    declarations = (
        ("module_id", "string", True),
        ("kind", "enum", True),
        ("left_address", "string|null", False),
        ("right_address", "string|null", False),
        ("physical_delta", "integer", True),
        ("nonblank_delta", "integer", True),
        ("public_symbol_delta", "integer", True),
        ("import_delta", "integer", True),
        ("test_reference_delta", "integer", True),
        ("added_symbols", "array[string]", True),
        ("removed_symbols", "array[string]", True),
        ("changed_symbols", "array[string]", True),
        ("added_dependencies", "array[string]", True),
        ("removed_dependencies", "array[string]", True),
        ("severity", "enum", True),
        ("content_address", "string", True),
    )
    return tuple(
        ModuleImpactSchemaField(
            name=name,
            value_type=value_type,
            required=required,
            description=f"Canonical public module-impact field: {name}.",
            content_address=content_hash(
                {"name": name, "value_type": value_type, "required": required},
                prefix="module-impact-schema-field",
            ),
        )
        for name, value_type, required in declarations
    )


def default_module_impact_schema() -> dict[str, Any]:
    """Return the field-level schema for all impact projections."""

    fields = _fields()
    return {
        "version": "module-impact-schema-v1",
        "boundary": MODULE_IMPACT_BOUNDARY,
        "fields": [item.to_dict() for item in fields],
        "field_count": len(fields),
        "artifact_types": ["diff", "report", "verification", "gate", "runtime", "packet"],
        "diff_fields": [
            "left_inventory_address",
            "right_inventory_address",
            "changes",
            "dependencies",
            "changed_summary_fields",
            "summary_delta",
            "accepted",
            "content_address",
        ],
        "report_fields": [
            "diff_address",
            "assessments",
            "direct_count",
            "dependent_count",
            "transitive_count",
            "critical_count",
            "high_count",
            "accepted",
            "content_address",
        ],
        "verification_fields": [
            "diff_address",
            "impact_address",
            "tasks",
            "accepted",
            "content_address",
        ],
        "gate_fields": [
            "diff_address",
            "impact_address",
            "plan_address",
            "policy",
            "checks",
            "state",
            "accepted",
            "content_address",
        ],
    }


def _check(
    checks: list[Mapping[str, Any]],
    code: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "code": code,
            "passed": bool(passed),
            "observed": observed,
            "required": required,
            "detail": detail,
        }
    )


def validate_module_impact_schema(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    gate: ModuleImpactGate,
    schema: Mapping[str, Any] | None = None,
) -> ModuleImpactSchemaReport:
    """Validate closure shape and field coverage without source access."""

    if not all(
        isinstance(
            item,
            (ModuleImpactDiff, ModuleImpactReport, ModuleImpactVerificationPlan, ModuleImpactGate),
        )
        for item in (diff, report, plan, gate)
    ):
        raise ValidationError("impact schema validation requires typed closure objects")
    selected = schema or default_module_impact_schema()
    checks: list[Mapping[str, Any]] = []
    fields = selected.get("fields", ())
    names = {item.get("name") for item in fields if isinstance(item, Mapping)}
    required = {item.name for item in _fields() if item.required}
    _check(
        checks,
        "schema-version",
        selected.get("version") == "module-impact-schema-v1",
        selected.get("version"),
        "module-impact-schema-v1",
        "schema version is supported",
    )
    _check(
        checks,
        "boundary",
        selected.get("boundary") == MODULE_IMPACT_BOUNDARY,
        selected.get("boundary"),
        MODULE_IMPACT_BOUNDARY,
        "schema boundary is public impact boundary",
    )
    _check(
        checks,
        "field-coverage",
        required.issubset(names),
        len(required & names),
        len(required),
        "all required change fields are declared",
    )
    _check(
        checks,
        "diff-shape",
        bool(diff.left_inventory_address and diff.right_inventory_address and diff.content_address),
        True,
        True,
        "diff has immutable addresses",
    )
    _check(
        checks,
        "report-shape",
        report.diff_address == diff.content_address,
        report.diff_address,
        diff.content_address,
        "report references the diff",
    )
    _check(
        checks,
        "plan-shape",
        plan.diff_address == diff.content_address and plan.impact_address == report.content_address,
        True,
        True,
        "verification plan references its evidence",
    )
    _check(
        checks,
        "gate-shape",
        gate.diff_address == diff.content_address
        and gate.impact_address == report.content_address
        and gate.plan_address == plan.content_address,
        True,
        True,
        "gate references the complete closure",
    )
    accepted = all(bool(item.get("passed")) for item in checks)
    body = {"version": "module-impact-schema-v1", "checks": tuple(checks), "accepted": accepted}
    return ModuleImpactSchemaReport(
        **body, content_address=content_hash(body, prefix="module-impact-schema-report")
    )


def module_impact_schema_capabilities() -> dict[str, Any]:
    operations = (
        "declare_change_fields",
        "declare_diff_shape",
        "declare_report_shape",
        "declare_verification_shape",
        "declare_gate_shape",
        "validate_field_coverage",
        "validate_address_references",
    )
    return {
        "version": "module-impact-schema-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
    }


__all__ = [
    "ModuleImpactSchemaField",
    "ModuleImpactSchemaReport",
    "default_module_impact_schema",
    "module_impact_schema_capabilities",
    "validate_module_impact_schema",
]
