"""Bounded queries over D15 workbench-release closure resources."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, require_non_empty
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_DEFAULT_LIMIT,
    WORKBENCH_RELEASE_CLOSURE_MAX_LIMIT,
    WorkbenchReleaseClosureQueryResult,
)
from .workbench_release_frontier_offline_closure_support import all_rows, csv_text, markdown_table
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle
from .workbench_release_frontier_offline_query import load_workbench_release_offline_bundle

_ALIASES = {
    "artifact": "artifacts",
    "artifacts": "artifacts",
    "record": "records",
    "records": "records",
    "execution": "executions",
    "executions": "executions",
    "check": "checks",
    "checks": "checks",
    "source": "sources",
    "sources": "sources",
    "validation": "validation",
    "validations": "validation",
    "evidence": "evidence",
    "edge": "edges",
    "edges": "edges",
    "lineage": "edges",
    "view": "views",
    "views": "views",
    "queue": "queue",
    "review_queue": "queue",
    "diagnostic": "diagnostics",
    "diagnostics": "diagnostics",
    "stage": "stages",
    "stages": "stages",
    "stage_index": "stage_index",
    "operations": "operations",
    "operation": "operations",
    "controls": "controls",
    "control": "controls",
    "failures": "failures",
    "failure": "failures",
}


def _bundle(value: WorkbenchReleaseOfflineBundle | str | Path) -> WorkbenchReleaseOfflineBundle:
    return (
        value
        if isinstance(value, WorkbenchReleaseOfflineBundle)
        else load_workbench_release_offline_bundle(value, include_payloads=True)
    )


def query_workbench_release_closure(
    bundle: WorkbenchReleaseOfflineBundle | str | Path,
    *,
    resource: str = "artifacts",
    operation: str | None = None,
    role: str | None = None,
    state: str | None = None,
    capability: str | None = None,
    priority: str | None = None,
    severity: str | None = None,
    stage_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = WORKBENCH_RELEASE_CLOSURE_DEFAULT_LIMIT,
    filters: Mapping[str, Any] | None = None,
) -> WorkbenchReleaseClosureQueryResult:
    if offset < 0:
        raise ValidationError("D15 closure query offset cannot be negative")
    if limit < 1 or limit > WORKBENCH_RELEASE_CLOSURE_MAX_LIMIT:
        raise ValidationError(
            f"D15 closure query limit must be between 1 and {WORKBENCH_RELEASE_CLOSURE_MAX_LIMIT}"
        )
    normalized = require_non_empty(resource, "resource").casefold().replace("-", "_")
    try:
        resource_key = _ALIASES[normalized]
    except KeyError as exc:
        raise ValidationError(f"unknown D15 closure resource: {resource}") from exc
    value = _bundle(bundle)
    rows = list(all_rows(value)[resource_key])
    selected_filters: dict[str, Any] = {
        "operation": operation,
        "role": role,
        "state": state,
        "capability": capability,
        "priority": priority,
        "severity": severity,
        "stage_id": stage_id,
        "text": text,
    }
    for key in selected_filters:
        if selected_filters[key] in (None, "") and filters and filters.get(key) not in (None, ""):
            selected_filters[key] = filters[key]
    state = selected_filters["state"]
    text = selected_filters["text"]
    for key, expected in selected_filters.items():
        if key == "state":
            continue
        if expected in (None, "") or key == "text":
            continue
        rows = [
            row for row in rows if str(row.get(key, row.get("observed_state", ""))) == str(expected)
        ]
    if state is not None:
        wanted = state.casefold()
        rows = [
            row
            for row in rows
            if str(row.get("state", row.get("observed_state", ""))).casefold() == wanted
            or str(row.get("expected_state", "")).casefold() == wanted
            or (row.get("passed") is (wanted in {"passed", "true"}))
        ]
    if text:
        wanted = text.casefold()
        rows = [row for row in rows if wanted in canonical_json(row).casefold()]
    rows = sorted(rows, key=lambda row: (str(row.get("ordinal", "")), canonical_json(row)))
    page = tuple(rows[offset : offset + limit])
    body = {
        "bundle_id": value.bundle_id,
        "resource": resource_key,
        "filters": selected_filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": value.ready,
    }
    return WorkbenchReleaseClosureQueryResult(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-query"),
    )


def workbench_release_closure_resource_names() -> tuple[str, ...]:
    return tuple(sorted(set(_ALIASES.values())))


def export_workbench_release_closure_csv(result: WorkbenchReleaseClosureQueryResult) -> str:
    return csv_text(result.items)


def export_workbench_release_closure_markdown(result: WorkbenchReleaseClosureQueryResult) -> str:
    return markdown_table(result.items, f"D15 closure query: {result.resource}")


__all__ = [
    "export_workbench_release_closure_csv",
    "export_workbench_release_closure_markdown",
    "query_workbench_release_closure",
    "workbench_release_closure_resource_names",
]
