"""Bounded remediation planning and query projections for certification gaps."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    MODULE_CERTIFICATION_DEFAULT_LIMIT,
    MODULE_CERTIFICATION_MAX_LIMIT,
    MODULE_CERTIFICATION_MAX_TASKS,
    CertificationCheckKind,
    CertificationResource,
    CertificationTaskKind,
    ModuleCertificationMatrix,
    ModuleCertificationTask,
    ModuleCertificationTaskPlan,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _task_kind(kind: CertificationCheckKind) -> CertificationTaskKind:
    return {
        CertificationCheckKind.PARSE: CertificationTaskKind.REPAIR_PARSE,
        CertificationCheckKind.DEPENDENCY: CertificationTaskKind.REPAIR_DEPENDENCY,
        CertificationCheckKind.TEST: CertificationTaskKind.ADD_TEST_COVERAGE,
        CertificationCheckKind.DOCUMENTATION: CertificationTaskKind.ADD_DOCUMENTATION,
        CertificationCheckKind.EXPORT: CertificationTaskKind.REVIEW_EXPORT,
        CertificationCheckKind.BOUNDARY: CertificationTaskKind.REVIEW_BOUNDARY,
        CertificationCheckKind.SYMBOL: CertificationTaskKind.REVIEW_MODULE,
        CertificationCheckKind.SCALE: CertificationTaskKind.REVIEW_MODULE,
    }[kind]


def _reason(kind: CertificationCheckKind) -> str:
    return {
        CertificationCheckKind.PARSE: "repair the source parse contract before downstream review",
        CertificationCheckKind.DEPENDENCY: (
            "resolve or explicitly review unresolved local dependency edges"
        ),
        CertificationCheckKind.TEST: (
            "add deterministic test evidence for the public module surface"
        ),
        CertificationCheckKind.DOCUMENTATION: (
            "document the module contract and its supported boundary"
        ),
        CertificationCheckKind.EXPORT: "review package exposure for the public module surface",
        CertificationCheckKind.BOUNDARY: (
            "review the module identifier against the public boundary policy"
        ),
        CertificationCheckKind.SYMBOL: (
            "review whether the module has a deliberate public symbol surface"
        ),
        CertificationCheckKind.SCALE: (
            "review implementation scale and split oversized responsibilities"
        ),
    }[kind]


def build_module_certification_task_plan(
    matrix: ModuleCertificationMatrix,
    *,
    limit: int = MODULE_CERTIFICATION_MAX_TASKS,
) -> ModuleCertificationTaskPlan:
    """Turn every failed check into one stable, ordered remediation task."""

    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("certification task planning requires a typed matrix")
    if limit < 1 or limit > MODULE_CERTIFICATION_MAX_TASKS:
        raise ValidationError("certification task limit is invalid")
    tasks: list[ModuleCertificationTask] = []
    for gap in matrix.gaps[:limit]:
        kind = _task_kind(gap.kind)
        body = {
            "task_id": f"{kind.value}:{gap.module_id}",
            "module_id": gap.module_id,
            "kind": kind,
            "priority": gap.priority,
            "reason": _reason(gap.kind),
            "gap_ids": (gap.gap_id,),
            "evidence": gap.evidence,
        }
        tasks.append(
            ModuleCertificationTask(
                **body, content_address=_address(body, "module-certification-task")
            )
        )
    ordered = tuple(
        sorted(
            tasks, key=lambda item: (item.priority, item.kind.value, item.module_id, item.task_id)
        )
    )
    body = {
        "matrix_address": matrix.content_address,
        "tasks": ordered,
        "accepted": len(matrix.gaps) <= limit,
    }
    return ModuleCertificationTaskPlan(
        **body, content_address=_address(body, "module-certification-task-plan")
    )


def verify_module_certification_tasks(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
) -> ModuleCertificationTaskPlan:
    """Verify that every plan task is addressed and references a real gap."""

    if not isinstance(matrix, ModuleCertificationMatrix) or not isinstance(
        plan, ModuleCertificationTaskPlan
    ):
        raise ValidationError("certification task verification requires typed inputs")
    if plan.matrix_address != matrix.content_address:
        raise ValidationError("certification task plan references another matrix")
    gaps = {gap.gap_id: gap for gap in matrix.gaps}
    for task in plan.tasks:
        if not task.gap_ids or any(gap_id not in gaps for gap_id in task.gap_ids):
            raise ValidationError(f"certification task has an unknown gap: {task.task_id}")
        body = {key: value for key, value in task.to_dict().items() if key != "content_address"}
        if _address(body, "module-certification-task") != task.content_address:
            raise ValidationError(f"certification task address mismatch: {task.task_id}")
    body = {
        "matrix_address": plan.matrix_address,
        "tasks": plan.tasks,
        "accepted": plan.accepted,
    }
    if _address(body, "module-certification-task-plan") != plan.content_address:
        raise ValidationError("certification task plan address mismatch")
    return plan


def _query_rows(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
    resource: CertificationResource,
) -> list[Any]:
    if resource is CertificationResource.MODULES:
        return list(matrix.rows)
    if resource is CertificationResource.CHECKS:
        return [check for row in matrix.rows for check in row.checks]
    if resource is CertificationResource.GAPS:
        return list(matrix.gaps)
    if resource is CertificationResource.TASKS:
        return list(plan.tasks)
    raise ValidationError(
        "certification task query resource must be modules, checks, gaps, or tasks"
    )


def query_module_certification(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
    *,
    resource: str = "gaps",
    module_id: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    offset: int = 0,
    limit: int = MODULE_CERTIFICATION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a deterministic bounded page over certification resources."""

    if not isinstance(matrix, ModuleCertificationMatrix) or not isinstance(
        plan, ModuleCertificationTaskPlan
    ):
        raise ValidationError("certification query requires typed matrix and plan")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_MAX_LIMIT:
        raise ValidationError("certification query pagination is invalid")
    try:
        selected = CertificationResource(str(resource).casefold())
    except ValueError as exc:
        raise ValidationError(f"unsupported certification resource: {resource}") from exc
    rows = _query_rows(matrix, plan, selected)
    if module_id is not None:
        rows = [item for item in rows if getattr(item, "module_id", None) == module_id]
    if kind is not None:
        rows = [
            item for item in rows if getattr(getattr(item, "kind", None), "value", None) == kind
        ]
    if state is not None:
        rows = [
            item for item in rows if getattr(getattr(item, "state", None), "value", None) == state
        ]
    page = tuple(rows[offset : offset + limit])
    body = {
        "resource": selected,
        "query": {
            "module_id": module_id,
            "kind": kind,
            "state": state,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": page,
        "matrix_address": matrix.content_address,
        "plan_address": plan.content_address,
        "accepted": matrix.accepted and plan.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-query")}


def module_certification_tasks_json(plan: ModuleCertificationTaskPlan) -> str:
    return canonical_json(plan.to_dict()) + "\n"


def _csv(rows: list[Mapping[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: ";".join(str(item) for item in row[field])
                if isinstance(row.get(field), (tuple, list))
                else row.get(field, "")
                for field in fields
            }
        )
    return output.getvalue()


def module_certification_gaps_csv(matrix: ModuleCertificationMatrix) -> str:
    fields = (
        "gap_id",
        "module_id",
        "kind",
        "priority",
        "detail",
        "next_action",
        "evidence",
        "content_address",
    )
    return _csv([gap.to_dict() for gap in matrix.gaps], fields)


def module_certification_tasks_csv(plan: ModuleCertificationTaskPlan) -> str:
    fields = (
        "task_id",
        "module_id",
        "kind",
        "priority",
        "reason",
        "gap_ids",
        "evidence",
        "content_address",
    )
    return _csv([task.to_dict() for task in plan.tasks], fields)


def module_certification_tasks_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-tasks-v1",
        "boundary": "public_aggregate_module_certification_tasks",
        "task_fields": [
            "task_id",
            "module_id",
            "kind",
            "priority",
            "reason",
            "gap_ids",
            "evidence",
            "content_address",
        ],
        "resources": [
            item.value for item in CertificationResource if item.value not in {"events", "metrics"}
        ],
        "task_kinds": [item.value for item in CertificationTaskKind],
        "ordering": "priority, kind, module_id, task_id",
        "bounded": True,
    }


def module_certification_tasks_capabilities() -> dict[str, Any]:
    operations = (
        "derive_task_from_parse_gap",
        "derive_task_from_dependency_gap",
        "derive_task_from_test_gap",
        "derive_task_from_documentation_gap",
        "derive_task_from_export_gap",
        "derive_task_from_boundary_gap",
        "derive_task_from_symbol_gap",
        "derive_task_from_scale_gap",
        "verify_task_addresses",
        "query_modules",
        "query_checks",
        "query_gaps",
        "query_tasks",
        "export_gap_csv",
        "export_task_csv",
    )
    return {
        "version": "module-certification-tasks-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "maximum_tasks": MODULE_CERTIFICATION_MAX_TASKS,
    }


__all__ = [
    "build_module_certification_task_plan",
    "module_certification_gaps_csv",
    "module_certification_tasks_capabilities",
    "module_certification_tasks_csv",
    "module_certification_tasks_json",
    "module_certification_tasks_schema",
    "query_module_certification",
    "verify_module_certification_tasks",
]
