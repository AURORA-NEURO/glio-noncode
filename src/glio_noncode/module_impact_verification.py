"""Verification-plan generation for module impact assessments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    ImpactPropagation,
    ImpactResource,
    ImpactSeverity,
    ImpactTaskKind,
    ModuleImpactDiff,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
    ModuleVerificationTask,
)
from .serialization import content_hash, jsonable


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _priority(severity: ImpactSeverity, distance: int) -> int:
    base = {
        ImpactSeverity.CRITICAL: 0,
        ImpactSeverity.HIGH: 15,
        ImpactSeverity.MODERATE: 35,
        ImpactSeverity.LOW: 55,
        ImpactSeverity.NONE: 90,
    }[severity]
    return min(100, base + distance * 10)


def _task(
    module_id: str,
    kind: ImpactTaskKind,
    priority: int,
    reason: str,
    source_modules: tuple[str, ...],
    evidence: tuple[str, ...],
) -> ModuleVerificationTask:
    body = {
        "task_id": f"{kind.value}:{module_id}",
        "module_id": module_id,
        "kind": kind,
        "priority": priority,
        "reason": reason,
        "source_modules": tuple(sorted(set(source_modules))),
        "evidence": tuple(sorted(set(evidence))),
    }
    return ModuleVerificationTask(**body, content_address=_address(body, "module-impact-task"))


def build_module_impact_verification_plan(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
) -> ModuleImpactVerificationPlan:
    """Create stable review tasks from direct and propagated impact rows."""

    if not isinstance(diff, ModuleImpactDiff) or not isinstance(report, ModuleImpactReport):
        raise ValidationError("verification planning requires typed impact evidence")
    changes = {item.module_id: item for item in diff.changes}
    tasks: list[ModuleVerificationTask] = []
    for assessment in report.assessments:
        change = changes.get(assessment.module_id)
        if assessment.propagation is ImpactPropagation.DIRECT:
            if change is not None and change.kind.value == "removed":
                kind = ImpactTaskKind.REVIEW_REMOVED_MODULE
                reason = "review removed module references before release"
            elif change is not None and change.removed_symbols:
                kind = ImpactTaskKind.REVIEW_PUBLIC_SURFACE
                reason = "review symbol removals and downstream callers"
            else:
                kind = ImpactTaskKind.REVIEW_DIRECT_CHANGE
                reason = "review direct module change and its structural deltas"
        else:
            kind = ImpactTaskKind.REPLAY_DEPENDENT
            reason = "replay dependent module behavior after upstream change"
        tasks.append(
            _task(
                assessment.module_id,
                kind,
                _priority(assessment.severity, assessment.distance),
                reason,
                assessment.changed_sources,
                assessment.reasons,
            )
        )
    for dependency in diff.dependencies:
        if dependency.left_resolved is False or dependency.right_resolved is False:
            tasks.append(
                _task(
                    dependency.source_module,
                    ImpactTaskKind.REVIEW_UNRESOLVED_EDGE,
                    20,
                    "review unresolved dependency edge before accepting the change",
                    (dependency.source_module,),
                    (dependency.key, dependency.kind.value),
                )
            )
    tasks_tuple = tuple(
        sorted(
            {item.task_id: item for item in tasks}.values(),
            key=lambda item: (item.priority, item.kind.value, item.module_id, item.task_id),
        )
    )
    body = {
        "diff_address": diff.content_address,
        "impact_address": report.content_address,
        "tasks": tasks_tuple,
        "accepted": diff.accepted and report.accepted,
    }
    return ModuleImpactVerificationPlan(
        **body, content_address=_address(body, "module-impact-verification-plan")
    )


def query_module_impact_tasks(
    plan: ModuleImpactVerificationPlan,
    *,
    module_id: str | None = None,
    kind: str | None = None,
    min_priority: int | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded task page with stable task order."""

    if not isinstance(plan, ModuleImpactVerificationPlan):
        raise ValidationError("task query requires a typed verification plan")
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("invalid impact task pagination")
    if min_priority is not None and min_priority < 0:
        raise ValidationError("minimum task priority cannot be negative")
    items = list(plan.tasks)
    if module_id is not None:
        items = [item for item in items if item.module_id == module_id]
    if kind is not None:
        items = [item for item in items if item.kind.value == kind]
    if min_priority is not None:
        items = [item for item in items if item.priority >= min_priority]
    if text:
        needle = text.casefold()
        items = [
            item
            for item in items
            if needle in jsonable(item).get("module_id", "").casefold()
            or needle in jsonable(item).get("reason", "").casefold()
            or needle in " ".join(item.evidence).casefold()
        ]
    page = tuple(items[offset : offset + limit])
    body = {
        "resource": ImpactResource.TASKS,
        "query": {
            "module_id": module_id,
            "kind": kind,
            "min_priority": min_priority,
            "text": text,
            "offset": offset,
            "limit": limit,
        },
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(items),
        "items": page,
        "accepted": plan.accepted,
    }
    return body | {"content_address": _address(body, "module-impact-task-query")}


def module_impact_verification_schema() -> dict[str, Any]:
    return {
        "version": "module-impact-verification-v1",
        "boundary": "public_aggregate_module_impact_verification",
        "task_fields": [
            "task_id",
            "module_id",
            "kind",
            "priority",
            "reason",
            "source_modules",
            "evidence",
            "content_address",
        ],
        "task_kinds": [item.value for item in ImpactTaskKind],
        "stable_order": "priority, kind, module_id, task_id",
        "pagination": {"minimum": 1, "maximum": 512},
    }


def module_impact_verification_capabilities() -> dict[str, Any]:
    operations = (
        "plan_direct_change_review",
        "plan_public_surface_review",
        "plan_removed_module_review",
        "plan_dependent_replay",
        "plan_unresolved_edge_review",
        "query_tasks",
        "export_tasks",
    )
    return {
        "version": "module-impact-verification-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "bounded_pagination": True,
        "read_only": True,
        "handler_execution": False,
    }


__all__ = [
    "build_module_impact_verification_plan",
    "module_impact_verification_capabilities",
    "module_impact_verification_schema",
    "query_module_impact_tasks",
]
