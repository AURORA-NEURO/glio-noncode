"""Deterministic change analysis for module execution ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_contracts import ModuleWorkbenchExecutionLedger
from .module_workbench_execution_diff_contracts import (
    MODULE_WORKBENCH_EXECUTION_DIFF_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_DIFF_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_DIFF_VERSION,
    ModuleWorkbenchExecutionChange,
    ModuleWorkbenchExecutionChangeKind,
    ModuleWorkbenchExecutionDiff,
    address_module_workbench_execution_change,
    address_module_workbench_execution_diff,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _change(
    task_id: str,
    kind: ModuleWorkbenchExecutionChangeKind,
    previous: Any | None,
    current: Any | None,
) -> ModuleWorkbenchExecutionChange:
    previous_state = None if previous is None else previous.state.value
    current_state = None if current is None else current.state.value
    completion_delta = round(
        (0.0 if current is None else current.completion_percent)
        - (0.0 if previous is None else previous.completion_percent),
        6,
    )
    evidence_delta = (0 if current is None else len(current.evidence_addresses)) - (
        0 if previous is None else len(previous.evidence_addresses)
    )
    event_delta = (0 if current is None else current.event_count) - (
        0 if previous is None else previous.event_count
    )
    detail = (
        "task added to the execution portfolio"
        if kind is ModuleWorkbenchExecutionChangeKind.ADDED
        else "task removed from the execution portfolio"
        if kind is ModuleWorkbenchExecutionChangeKind.REMOVED
        else f"state {previous_state or 'none'} -> {current_state or 'none'}"
        if kind is ModuleWorkbenchExecutionChangeKind.CHANGED
        else "task state and evidence are unchanged"
    )
    body = {
        "task_id": task_id,
        "kind": kind,
        "previous_state": previous_state,
        "current_state": current_state,
        "completion_delta": completion_delta,
        "evidence_delta": evidence_delta,
        "event_delta": event_delta,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionChange(**body, content_address="pending")
    return ModuleWorkbenchExecutionChange(
        **body,
        content_address=address_module_workbench_execution_change(provisional),
    )


def build_module_workbench_execution_diff(
    previous: ModuleWorkbenchExecutionLedger,
    current: ModuleWorkbenchExecutionLedger,
) -> ModuleWorkbenchExecutionDiff:
    """Compare item states, evidence, event counts, and aggregate progress."""

    if not isinstance(previous, ModuleWorkbenchExecutionLedger) or not isinstance(
        current, ModuleWorkbenchExecutionLedger
    ):
        raise ValidationError("execution diff requires two typed ledgers")
    previous_by_id = {item.task_id: item for item in previous.items}
    current_by_id = {item.task_id: item for item in current.items}
    changes: list[ModuleWorkbenchExecutionChange] = []
    for task_id in sorted(set(previous_by_id) | set(current_by_id)):
        before = previous_by_id.get(task_id)
        after = current_by_id.get(task_id)
        if before is None:
            kind = ModuleWorkbenchExecutionChangeKind.ADDED
        elif after is None:
            kind = ModuleWorkbenchExecutionChangeKind.REMOVED
        elif before.to_dict() == after.to_dict():
            kind = ModuleWorkbenchExecutionChangeKind.UNCHANGED
        else:
            kind = ModuleWorkbenchExecutionChangeKind.CHANGED
        changes.append(_change(task_id, kind, before, after))
    rows = tuple(changes)
    body = {
        "previous_address": previous.content_address,
        "current_address": current.content_address,
        "changes": rows,
        "added_count": sum(item.kind is ModuleWorkbenchExecutionChangeKind.ADDED for item in rows),
        "changed_count": sum(
            item.kind is ModuleWorkbenchExecutionChangeKind.CHANGED for item in rows
        ),
        "removed_count": sum(
            item.kind is ModuleWorkbenchExecutionChangeKind.REMOVED for item in rows
        ),
        "unchanged_count": sum(
            item.kind is ModuleWorkbenchExecutionChangeKind.UNCHANGED for item in rows
        ),
        "completion_delta": round(current.completion_percent - previous.completion_percent, 6),
        "evidence_delta": sum(len(item.evidence_addresses) for item in current.items)
        - sum(len(item.evidence_addresses) for item in previous.items),
        "event_delta": len(current.events) - len(previous.events),
        "task_delta": current.total_task_count - previous.total_task_count,
        "accepted": previous.accepted and current.accepted,
    }
    provisional = ModuleWorkbenchExecutionDiff(**body, content_address="pending")
    return ModuleWorkbenchExecutionDiff(
        **body,
        content_address=address_module_workbench_execution_diff(provisional),
    )


def verify_module_workbench_execution_diff(
    value: ModuleWorkbenchExecutionDiff,
) -> ModuleWorkbenchExecutionDiff:
    """Verify nested change and aggregate diff addresses."""

    if not isinstance(value, ModuleWorkbenchExecutionDiff):
        raise ValidationError("execution diff verification requires a typed diff")
    for change in value.changes:
        if address_module_workbench_execution_change(change) != change.content_address:
            raise ValidationError(f"execution change address mismatch: {change.task_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-diff") != value.content_address:
        raise ValidationError("execution diff address mismatch")
    return value


def query_module_workbench_execution_diff(
    value: ModuleWorkbenchExecutionDiff,
    *,
    kind: str | None = None,
    task_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded execution change page."""

    if not isinstance(value, ModuleWorkbenchExecutionDiff):
        raise ValidationError("execution diff query requires a typed diff")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_DIFF_MAX_LIMIT:
        raise ValidationError("execution diff paging is invalid")
    rows = [item.to_dict() for item in value.changes]
    if kind:
        rows = [item for item in rows if item.get("kind") == kind]
    if task_id:
        rows = [item for item in rows if item.get("task_id") == task_id]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "diff_address": value.content_address,
        "query": {"kind": kind, "task_id": task_id, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-diff-query")}


def module_workbench_execution_diff_json(value: ModuleWorkbenchExecutionDiff) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_diff_csv(value: ModuleWorkbenchExecutionDiff) -> str:
    output = io.StringIO(newline="")
    fields = (
        "task_id",
        "kind",
        "previous_state",
        "current_state",
        "completion_delta",
        "evidence_delta",
        "event_delta",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for change in value.changes:
        writer.writerow(change.to_dict())
    return output.getvalue()


def module_workbench_execution_diff_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_DIFF_BOUNDARY,
        "change_kinds": [kind.value for kind in ModuleWorkbenchExecutionChangeKind],
        "resources": ["changes", "summary"],
        "signed_deltas": ["completion_delta", "evidence_delta", "event_delta", "task_delta"],
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_diff_capabilities() -> dict[str, Any]:
    operations = (
        "compare_task_identity",
        "classify_added_tasks",
        "classify_changed_tasks",
        "classify_removed_tasks",
        "classify_unchanged_tasks",
        "measure_completion_delta",
        "measure_evidence_delta",
        "measure_event_delta",
        "query_changes",
        "export_json",
        "export_csv",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_DIFF_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "signed_deltas": True,
    }


__all__ = [
    "build_module_workbench_execution_diff",
    "module_workbench_execution_diff_capabilities",
    "module_workbench_execution_diff_csv",
    "module_workbench_execution_diff_json",
    "module_workbench_execution_diff_schema",
    "query_module_workbench_execution_diff",
    "verify_module_workbench_execution_diff",
]
