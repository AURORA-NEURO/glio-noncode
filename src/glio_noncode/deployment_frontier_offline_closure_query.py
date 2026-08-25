"""Bounded queries over D16 deployment closure resources."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_DEFAULT_LIMIT,
    DEPLOYMENT_FRONTIER_CLOSURE_MAX_LIMIT,
    DeploymentFrontierClosureQueryResult,
)
from .deployment_frontier_offline_closure_support import all_rows, csv_text, markdown_table
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .deployment_frontier_offline_query import load_deployment_frontier_offline_bundle
from .errors import ValidationError
from .serialization import canonical_json, content_hash, require_non_empty

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
    "operation": "operations",
    "operations": "operations",
    "control": "controls",
    "controls": "controls",
    "failure": "failures",
    "failures": "failures",
    "audit_event": "audit_events",
    "audit_events": "audit_events",
    "transcript_event": "transcript_events",
    "transcript_events": "transcript_events",
    "trace": "trace_observations",
    "trace_observation": "trace_observations",
    "trace_observations": "trace_observations",
}


def _bundle(value: DeploymentFrontierOfflineBundle | str | Path) -> DeploymentFrontierOfflineBundle:
    return (
        value
        if isinstance(value, DeploymentFrontierOfflineBundle)
        else load_deployment_frontier_offline_bundle(value, include_payloads=True)
    )


def _match(row: Mapping[str, Any], key: str, expected: Any) -> bool:
    if expected in (None, ""):
        return True
    values = expected if isinstance(expected, (list, tuple, set)) else str(expected).split(",")
    wanted = {str(item).casefold().strip() for item in values if str(item).strip()}
    if key == "state":
        actual = row.get("state", row.get("observed_state", row.get("expected_state")))
        if "passed" in wanted or "failed" in wanted:
            actual = "passed" if bool(row.get("passed")) else "failed"
    else:
        actual = row.get(key, "")
    if isinstance(actual, (list, tuple, set)):
        return bool(wanted & {str(item).casefold() for item in actual})
    return str(actual).casefold() in wanted


def query_deployment_frontier_closure(
    bundle: DeploymentFrontierOfflineBundle | str | Path,
    *,
    resource: str = "records",
    operation: str | None = None,
    role: str | None = None,
    state: str | None = None,
    capability: str | None = None,
    priority: str | None = None,
    severity: str | None = None,
    stage_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = DEPLOYMENT_FRONTIER_CLOSURE_DEFAULT_LIMIT,
    filters: Mapping[str, Any] | None = None,
) -> DeploymentFrontierClosureQueryResult:
    if offset < 0:
        raise ValidationError("D16 closure query offset cannot be negative")
    if limit < 1 or limit > DEPLOYMENT_FRONTIER_CLOSURE_MAX_LIMIT:
        raise ValidationError(
            f"D16 closure query limit must be between 1 and {DEPLOYMENT_FRONTIER_CLOSURE_MAX_LIMIT}"
        )
    normalized = require_non_empty(resource, "resource").casefold().replace("-", "_")
    try:
        resource_key = _ALIASES[normalized]
    except KeyError as exc:
        raise ValidationError(f"unknown D16 closure resource: {resource}") from exc
    value = _bundle(bundle)
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
    rows = list(all_rows(value)[resource_key])
    for key, expected in selected_filters.items():
        if key == "text" or expected in (None, ""):
            continue
        rows = [row for row in rows if _match(row, key, expected)]
    if selected_filters["text"]:
        wanted = str(selected_filters["text"]).casefold()
        rows = [row for row in rows if wanted in canonical_json(row).casefold()]
    rows = sorted(rows, key=lambda row: (str(row.get("ordinal", "")), canonical_json(row)))
    body = {
        "bundle_id": value.bundle_id,
        "resource": resource_key,
        "filters": selected_filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": tuple(rows[offset : offset + limit]),
        "accepted": value.ready,
    }
    return DeploymentFrontierClosureQueryResult(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-query")
    )


def deployment_frontier_closure_resource_names() -> tuple[str, ...]:
    return tuple(sorted(set(_ALIASES.values())))


def export_deployment_frontier_closure_csv(result: DeploymentFrontierClosureQueryResult) -> str:
    return csv_text(result.items)


def export_deployment_frontier_closure_markdown(
    result: DeploymentFrontierClosureQueryResult,
) -> str:
    return markdown_table(result.items, f"D16 closure query: {result.resource}")


__all__ = [
    "deployment_frontier_closure_resource_names",
    "export_deployment_frontier_closure_csv",
    "export_deployment_frontier_closure_markdown",
    "query_deployment_frontier_closure",
]
