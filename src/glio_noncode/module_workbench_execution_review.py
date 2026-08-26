"""Build deterministic module-level review routing from execution state."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_contracts import (
    ModuleWorkbenchExecutionItem,
    ModuleWorkbenchExecutionLedger,
    ModuleWorkbenchExecutionState,
)
from .module_workbench_execution_review_contracts import (
    MODULE_WORKBENCH_EXECUTION_REVIEW_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_REVIEW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_REVIEW_VERSION,
    ModuleWorkbenchExecutionReview,
    ModuleWorkbenchExecutionReviewItem,
    ModuleWorkbenchExecutionReviewState,
    address_module_workbench_execution_review,
    address_module_workbench_execution_review_item,
)
from .serialization import canonical_json, content_hash

_REVIEW_ORDER = {
    ModuleWorkbenchExecutionReviewState.ATTENTION: 0,
    ModuleWorkbenchExecutionReviewState.EVIDENCE_PENDING: 1,
    ModuleWorkbenchExecutionReviewState.READY: 2,
    ModuleWorkbenchExecutionReviewState.WAITING: 3,
    ModuleWorkbenchExecutionReviewState.VERIFY: 4,
    ModuleWorkbenchExecutionReviewState.COMPLETE: 5,
    ModuleWorkbenchExecutionReviewState.SUPERSEDED: 6,
}


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _state(item_rows: list[ModuleWorkbenchExecutionItem]) -> ModuleWorkbenchExecutionReviewState:
    if any(item.state is ModuleWorkbenchExecutionState.BLOCKED for item in item_rows):
        return ModuleWorkbenchExecutionReviewState.ATTENTION
    if any(item.state is ModuleWorkbenchExecutionState.IN_PROGRESS for item in item_rows):
        return ModuleWorkbenchExecutionReviewState.EVIDENCE_PENDING
    if any(item.state is ModuleWorkbenchExecutionState.READY for item in item_rows):
        return ModuleWorkbenchExecutionReviewState.READY
    if any(item.state is ModuleWorkbenchExecutionState.PLANNED for item in item_rows):
        return ModuleWorkbenchExecutionReviewState.WAITING
    if any(item.state is ModuleWorkbenchExecutionState.COMPLETED for item in item_rows):
        if all(
            item.state
            in {
                ModuleWorkbenchExecutionState.COMPLETED,
                ModuleWorkbenchExecutionState.SKIPPED,
            }
            for item in item_rows
        ):
            return ModuleWorkbenchExecutionReviewState.COMPLETE
        return ModuleWorkbenchExecutionReviewState.VERIFY
    if all(item.state is ModuleWorkbenchExecutionState.SKIPPED for item in item_rows):
        return ModuleWorkbenchExecutionReviewState.COMPLETE
    return ModuleWorkbenchExecutionReviewState.SUPERSEDED


def _next_tasks(
    item_rows: list[ModuleWorkbenchExecutionItem],
    state: ModuleWorkbenchExecutionReviewState,
) -> tuple[str, ...]:
    candidates = [
        item
        for item in item_rows
        if item.state
        in {
            ModuleWorkbenchExecutionState.BLOCKED,
            ModuleWorkbenchExecutionState.READY,
            ModuleWorkbenchExecutionState.IN_PROGRESS,
        }
    ]
    candidates.sort(
        key=lambda item: (
            0 if item.state is ModuleWorkbenchExecutionState.BLOCKED else 1,
            0 if item.state is ModuleWorkbenchExecutionState.IN_PROGRESS else 1,
            item.priority,
            item.task_id,
        )
    )
    if state is ModuleWorkbenchExecutionReviewState.WAITING:
        candidates = [
            item for item in item_rows if item.state is ModuleWorkbenchExecutionState.PLANNED
        ]
        candidates.sort(key=lambda item: (item.priority, item.task_id))
    return tuple(sorted(item.task_id for item in candidates[:32]))


def _detail(
    state: ModuleWorkbenchExecutionReviewState,
    item_rows: list[ModuleWorkbenchExecutionItem],
    next_task_ids: tuple[str, ...],
) -> str:
    if state is ModuleWorkbenchExecutionReviewState.ATTENTION:
        blocked = sum(item.state is ModuleWorkbenchExecutionState.BLOCKED for item in item_rows)
        return f"{blocked} task{'s' if blocked != 1 else ''} require blocker resolution"
    if state is ModuleWorkbenchExecutionReviewState.EVIDENCE_PENDING:
        active = sum(item.state is ModuleWorkbenchExecutionState.IN_PROGRESS for item in item_rows)
        return f"{active} active task{'s' if active != 1 else ''} await completion evidence"
    if state is ModuleWorkbenchExecutionReviewState.READY:
        return (
            f"{len(next_task_ids)} task{'s' if len(next_task_ids) != 1 else ''} are ready to start"
        )
    if state is ModuleWorkbenchExecutionReviewState.WAITING:
        return "selected tasks are waiting for prerequisite completion"
    if state is ModuleWorkbenchExecutionReviewState.VERIFY:
        return "completed tasks retain evidence for review verification"
    if state is ModuleWorkbenchExecutionReviewState.COMPLETE:
        return "all module tasks are terminal and no replacement is pending"
    return "all remaining module tasks were explicitly superseded"


def _review_item(
    module_id: str,
    item_rows: list[ModuleWorkbenchExecutionItem],
) -> ModuleWorkbenchExecutionReviewItem:
    state = _state(item_rows)
    next_task_ids = _next_tasks(item_rows, state)
    task_count = len(item_rows)
    total_required = sum(item.required_evidence_count for item in item_rows)
    evidence_present = sum(
        min(len(item.evidence_addresses), item.required_evidence_count) for item in item_rows
    )
    blockers = tuple(sorted({blocker for item in item_rows for blocker in item.blockers}))
    critical = sum(
        item.priority <= 20 or item.state is ModuleWorkbenchExecutionState.BLOCKED
        for item in item_rows
    )
    completion = round(sum(item.completion_percent for item in item_rows) / task_count, 6)
    evidence = round(evidence_present / total_required * 100.0, 6) if total_required else 100.0
    body = {
        "module_id": module_id,
        "family": item_rows[0].family,
        "task_count": task_count,
        "planned_count": sum(
            item.state is ModuleWorkbenchExecutionState.PLANNED for item in item_rows
        ),
        "ready_count": sum(item.state is ModuleWorkbenchExecutionState.READY for item in item_rows),
        "in_progress_count": sum(
            item.state is ModuleWorkbenchExecutionState.IN_PROGRESS for item in item_rows
        ),
        "blocked_count": sum(
            item.state is ModuleWorkbenchExecutionState.BLOCKED for item in item_rows
        ),
        "completed_count": sum(
            item.state is ModuleWorkbenchExecutionState.COMPLETED for item in item_rows
        ),
        "skipped_count": sum(
            item.state is ModuleWorkbenchExecutionState.SKIPPED for item in item_rows
        ),
        "superseded_count": sum(
            item.state is ModuleWorkbenchExecutionState.SUPERSEDED for item in item_rows
        ),
        "completion_percent": completion,
        "evidence_coverage_percent": evidence,
        "highest_priority": min(item.priority for item in item_rows),
        "critical_task_count": critical,
        "review_state": state,
        "next_task_ids": next_task_ids,
        "blocker_details": blockers,
        "detail": _detail(state, item_rows, next_task_ids),
    }
    return ModuleWorkbenchExecutionReviewItem(
        **body,
        content_address=address_module_workbench_execution_review_item(
            ModuleWorkbenchExecutionReviewItem(**body, content_address="pending")
        ),
    )


def build_module_workbench_execution_review(
    ledger: ModuleWorkbenchExecutionLedger,
) -> ModuleWorkbenchExecutionReview:
    """Build per-module progress, attention, and next-task routing."""

    if not isinstance(ledger, ModuleWorkbenchExecutionLedger):
        raise ValidationError("execution review requires a typed ledger")
    grouped: dict[str, list[ModuleWorkbenchExecutionItem]] = defaultdict(list)
    for item in ledger.items:
        grouped[item.module_id].append(item)
    items = tuple(
        sorted(
            (_review_item(module_id, rows) for module_id, rows in grouped.items()),
            key=lambda item: item.module_id,
        )
    )
    state_counts = Counter(item.review_state for item in items)
    body = {
        "ledger_address": ledger.content_address,
        "items": items,
        "module_count": len(items),
        "attention_count": state_counts[ModuleWorkbenchExecutionReviewState.ATTENTION],
        "evidence_pending_count": state_counts[
            ModuleWorkbenchExecutionReviewState.EVIDENCE_PENDING
        ],
        "ready_count": state_counts[ModuleWorkbenchExecutionReviewState.READY],
        "waiting_count": state_counts[ModuleWorkbenchExecutionReviewState.WAITING],
        "verify_count": state_counts[ModuleWorkbenchExecutionReviewState.VERIFY],
        "complete_count": state_counts[ModuleWorkbenchExecutionReviewState.COMPLETE],
        "superseded_count": state_counts[ModuleWorkbenchExecutionReviewState.SUPERSEDED],
        "next_task_count": sum(len(item.next_task_ids) for item in items),
        "accepted": ledger.accepted,
    }
    provisional = ModuleWorkbenchExecutionReview(**body, content_address="pending")
    return ModuleWorkbenchExecutionReview(
        **body,
        content_address=address_module_workbench_execution_review(provisional),
    )


def verify_module_workbench_execution_review(
    value: ModuleWorkbenchExecutionReview,
) -> ModuleWorkbenchExecutionReview:
    """Verify nested review rows and aggregate address."""

    if not isinstance(value, ModuleWorkbenchExecutionReview):
        raise ValidationError("execution review verification requires a typed review")
    for item in value.items:
        if address_module_workbench_execution_review_item(item) != item.content_address:
            raise ValidationError(f"execution review item address mismatch: {item.module_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-review") != value.content_address:
        raise ValidationError("execution review address mismatch")
    return value


def query_module_workbench_execution_review(
    value: ModuleWorkbenchExecutionReview,
    *,
    resource: str = "modules",
    module_id: str | None = None,
    family: str | None = None,
    review_state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_REVIEW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded module review or routed-task page."""

    if not isinstance(value, ModuleWorkbenchExecutionReview):
        raise ValidationError("execution review query requires a typed review")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_LIMIT:
        raise ValidationError("execution review paging is invalid")
    if resource == "modules":
        rows = [item.to_dict() for item in value.items]
    elif resource == "tasks":
        rows = [
            {
                "task_id": task_id,
                "module_id": item.module_id,
                "family": item.family,
                "review_state": item.review_state,
                "highest_priority": item.highest_priority,
                "content_address": item.content_address,
            }
            for item in value.items
            for task_id in item.next_task_ids
        ]
    elif resource == "summary":
        rows = [value.to_dict(include_items=False)]
    else:
        raise ValidationError("execution review resource must be modules, tasks, or summary")
    if module_id:
        rows = [item for item in rows if item.get("module_id") == module_id]
    if family:
        rows = [item for item in rows if item.get("family") == family]
    if review_state:
        rows = [item for item in rows if item.get("review_state") == review_state]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    rows.sort(key=lambda item: (str(item.get("module_id", "")), str(item.get("task_id", ""))))
    body = {
        "review_address": value.content_address,
        "query": {
            "resource": resource,
            "module_id": module_id,
            "family": family,
            "review_state": review_state,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-review-query")}


def module_workbench_execution_review_json(
    value: ModuleWorkbenchExecutionReview,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_review_csv(
    value: ModuleWorkbenchExecutionReview,
) -> str:
    output = io.StringIO(newline="")
    fields = (
        "module_id",
        "family",
        "review_state",
        "task_count",
        "planned_count",
        "ready_count",
        "in_progress_count",
        "blocked_count",
        "completed_count",
        "skipped_count",
        "superseded_count",
        "completion_percent",
        "evidence_coverage_percent",
        "highest_priority",
        "critical_task_count",
        "next_task_count",
        "blocker_count",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["next_task_count"] = len(item.next_task_ids)
        row["blocker_count"] = len(item.blocker_details)
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_review_markdown(
    value: ModuleWorkbenchExecutionReview,
) -> str:
    """Render a compact module-level review queue."""

    lines = [
        "# Module Workbench Execution Review",
        "",
        f"- Review: `{value.content_address}`",
        f"- Modules: {value.module_count}",
        f"- Routed next tasks: {value.next_task_count}",
        f"- Attention modules: {value.attention_count}",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Module | Family | State | Completion | Evidence | Next tasks | Detail |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    ordered = sorted(
        value.items,
        key=lambda item: (_REVIEW_ORDER[item.review_state], item.highest_priority, item.module_id),
    )
    for item in ordered:
        lines.append(
            f"| `{item.module_id}` | `{item.family}` | `{item.review_state.value}` | "
            f"{item.completion_percent:.2f}% | {item.evidence_coverage_percent:.2f}% | "
            f"{len(item.next_task_ids)} | {item.detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_review_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_REVIEW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_REVIEW_BOUNDARY,
        "review_states": [state.value for state in ModuleWorkbenchExecutionReviewState],
        "resources": ["modules", "tasks", "summary"],
        "ordering": (
            "attention, evidence pending, ready, waiting, verify, complete, superseded; "
            "then priority and module ID"
        ),
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_review_capabilities() -> dict[str, Any]:
    operations = (
        "roll_up_module_states",
        "measure_module_completion",
        "measure_module_evidence_coverage",
        "route_blocked_modules",
        "route_evidence_pending_modules",
        "route_ready_modules",
        "route_waiting_modules",
        "route_verification_modules",
        "derive_next_task_ids",
        "count_critical_tasks",
        "query_modules",
        "query_routed_tasks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_nested_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_REVIEW_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "bounded_routing": True,
        "identity_free": True,
    }


__all__ = [
    "build_module_workbench_execution_review",
    "module_workbench_execution_review_capabilities",
    "module_workbench_execution_review_csv",
    "module_workbench_execution_review_json",
    "module_workbench_execution_review_schema",
    "query_module_workbench_execution_review",
    "render_module_workbench_execution_review_markdown",
    "verify_module_workbench_execution_review",
]
