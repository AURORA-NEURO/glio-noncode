"""Independently audit module workbench identity, conservation, and coverage."""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench import verify_module_workbench
from .module_workbench_audit_contracts import (
    MODULE_WORKBENCH_AUDIT_DEFAULT_LIMIT,
    MODULE_WORKBENCH_AUDIT_MAX_LIMIT,
    ModuleWorkbenchAudit,
    ModuleWorkbenchAuditCheck,
    ModuleWorkbenchAuditPlane,
    address_module_workbench_audit_check,
)
from .module_workbench_contracts import (
    ModuleWorkbenchDepthBand,
    ModuleWorkbenchReport,
    ModuleWorkbenchRisk,
)
from .serialization import canonical_json, content_hash

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "patient",
        "subject",
    }
)


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _contains_forbidden(value: Any, path: str = "$") -> tuple[str, ...]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            name = str(key)
            if name.casefold() in _FORBIDDEN_KEYS:
                violations.append(f"{path}.{name}")
            violations.extend(_contains_forbidden(nested, f"{path}.{name}"))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            violations.extend(_contains_forbidden(nested, f"{path}[{index}]"))
    return tuple(violations)


def _check(
    check_id: str,
    plane: ModuleWorkbenchAuditPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchAuditCheck(**body, content_address="pending")
    return ModuleWorkbenchAuditCheck(
        **body,
        content_address=address_module_workbench_audit_check(provisional),
    )


def _checks(report: ModuleWorkbenchReport) -> tuple[ModuleWorkbenchAuditCheck, ...]:
    module_ids = tuple(item.module_id for item in report.assessments)
    task_ids = tuple(item.task_id for item in report.tasks)
    family_ids = tuple(item.family for item in report.families)
    depth_counts = Counter(item.depth_band.value for item in report.assessments)
    risk_counts = Counter(item.risk.value for item in report.assessments)
    assessed_families = Counter(item.family for item in report.assessments)
    rollup_families = {item.family: item.module_count for item in report.families}
    known_modules = set(module_ids)
    task_modules = {item.module_id for item in report.tasks}
    boundary_violations = _contains_forbidden(report.to_dict(include_rows=True))
    return tuple(
        sorted(
            (
                _check(
                    "address-presence",
                    ModuleWorkbenchAuditPlane.IDENTITY,
                    all(
                        bool(address)
                        for address in (
                            report.inventory_address,
                            report.matrix_address,
                            report.lineage_address,
                            report.quality_address,
                            report.content_address,
                        )
                    ),
                    "present",
                    "all aggregate addresses",
                    "the report is connected to its upstream content addresses",
                ),
                _check(
                    "assessment-addresses",
                    ModuleWorkbenchAuditPlane.IDENTITY,
                    all(
                        bool(item.content_address) and bool(item.source_address)
                        for item in report.assessments
                    ),
                    len(report.assessments),
                    len(report.assessments),
                    "every module assessment has stable source and assessment addresses",
                ),
                _check(
                    "boundary-keys",
                    ModuleWorkbenchAuditPlane.BOUNDARY,
                    not boundary_violations,
                    list(boundary_violations),
                    [],
                    "no public workbench payload key uses a reserved identity or attribution name",
                ),
                _check(
                    "depth-count-conservation",
                    ModuleWorkbenchAuditPlane.CONSERVATION,
                    sum(depth_counts.values()) == len(report.assessments)
                    and depth_counts[ModuleWorkbenchDepthBand.BLOCKED.value] == report.blocked_count
                    and depth_counts[ModuleWorkbenchDepthBand.COMPREHENSIVE.value]
                    == report.comprehensive_count
                    and depth_counts[ModuleWorkbenchDepthBand.STARTER.value]
                    == report.starter_count,
                    dict(sorted(depth_counts.items())),
                    {
                        "blocked": report.blocked_count,
                        "comprehensive": report.comprehensive_count,
                        "starter": report.starter_count,
                        "total": len(report.assessments),
                    },
                    "depth bands conserve every assessment and aggregate counters",
                ),
                _check(
                    "family-count-conservation",
                    ModuleWorkbenchAuditPlane.FAMILIES,
                    sum(rollup_families.values()) == len(report.assessments)
                    and all(
                        rollup_families.get(key) == value
                        for key, value in assessed_families.items()
                    ),
                    dict(sorted(rollup_families.items())),
                    dict(sorted(assessed_families.items())),
                    "family rollups conserve the module assessment set",
                ),
                _check(
                    "family-order",
                    ModuleWorkbenchAuditPlane.SORTING,
                    family_ids == tuple(sorted(family_ids))
                    and len(family_ids) == len(set(family_ids)),
                    list(family_ids),
                    "sorted unique family IDs",
                    "family rollups are deterministic and unique",
                ),
                _check(
                    "module-order",
                    ModuleWorkbenchAuditPlane.SORTING,
                    module_ids == tuple(sorted(module_ids))
                    and len(module_ids) == len(set(module_ids)),
                    len(module_ids),
                    len(set(module_ids)),
                    "module assessments are sorted and unique",
                ),
                _check(
                    "risk-count-conservation",
                    ModuleWorkbenchAuditPlane.CONSERVATION,
                    sum(risk_counts.values()) == len(report.assessments)
                    and {risk.value: risk_counts[risk.value] for risk in ModuleWorkbenchRisk}
                    == dict(report.risk_counts),
                    {risk.value: risk_counts[risk.value] for risk in ModuleWorkbenchRisk},
                    dict(sorted(report.risk_counts.items())),
                    "risk counts conserve every module assessment",
                ),
                _check(
                    "task-coverage",
                    ModuleWorkbenchAuditPlane.TASKS,
                    all(item.module_id in known_modules for item in report.tasks)
                    and task_modules <= known_modules
                    and len(task_ids) == len(set(task_ids)),
                    {
                        "task_count": len(report.tasks),
                        "task_module_count": len(task_modules),
                    },
                    {"module_count": len(report.assessments), "unique_task_ids": True},
                    "every task points to a known module and task IDs are unique",
                ),
                _check(
                    "task-order",
                    ModuleWorkbenchAuditPlane.SORTING,
                    task_ids == tuple(sorted(task_ids))
                    and all(0 <= item.priority <= 100 for item in report.tasks),
                    len(task_ids),
                    len(set(task_ids)),
                    "task IDs are sorted, unique, and priorities are bounded",
                ),
                _check(
                    "typed-report",
                    ModuleWorkbenchAuditPlane.IDENTITY,
                    isinstance(report, ModuleWorkbenchReport),
                    type(report).__name__,
                    "ModuleWorkbenchReport",
                    "the audit input is the typed public workbench contract",
                ),
                _check(
                    "nested-addresses",
                    ModuleWorkbenchAuditPlane.IDENTITY,
                    _nested_addresses_valid(report),
                    "valid" if _nested_addresses_valid(report) else "invalid",
                    "valid",
                    "dimension, assessment, task, family, and report addresses recompute",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )


def _nested_addresses_valid(report: ModuleWorkbenchReport) -> bool:
    try:
        verify_module_workbench(report)
    except ValidationError:
        return False
    return True


def audit_module_workbench(report: ModuleWorkbenchReport) -> ModuleWorkbenchAudit:
    """Build an independent, timestamp-free invariant report."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("workbench audit requires a typed report")
    checks = _checks(report)
    body = {
        "report_address": report.content_address,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchAudit(**body, content_address="pending")
    audit_body = provisional.to_dict()
    audit_body.pop("content_address", None)
    return ModuleWorkbenchAudit(
        **body,
        content_address=_address(audit_body, "module-workbench-audit"),
    )


def verify_module_workbench_audit(value: ModuleWorkbenchAudit) -> ModuleWorkbenchAudit:
    """Verify every audit check and the aggregate audit address."""

    if not isinstance(value, ModuleWorkbenchAudit):
        raise ValidationError("workbench audit verification requires a typed audit")
    for check in value.checks:
        if address_module_workbench_audit_check(check) != check.content_address:
            raise ValidationError(f"workbench audit check address mismatch: {check.check_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-audit") != value.content_address:
        raise ValidationError("module workbench audit address mismatch")
    return value


def query_module_workbench_audit(
    value: ModuleWorkbenchAudit,
    *,
    plane: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_AUDIT_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded audit check page."""

    if not isinstance(value, ModuleWorkbenchAudit):
        raise ValidationError("workbench audit query requires a typed audit")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_AUDIT_MAX_LIMIT:
        raise ValidationError("workbench audit paging is invalid")
    rows = [item.to_dict() for item in value.checks]
    if plane:
        rows = [item for item in rows if item["plane"] == plane]
    if passed is not None:
        rows = [item for item in rows if item["passed"] is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "audit_address": value.content_address,
        "query": {"plane": plane, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-audit-query")}


def module_workbench_audit_csv(value: ModuleWorkbenchAudit) -> str:
    fields = ("check_id", "plane", "passed", "observed", "required", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow(check.to_dict())
    return output.getvalue()


def module_workbench_audit_json(value: ModuleWorkbenchAudit) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_audit_schema() -> dict[str, Any]:
    return {
        "version": "module-workbench-audit-v1",
        "boundary": "public_aggregate_module_workbench_audit",
        "planes": [item.value for item in ModuleWorkbenchAuditPlane],
        "resources": ["checks"],
        "independent": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_audit_capabilities() -> dict[str, Any]:
    operations = (
        "audit_addresses",
        "audit_boundary_keys",
        "audit_depth_conservation",
        "audit_family_conservation",
        "audit_module_order",
        "audit_risk_conservation",
        "audit_task_coverage",
        "audit_task_order",
        "audit_nested_addresses",
        "query_checks",
        "export_json",
        "export_csv",
        "verify_audit",
    )
    return {
        "version": "module-workbench-audit-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
        "independent": True,
    }


__all__ = [
    "audit_module_workbench",
    "module_workbench_audit_capabilities",
    "module_workbench_audit_csv",
    "module_workbench_audit_json",
    "module_workbench_audit_schema",
    "query_module_workbench_audit",
    "verify_module_workbench_audit",
]
