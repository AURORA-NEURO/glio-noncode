"""Offline hydration, bounded queries, and structural impact comparisons."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    ImpactChangeKind,
    ImpactCheckPlane,
    ImpactGateState,
    ImpactPropagation,
    ImpactResource,
    ImpactSeverity,
    ImpactTaskKind,
    ModuleDependencyChange,
    ModuleImpactAssessment,
    ModuleImpactChange,
    ModuleImpactDiff,
    ModuleImpactGate,
    ModuleImpactGateCheck,
    ModuleImpactPolicy,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
    ModuleVerificationTask,
)
from .serialization import content_hash


def _enum(value: Any, kind: type) -> Any:
    try:
        return kind(str(value))
    except ValueError as exc:
        raise ValidationError(f"invalid module impact enum value: {value!r}") from exc


def _change(value: Mapping[str, Any]) -> Any:
    return ModuleImpactChange(
        module_id=str(value.get("module_id", "")),
        kind=_enum(value.get("kind", "unchanged"), ImpactChangeKind),
        left_address=value.get("left_address"),
        right_address=value.get("right_address"),
        physical_delta=int(value.get("physical_delta", 0)),
        nonblank_delta=int(value.get("nonblank_delta", 0)),
        public_symbol_delta=int(value.get("public_symbol_delta", 0)),
        import_delta=int(value.get("import_delta", 0)),
        test_reference_delta=int(value.get("test_reference_delta", 0)),
        added_symbols=tuple(str(item) for item in value.get("added_symbols", ())),
        removed_symbols=tuple(str(item) for item in value.get("removed_symbols", ())),
        changed_symbols=tuple(str(item) for item in value.get("changed_symbols", ())),
        added_dependencies=tuple(str(item) for item in value.get("added_dependencies", ())),
        removed_dependencies=tuple(str(item) for item in value.get("removed_dependencies", ())),
        severity=_enum(value.get("severity", "none"), ImpactSeverity),
        content_address=str(value.get("content_address", "")),
    )


def _dependency(value: Mapping[str, Any]) -> ModuleDependencyChange:
    return ModuleDependencyChange(
        source_module=str(value.get("source_module", "")),
        target_module=str(value.get("target_module", "")),
        import_name=str(value.get("import_name", "")),
        kind=_enum(value.get("kind", "changed"), ImpactChangeKind),
        relative=bool(value.get("relative", False)),
        left_resolved=value.get("left_resolved"),
        right_resolved=value.get("right_resolved"),
        content_address=str(value.get("content_address", "")),
    )


def impact_diff_from_mapping(value: Mapping[str, Any]) -> ModuleImpactDiff:
    """Hydrate a diff from verified offline JSON without reading source."""

    if not isinstance(value, Mapping):
        raise ValidationError("module impact diff must be an object")
    changes = tuple(_change(item) for item in value.get("changes", ()) if isinstance(item, Mapping))
    dependencies = tuple(
        _dependency(item) for item in value.get("dependencies", ()) if isinstance(item, Mapping)
    )
    return ModuleImpactDiff(
        left_inventory_address=str(value.get("left_inventory_address", "")),
        right_inventory_address=str(value.get("right_inventory_address", "")),
        changes=changes,
        dependencies=dependencies,
        changed_summary_fields=tuple(str(item) for item in value.get("changed_summary_fields", ())),
        summary_delta={
            str(key): int(item) for key, item in dict(value.get("summary_delta", {})).items()
        },
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )


def _assessment(value: Mapping[str, Any]) -> ModuleImpactAssessment:
    direct = value.get("direct_change_kind")
    return ModuleImpactAssessment(
        module_id=str(value.get("module_id", "")),
        propagation=_enum(value.get("propagation", "direct"), ImpactPropagation),
        distance=int(value.get("distance", 0)),
        severity=_enum(value.get("severity", "none"), ImpactSeverity),
        risk_score=float(value.get("risk_score", 0.0)),
        direct_change_kind=_enum(direct, ImpactChangeKind) if direct is not None else None,
        changed_sources=tuple(str(item) for item in value.get("changed_sources", ())),
        paths=tuple(str(item) for item in value.get("paths", ())),
        reasons=tuple(str(item) for item in value.get("reasons", ())),
        content_address=str(value.get("content_address", "")),
    )


def impact_report_from_mapping(value: Mapping[str, Any]) -> ModuleImpactReport:
    if not isinstance(value, Mapping):
        raise ValidationError("module impact report must be an object")
    assessments = tuple(
        _assessment(item) for item in value.get("assessments", ()) if isinstance(item, Mapping)
    )
    return ModuleImpactReport(
        diff_address=str(value.get("diff_address", "")),
        assessments=assessments,
        direct_count=int(value.get("direct_count", 0)),
        dependent_count=int(value.get("dependent_count", 0)),
        transitive_count=int(value.get("transitive_count", 0)),
        critical_count=int(value.get("critical_count", 0)),
        high_count=int(value.get("high_count", 0)),
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )


def _task(value: Mapping[str, Any]) -> ModuleVerificationTask:
    return ModuleVerificationTask(
        task_id=str(value.get("task_id", "")),
        module_id=str(value.get("module_id", "")),
        kind=_enum(value.get("kind", "review_direct_change"), ImpactTaskKind),
        priority=int(value.get("priority", 0)),
        reason=str(value.get("reason", "")),
        source_modules=tuple(str(item) for item in value.get("source_modules", ())),
        evidence=tuple(str(item) for item in value.get("evidence", ())),
        content_address=str(value.get("content_address", "")),
    )


def impact_plan_from_mapping(value: Mapping[str, Any]) -> ModuleImpactVerificationPlan:
    if not isinstance(value, Mapping):
        raise ValidationError("module impact plan must be an object")
    tasks = tuple(_task(item) for item in value.get("tasks", ()) if isinstance(item, Mapping))
    return ModuleImpactVerificationPlan(
        diff_address=str(value.get("diff_address", "")),
        impact_address=str(value.get("impact_address", "")),
        tasks=tasks,
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )


def _policy(value: Mapping[str, Any]) -> ModuleImpactPolicy:
    return ModuleImpactPolicy(
        policy_id=str(value.get("policy_id", "")),
        max_critical=int(value.get("max_critical", 0)),
        max_high=int(value.get("max_high", 0)),
        allow_removed_modules=bool(value.get("allow_removed_modules", False)),
        require_tests_for_direct_changes=bool(value.get("require_tests_for_direct_changes", False)),
        require_clean_inputs=bool(value.get("require_clean_inputs", True)),
        max_unresolved_direct=int(value.get("max_unresolved_direct", 0)),
        min_verification_task_count=int(value.get("min_verification_task_count", 0)),
        content_address=str(value.get("content_address", "")),
    )


def _gate_check(value: Mapping[str, Any]) -> ModuleImpactGateCheck:
    return ModuleImpactGateCheck(
        check_id=str(value.get("check_id", "")),
        plane=_enum(value.get("plane", "input"), ImpactCheckPlane),
        passed=bool(value.get("passed", False)),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "")),
    )


def impact_gate_from_mapping(value: Mapping[str, Any]) -> ModuleImpactGate:
    if not isinstance(value, Mapping):
        raise ValidationError("module impact gate must be an object")
    raw_policy = value.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise ValidationError("module impact gate policy is required")
    checks = tuple(
        _gate_check(item) for item in value.get("checks", ()) if isinstance(item, Mapping)
    )
    return ModuleImpactGate(
        diff_address=str(value.get("diff_address", "")),
        impact_address=str(value.get("impact_address", "")),
        plan_address=str(value.get("plan_address", "")),
        policy=_policy(raw_policy),
        checks=checks,
        state=_enum(value.get("state", "blocked"), ImpactGateState),
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )


def query_module_impact(
    *,
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    resource: str = "impacts",
    module_id: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    min_risk: float | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Query one typed closure resource with bounded pagination."""

    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("invalid module impact pagination")
    try:
        selected = ImpactResource(str(resource).casefold())
    except ValueError as exc:
        raise ValidationError(f"unsupported module impact resource: {resource}") from exc
    if selected is ImpactResource.CHANGES:
        rows: list[Any] = list(diff.changes)
        if module_id is not None:
            rows = [item for item in rows if item.module_id == module_id]
        if kind is not None:
            rows = [item for item in rows if item.kind.value == kind]
        if severity is not None:
            rows = [item for item in rows if item.severity.value == severity]
    elif selected is ImpactResource.DEPENDENCIES:
        rows = list(diff.dependencies)
        if module_id is not None:
            rows = [item for item in rows if item.source_module == module_id]
        if kind is not None:
            rows = [item for item in rows if item.kind.value == kind]
    elif selected is ImpactResource.IMPACTS:
        rows = list(report.assessments)
        if module_id is not None:
            rows = [item for item in rows if item.module_id == module_id]
        if severity is not None:
            rows = [item for item in rows if item.severity.value == severity]
        if min_risk is not None:
            rows = [item for item in rows if item.risk_score >= min_risk]
    elif selected is ImpactResource.TASKS:
        rows = list(plan.tasks)
        if module_id is not None:
            rows = [item for item in rows if item.module_id == module_id]
        if kind is not None:
            rows = [item for item in rows if item.kind.value == kind]
    else:
        raise ValidationError(
            "impact query resource must be changes, dependencies, impacts, or tasks"
        )
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in str(item.to_dict()).casefold()]
    page = tuple(rows[offset : offset + limit])
    body = {
        "version": "module-impact-query-v1",
        "resource": selected,
        "query": {
            "module_id": module_id,
            "kind": kind,
            "severity": severity,
            "min_risk": min_risk,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": page,
        "accepted": diff.accepted and report.accepted and plan.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-impact-query")}


def diff_module_impact_reports(
    left: ModuleImpactReport | Mapping[str, Any],
    right: ModuleImpactReport | Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two impact reports using module IDs and risk shifts."""

    old = left if isinstance(left, ModuleImpactReport) else impact_report_from_mapping(left)
    new = right if isinstance(right, ModuleImpactReport) else impact_report_from_mapping(right)
    left_rows = {item.module_id: item for item in old.assessments}
    right_rows = {item.module_id: item for item in new.assessments}
    common = set(left_rows) & set(right_rows)
    changed = tuple(
        sorted(
            module_id
            for module_id in common
            if left_rows[module_id].content_address != right_rows[module_id].content_address
        )
    )
    body = {
        "left_address": old.content_address,
        "right_address": new.content_address,
        "added_modules": tuple(sorted(set(right_rows) - set(left_rows))),
        "removed_modules": tuple(sorted(set(left_rows) - set(right_rows))),
        "changed_modules": changed,
        "left_critical_count": old.critical_count,
        "right_critical_count": new.critical_count,
        "left_high_count": old.high_count,
        "right_high_count": new.high_count,
        "accepted": old.accepted and new.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-impact-report-diff")}


__all__ = [
    "diff_module_impact_reports",
    "impact_diff_from_mapping",
    "impact_gate_from_mapping",
    "impact_plan_from_mapping",
    "impact_report_from_mapping",
    "query_module_impact",
]
