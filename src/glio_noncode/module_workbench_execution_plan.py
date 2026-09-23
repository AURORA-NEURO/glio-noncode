"""Build and query a dependency-aware execution plan for module work."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchReport, ModuleWorkbenchTask
from .module_workbench_execution_contracts import ModuleWorkbenchExecutionLedger
from .module_workbench_execution_plan_contracts import (
    MODULE_WORKBENCH_EXECUTION_PLAN_VERSION,
    ModuleWorkbenchExecutionPlan,
    ModuleWorkbenchExecutionPlanDependencyStatus,
    ModuleWorkbenchExecutionPlanNode,
    address_module_workbench_execution_plan,
    address_module_workbench_execution_plan_node,
)
from .module_workbench_portfolio_contracts import ModuleWorkbenchPortfolio
from .serialization import canonical_json, content_hash

_KIND_ORDER = {
    "repair_parse": 0,
    "resolve_dependency": 1,
    "add_test": 2,
    "add_documentation": 3,
    "expand_public_contract": 4,
    "decompose_oversized": 5,
    "review_integration": 6,
    "close_certification": 7,
}
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 512


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _ordered_module_tasks(tasks: tuple[ModuleWorkbenchTask, ...]) -> tuple[ModuleWorkbenchTask, ...]:
    return tuple(
        sorted(
            tasks,
            key=lambda item: (_KIND_ORDER.get(item.kind.value, 99), item.task_id),
        )
    )


def _full_dependency_map(
    report: ModuleWorkbenchReport,
) -> tuple[dict[str, tuple[str, ...]], dict[str, int]]:
    grouped: dict[str, list[ModuleWorkbenchTask]] = defaultdict(list)
    for task in report.tasks:
        grouped[task.module_id].append(task)
    dependencies: dict[str, tuple[str, ...]] = {}
    depths: dict[str, int] = {}
    for module_id, module_tasks in grouped.items():
        previous: str | None = None
        depth = 0
        for task in _ordered_module_tasks(tuple(module_tasks)):
            dependencies[task.task_id] = (previous,) if previous else ()
            depths[task.task_id] = depth
            previous = task.task_id
            depth += 1
    return dependencies, depths


def build_module_workbench_execution_plan(
    report: ModuleWorkbenchReport,
    portfolio: ModuleWorkbenchPortfolio,
    ledger: ModuleWorkbenchExecutionLedger,
) -> ModuleWorkbenchExecutionPlan:
    """Join full task dependencies to selected-wave and current-state evidence."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("execution plan requires a typed workbench report")
    if not isinstance(portfolio, ModuleWorkbenchPortfolio):
        raise ValidationError("execution plan requires a typed portfolio")
    if not isinstance(ledger, ModuleWorkbenchExecutionLedger):
        raise ValidationError("execution plan requires a typed execution ledger")
    if portfolio.report_address != report.content_address:
        raise ValidationError("execution plan portfolio does not belong to report")
    if ledger.report_address != report.content_address:
        raise ValidationError("execution plan ledger does not belong to report")
    if ledger.portfolio_address != portfolio.content_address:
        raise ValidationError("execution plan ledger does not belong to portfolio")
    selected_ids = {task.task_id for task in portfolio.selected_tasks}
    ledger_ids = {item.task_id for item in ledger.items}
    if selected_ids != ledger_ids:
        raise ValidationError("execution plan portfolio and ledger task sets differ")
    task_by_id = {task.task_id: task for task in report.tasks}
    dependencies, depths = _full_dependency_map(report)
    family_by_module = {item.module_id: item.family for item in report.assessments}
    state_by_task = {item.task_id: item.state.value for item in ledger.items}
    downstream = Counter(
        dependency
        for task_id in selected_ids
        for dependency in dependencies.get(task_id, ())
        if dependency in selected_ids
    )
    rows: list[ModuleWorkbenchExecutionPlanNode] = []
    ordered_ids = sorted(
        selected_ids,
        key=lambda task_id: (depths.get(task_id, 0), task_by_id[task_id].module_id, task_id),
    )
    for sequence, task_id in enumerate(ordered_ids, start=1):
        task = task_by_id.get(task_id)
        if task is None:
            raise ValidationError(f"execution plan contains unknown task: {task_id}")
        prerequisites = dependencies.get(task_id, ())
        selected_prerequisites = tuple(sorted(item for item in prerequisites if item in selected_ids))
        deferred_prerequisites = tuple(sorted(item for item in prerequisites if item not in selected_ids and item in task_by_id))
        unknown_prerequisites = tuple(sorted(item for item in prerequisites if item not in task_by_id))
        if unknown_prerequisites:
            status = ModuleWorkbenchExecutionPlanDependencyStatus.UNKNOWN_PREREQUISITE
        elif deferred_prerequisites:
            status = ModuleWorkbenchExecutionPlanDependencyStatus.DEFERRED_PREREQUISITE
        elif selected_prerequisites:
            status = ModuleWorkbenchExecutionPlanDependencyStatus.SELECTED_PREREQUISITE
        else:
            status = ModuleWorkbenchExecutionPlanDependencyStatus.ROOT
        all_deferred = tuple(sorted((*deferred_prerequisites, *unknown_prerequisites)))
        body = {
            "task_id": task.task_id,
            "module_id": task.module_id,
            "family": family_by_module.get(task.module_id, "unknown"),
            "kind": task.kind.value,
            "priority": task.priority,
            "sequence": sequence,
            "depth": depths.get(task.task_id, 0),
            "prerequisite_task_ids": tuple(sorted(prerequisites)),
            "selected_prerequisite_task_ids": selected_prerequisites,
            "deferred_prerequisite_task_ids": all_deferred,
            "execution_state": state_by_task.get(task.task_id, "untracked"),
            "dependency_status": status,
            "downstream_count": downstream.get(task.task_id, 0),
        }
        provisional = ModuleWorkbenchExecutionPlanNode(**body, content_address="pending")
        rows.append(
            ModuleWorkbenchExecutionPlanNode(
                **body,
                content_address=address_module_workbench_execution_plan_node(provisional),
            )
        )
    nodes = tuple(rows)
    paths: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        paths[node.module_id].append(node.task_id)
    critical_path = max(
        (tuple(task_ids) for task_ids in paths.values()),
        key=lambda path: (len(path), path),
        default=(),
    )
    dependency_edge_count = sum(len(node.prerequisite_task_ids) for node in nodes)
    root_count = sum(not node.prerequisite_task_ids for node in nodes)
    selected_prerequisite_count = sum(len(node.selected_prerequisite_task_ids) for node in nodes)
    deferred_prerequisite_count = sum(
        len(node.deferred_prerequisite_task_ids)
        for node in nodes
        if node.dependency_status is ModuleWorkbenchExecutionPlanDependencyStatus.DEFERRED_PREREQUISITE
    )
    unknown_prerequisite_count = sum(
        len(node.deferred_prerequisite_task_ids)
        for node in nodes
        if node.dependency_status is ModuleWorkbenchExecutionPlanDependencyStatus.UNKNOWN_PREREQUISITE
    )
    body = {
        "report_address": report.content_address,
        "portfolio_address": portfolio.content_address,
        "ledger_address": ledger.content_address,
        "nodes": nodes,
        "dependency_edge_count": dependency_edge_count,
        "root_count": root_count,
        "selected_prerequisite_count": selected_prerequisite_count,
        "deferred_prerequisite_count": deferred_prerequisite_count,
        "unknown_prerequisite_count": unknown_prerequisite_count,
        "max_depth": max((node.depth for node in nodes), default=0),
        "critical_path_task_ids": critical_path,
        "dependency_safe": not (deferred_prerequisite_count or unknown_prerequisite_count),
        "accepted": report.accepted and portfolio.accepted and ledger.accepted,
    }
    provisional = ModuleWorkbenchExecutionPlan(**body, content_address="pending")
    return ModuleWorkbenchExecutionPlan(
        **body,
        content_address=address_module_workbench_execution_plan(provisional),
    )


def verify_module_workbench_execution_plan(
    value: ModuleWorkbenchExecutionPlan,
) -> ModuleWorkbenchExecutionPlan:
    """Verify every node and the aggregate plan address."""

    if not isinstance(value, ModuleWorkbenchExecutionPlan):
        raise ValidationError("execution plan verification requires a typed plan")
    for node in value.nodes:
        if address_module_workbench_execution_plan_node(node) != node.content_address:
            raise ValidationError(f"execution plan node address mismatch: {node.task_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-plan") != value.content_address:
        raise ValidationError("execution plan address mismatch")
    return value


def _dependency_rows(value: ModuleWorkbenchExecutionPlan) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in value.nodes:
        for prerequisite in node.prerequisite_task_ids:
            selected = prerequisite in node.selected_prerequisite_task_ids
            rows.append(
                {
                    "task_id": node.task_id,
                    "module_id": node.module_id,
                    "prerequisite_task_id": prerequisite,
                    "selected": selected,
                    "dependency_status": "selected" if selected else node.dependency_status.value,
                    "node_address": node.content_address,
                }
            )
    return rows


def query_module_workbench_execution_plan(
    value: ModuleWorkbenchExecutionPlan,
    *,
    resource: str = "nodes",
    task_id: str | None = None,
    module_id: str | None = None,
    dependency_status: str | None = None,
    execution_state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded plan nodes, dependency edges, or summary resources."""

    if not isinstance(value, ModuleWorkbenchExecutionPlan):
        raise ValidationError("execution plan query requires a typed plan")
    if offset < 0 or limit < 1 or limit > _MAX_LIMIT:
        raise ValidationError("execution plan paging is invalid")
    if resource == "nodes":
        rows = [item.to_dict() for item in value.nodes]
    elif resource == "dependencies":
        rows = _dependency_rows(value)
    elif resource == "critical_path":
        rows = [
            {"position": index, "task_id": item, "plan_address": value.content_address}
            for index, item in enumerate(value.critical_path_task_ids, start=1)
        ]
    elif resource == "summary":
        rows = [value.to_dict(include_nodes=False)]
    else:
        raise ValidationError("execution plan resource must be nodes, dependencies, critical_path, or summary")
    if task_id:
        rows = [item for item in rows if item.get("task_id") == task_id]
    if module_id:
        rows = [item for item in rows if item.get("module_id") == module_id]
    if dependency_status:
        rows = [item for item in rows if item.get("dependency_status") == dependency_status]
    if execution_state:
        rows = [item for item in rows if item.get("execution_state") == execution_state]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "version": MODULE_WORKBENCH_EXECUTION_PLAN_VERSION,
        "plan_address": value.content_address,
        "query": {
            "resource": resource,
            "task_id": task_id,
            "module_id": module_id,
            "dependency_status": dependency_status,
            "execution_state": execution_state,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "plan_summary": value.to_dict(include_nodes=False),
        "dependency_safe": value.dependency_safe,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-plan-query")}


def module_workbench_execution_plan_csv(value: ModuleWorkbenchExecutionPlan) -> str:
    """Export the dependency-aware node projection as CSV."""

    output = io.StringIO(newline="")
    fields = (
        "sequence",
        "task_id",
        "module_id",
        "family",
        "kind",
        "priority",
        "depth",
        "execution_state",
        "dependency_status",
        "prerequisite_count",
        "selected_prerequisite_count",
        "deferred_prerequisite_count",
        "downstream_count",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for node in value.nodes:
        writer.writerow(
            {
                "sequence": node.sequence,
                "task_id": node.task_id,
                "module_id": node.module_id,
                "family": node.family,
                "kind": node.kind,
                "priority": node.priority,
                "depth": node.depth,
                "execution_state": node.execution_state,
                "dependency_status": node.dependency_status.value,
                "prerequisite_count": len(node.prerequisite_task_ids),
                "selected_prerequisite_count": len(node.selected_prerequisite_task_ids),
                "deferred_prerequisite_count": len(node.deferred_prerequisite_task_ids),
                "downstream_count": node.downstream_count,
                "content_address": node.content_address,
            }
        )
    return output.getvalue()


def render_module_workbench_execution_plan_markdown(
    value: ModuleWorkbenchExecutionPlan,
) -> str:
    """Render a compact, path-free plan review."""

    lines = [
        "# Module workbench execution plan",
        "",
        f"- Plan: `{value.content_address}`",
        f"- Selected nodes: `{len(value.nodes)}`",
        f"- Dependency safe: `{str(value.dependency_safe).lower()}`",
        f"- Edges: `{value.dependency_edge_count}`",
        f"- Deferred prerequisites: `{value.deferred_prerequisite_count}`",
        f"- Critical path: `{', '.join(value.critical_path_task_ids) or 'none'}`",
        "",
        "| Sequence | Task | Module | Depth | State | Dependency | Deferred |",
        "| ---: | --- | --- | ---: | --- | --- | ---: |",
    ]
    lines.extend(
        f"| {node.sequence} | `{node.task_id}` | `{node.module_id}` | {node.depth} | `{node.execution_state}` | `{node.dependency_status.value}` | {len(node.deferred_prerequisite_task_ids)} |"
        for node in value.nodes
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_plan_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PLAN_VERSION,
        "boundary": "public_aggregate_module_workbench_execution_plan",
        "resources": ["nodes", "dependencies", "critical_path", "summary"],
        "node_order": "topological depth, module ID, task ID",
        "dependency_policy": "immediate predecessor in full module task-kind order",
        "accepted_fields": ["accepted", "dependency_safe"],
        "preview": {
            "route": "/v1/module-workbench/execution/plan/preview",
            "query_route": "/v1/module-workbench/execution/plan/preview/query",
            "selection_fields": [
                "capacity",
                "max_tasks_per_module",
                "minimum_priority",
                "maximum_priority",
                "risk",
            ],
            "durable_ledger_mutation": False,
        },
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_plan_capabilities() -> dict[str, Any]:
    operations = (
        "derive_full_task_dependencies",
        "compare_selected_and_deferred_prerequisites",
        "calculate_topological_depth",
        "calculate_critical_path",
        "join_current_execution_state",
        "preview_alternate_capacity",
        "preview_alternate_module_limit",
        "preview_priority_window",
        "preview_risk_window",
        "query_nodes",
        "query_dependencies",
        "query_critical_path",
        "export_csv",
        "export_markdown",
        "verify_address",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PLAN_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_execution_plan",
    "module_workbench_execution_plan_capabilities",
    "module_workbench_execution_plan_csv",
    "module_workbench_execution_plan_schema",
    "query_module_workbench_execution_plan",
    "render_module_workbench_execution_plan_markdown",
    "verify_module_workbench_execution_plan",
]
