"""Compare module workbench snapshots without timestamps or source payloads."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchReport
from .module_workbench_diff_contracts import (
    MODULE_WORKBENCH_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_DIFF_MAX_LIMIT,
    ModuleWorkbenchChange,
    ModuleWorkbenchChangeKind,
    ModuleWorkbenchDiff,
    address_module_workbench_change,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _module_change(
    previous: Any | None,
    current: Any | None,
    previous_tasks: int,
    current_tasks: int,
) -> ModuleWorkbenchChange:
    if previous is None:
        kind = ModuleWorkbenchChangeKind.ADDED
        module_id = current.module_id
        detail = "module is present only in the current workbench"
    elif current is None:
        kind = ModuleWorkbenchChangeKind.REMOVED
        module_id = previous.module_id
        detail = "module is present only in the previous workbench"
    elif previous.to_dict() == current.to_dict():
        kind = ModuleWorkbenchChangeKind.UNCHANGED
        module_id = current.module_id
        detail = "assessment content is unchanged"
    else:
        kind = ModuleWorkbenchChangeKind.CHANGED
        module_id = current.module_id
        detail = "assessment score, classification, metrics, or evidence changed"
    body = {
        "module_id": module_id,
        "kind": kind,
        "previous_score": previous.score if previous is not None else None,
        "current_score": current.score if current is not None else None,
        "previous_depth_band": previous.depth_band if previous is not None else None,
        "current_depth_band": current.depth_band if current is not None else None,
        "previous_risk": previous.risk if previous is not None else None,
        "current_risk": current.risk if current is not None else None,
        "task_delta": abs(current_tasks - previous_tasks),
        "detail": detail,
    }
    provisional = ModuleWorkbenchChange(**body, content_address="pending")
    return ModuleWorkbenchChange(
        **body,
        content_address=address_module_workbench_change(provisional),
    )


def build_module_workbench_diff(
    previous: ModuleWorkbenchReport,
    current: ModuleWorkbenchReport,
) -> ModuleWorkbenchDiff:
    """Build a stable module-by-module snapshot diff."""

    if not isinstance(previous, ModuleWorkbenchReport) or not isinstance(
        current, ModuleWorkbenchReport
    ):
        raise ValidationError("workbench diff requires two typed reports")
    previous_rows = {item.module_id: item for item in previous.assessments}
    current_rows = {item.module_id: item for item in current.assessments}
    previous_tasks = {}
    current_tasks = {}
    for task in previous.tasks:
        previous_tasks[task.module_id] = previous_tasks.get(task.module_id, 0) + 1
    for task in current.tasks:
        current_tasks[task.module_id] = current_tasks.get(task.module_id, 0) + 1
    changes = tuple(
        sorted(
            (
                _module_change(
                    previous_rows.get(module_id),
                    current_rows.get(module_id),
                    previous_tasks.get(module_id, 0),
                    current_tasks.get(module_id, 0),
                )
                for module_id in sorted(set(previous_rows) | set(current_rows))
            ),
            key=lambda item: item.module_id,
        )
    )
    body = {
        "previous_address": previous.content_address,
        "current_address": current.content_address,
        "changes": changes,
        "added_count": sum(item.kind is ModuleWorkbenchChangeKind.ADDED for item in changes),
        "changed_count": sum(item.kind is ModuleWorkbenchChangeKind.CHANGED for item in changes),
        "removed_count": sum(item.kind is ModuleWorkbenchChangeKind.REMOVED for item in changes),
        "unchanged_count": sum(
            item.kind is ModuleWorkbenchChangeKind.UNCHANGED for item in changes
        ),
        "score_delta": round(current.overall_score - previous.overall_score, 6),
        "task_delta": len(current.tasks) - len(previous.tasks),
        "accepted": previous.accepted and current.accepted,
    }
    provisional = ModuleWorkbenchDiff(**body, content_address="pending")
    diff_body = provisional.to_dict()
    diff_body.pop("content_address", None)
    return ModuleWorkbenchDiff(
        **body,
        content_address=_address(diff_body, "module-workbench-diff"),
    )


def verify_module_workbench_diff(value: ModuleWorkbenchDiff) -> ModuleWorkbenchDiff:
    """Verify change addresses and aggregate diff conservation."""

    if not isinstance(value, ModuleWorkbenchDiff):
        raise ValidationError("workbench diff verification requires a typed diff")
    for change in value.changes:
        if address_module_workbench_change(change) != change.content_address:
            raise ValidationError(f"workbench change address mismatch: {change.module_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-diff") != value.content_address:
        raise ValidationError("module workbench diff address mismatch")
    return value


def query_module_workbench_diff(
    value: ModuleWorkbenchDiff,
    *,
    kind: str | None = None,
    module_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded comparison page."""

    if not isinstance(value, ModuleWorkbenchDiff):
        raise ValidationError("workbench diff query requires a typed diff")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_DIFF_MAX_LIMIT:
        raise ValidationError("workbench diff paging is invalid")
    rows = [item.to_dict() for item in value.changes]
    if kind:
        rows = [item for item in rows if item["kind"] == kind]
    if module_id:
        rows = [item for item in rows if item["module_id"] == module_id]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "diff_address": value.content_address,
        "query": {"kind": kind, "module_id": module_id, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-diff-query")}


def module_workbench_diff_csv(value: ModuleWorkbenchDiff) -> str:
    fields = (
        "module_id",
        "kind",
        "previous_score",
        "current_score",
        "previous_depth_band",
        "current_depth_band",
        "previous_risk",
        "current_risk",
        "task_delta",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.changes:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_workbench_diff_json(value: ModuleWorkbenchDiff) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_diff_schema() -> dict[str, Any]:
    return {
        "version": "module-workbench-diff-v1",
        "boundary": "public_aggregate_module_workbench_diff",
        "change_kinds": [item.value for item in ModuleWorkbenchChangeKind],
        "resources": ["changes"],
        "signed_fields": ["score_delta", "task_delta"],
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_diff_capabilities() -> dict[str, Any]:
    operations = (
        "compare_module_assessments",
        "classify_added_modules",
        "classify_removed_modules",
        "classify_changed_modules",
        "classify_unchanged_modules",
        "measure_score_delta",
        "measure_task_delta",
        "query_changes",
        "export_json",
        "export_csv",
        "verify_addresses",
    )
    return {
        "version": "module-workbench-diff-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_diff",
    "module_workbench_diff_capabilities",
    "module_workbench_diff_csv",
    "module_workbench_diff_json",
    "module_workbench_diff_schema",
    "query_module_workbench_diff",
    "verify_module_workbench_diff",
]
