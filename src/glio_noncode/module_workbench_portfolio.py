"""Select a deterministic, capacity-bounded task portfolio from workbench data."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchReport, ModuleWorkbenchRisk
from .module_workbench_portfolio_contracts import (
    MODULE_WORKBENCH_PORTFOLIO_VERSION,
    ModuleWorkbenchPortfolio,
    address_module_workbench_portfolio,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def build_module_workbench_portfolio(
    report: ModuleWorkbenchReport,
    *,
    capacity: int = 100,
    max_tasks_per_module: int = 2,
    minimum_priority: int = 0,
    maximum_priority: int = 100,
    risks: tuple[str, ...] = (),
) -> ModuleWorkbenchPortfolio:
    """Choose the highest-priority tasks subject to module and capacity limits."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("portfolio requires a typed workbench report")
    if capacity < 1 or max_tasks_per_module < 1:
        raise ValidationError("portfolio capacity values must be positive")
    if not 0 <= minimum_priority <= 100 or not 0 <= maximum_priority <= 100:
        raise ValidationError("portfolio priority bounds are invalid")
    if minimum_priority > maximum_priority:
        raise ValidationError("portfolio minimum priority exceeds maximum priority")
    allowed_risks = frozenset(risks)
    known_risks = frozenset(item.value for item in ModuleWorkbenchRisk)
    if not allowed_risks <= known_risks:
        raise ValidationError("portfolio contains an unknown risk")
    module_risks = {item.module_id: item.risk.value for item in report.assessments}
    candidates = [
        item
        for item in report.tasks
        if minimum_priority <= item.priority <= maximum_priority
        and (not allowed_risks or module_risks.get(item.module_id) in allowed_risks)
    ]
    candidates.sort(key=lambda item: (item.priority, -item.estimated_impact, item.task_id))
    selected: list[Any] = []
    counts: Counter[str] = Counter()
    for task in candidates:
        if len(selected) >= capacity or counts[task.module_id] >= max_tasks_per_module:
            continue
        selected.append(task)
        counts[task.module_id] += 1
    selected_tasks = tuple(sorted(selected, key=lambda item: item.task_id))
    selected_families: Counter[str] = Counter()
    module_family = {item.module_id: item.family for item in report.assessments}
    for task in selected_tasks:
        selected_families[module_family.get(task.module_id, "unknown")] += 1
    body = {
        "report_address": report.content_address,
        "capacity": capacity,
        "max_tasks_per_module": max_tasks_per_module,
        "selected_tasks": selected_tasks,
        "deferred_task_count": len(report.tasks) - len(selected_tasks),
        "selected_module_count": len(counts),
        "selected_family_counts": dict(sorted(selected_families.items())),
        "total_estimated_impact": round(
            sum(item.estimated_impact for item in selected_tasks) / len(selected_tasks), 6
        )
        if selected_tasks
        else 0.0,
        "accepted": report.accepted,
    }
    provisional = ModuleWorkbenchPortfolio(**body, content_address="pending")
    return ModuleWorkbenchPortfolio(
        **body,
        content_address=address_module_workbench_portfolio(provisional),
    )


def verify_module_workbench_portfolio(value: ModuleWorkbenchPortfolio) -> ModuleWorkbenchPortfolio:
    """Verify a selected portfolio address."""

    if not isinstance(value, ModuleWorkbenchPortfolio):
        raise ValidationError("portfolio verification requires a typed portfolio")
    if address_module_workbench_portfolio(value) != value.content_address:
        raise ValidationError("module workbench portfolio address mismatch")
    return value


def query_module_workbench_portfolio(
    value: ModuleWorkbenchPortfolio,
    *,
    module_id: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded selected-task page."""

    if not isinstance(value, ModuleWorkbenchPortfolio):
        raise ValidationError("portfolio query requires a typed portfolio")
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("portfolio paging is invalid")
    rows = [item.to_dict() for item in value.selected_tasks]
    if module_id:
        rows = [item for item in rows if item["module_id"] == module_id]
    if kind:
        rows = [item for item in rows if item["kind"] == kind]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "portfolio_address": value.content_address,
        "query": {"module_id": module_id, "kind": kind, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-portfolio-query")}


def module_workbench_portfolio_json(value: ModuleWorkbenchPortfolio) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_portfolio_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_PORTFOLIO_VERSION,
        "boundary": "public_aggregate_module_workbench_portfolio",
        "selection": [
            "capacity",
            "max_tasks_per_module",
            "minimum_priority",
            "maximum_priority",
            "risks",
        ],
        "resources": ["selected_tasks"],
        "ordering": "priority, impact descending, task ID; persisted tasks sorted by task ID",
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_portfolio_capabilities() -> dict[str, Any]:
    operations = (
        "filter_priority_window",
        "filter_risk_window",
        "cap_total_tasks",
        "cap_tasks_per_module",
        "rank_by_priority",
        "rank_by_estimated_impact",
        "roll_up_selected_families",
        "query_selected_tasks",
        "export_json",
        "verify_address",
    )
    return {
        "version": MODULE_WORKBENCH_PORTFOLIO_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_portfolio",
    "module_workbench_portfolio_capabilities",
    "module_workbench_portfolio_json",
    "module_workbench_portfolio_schema",
    "query_module_workbench_portfolio",
    "verify_module_workbench_portfolio",
]
