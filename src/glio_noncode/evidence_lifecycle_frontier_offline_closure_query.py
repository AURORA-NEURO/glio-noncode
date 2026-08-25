"""Bounded queries over D14 closure resources."""

from __future__ import annotations

from pathlib import Path

from .errors import ValidationError
from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_DEFAULT_LIMIT,
    EVIDENCE_LIFECYCLE_CLOSURE_MAX_LIMIT,
    EvidenceLifecycleClosureQueryResult,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows, csv_text, markdown_table
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .evidence_lifecycle_frontier_offline_query import load_evidence_lifecycle_offline_bundle
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
    "event": "events",
    "events": "events",
    "stage": "stages",
    "stages": "stages",
    "edge": "edges",
    "edges": "edges",
    "queue": "queue",
    "queues": "queue",
    "review": "reviews",
    "reviews": "reviews",
    "scenario": "scenarios",
    "scenarios": "scenarios",
    "operation": "operations",
    "operations": "operations",
    "state": "states",
    "states": "states",
}


def _bundle(value: EvidenceLifecycleOfflineBundle | str | Path) -> EvidenceLifecycleOfflineBundle:
    return (
        value
        if isinstance(value, EvidenceLifecycleOfflineBundle)
        else load_evidence_lifecycle_offline_bundle(value, include_payloads=True)
    )


def query_evidence_lifecycle_closure(
    bundle: EvidenceLifecycleOfflineBundle | str | Path,
    *,
    resource: str = "artifacts",
    operation: str | None = None,
    role: str | None = None,
    state: str | None = None,
    artifact_kind: str | None = None,
    event_type: str | None = None,
    disposition: str | None = None,
    scenario_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = EVIDENCE_LIFECYCLE_CLOSURE_DEFAULT_LIMIT,
) -> EvidenceLifecycleClosureQueryResult:
    if offset < 0:
        raise ValidationError("D14 closure query offset cannot be negative")
    if limit < 1 or limit > EVIDENCE_LIFECYCLE_CLOSURE_MAX_LIMIT:
        raise ValidationError(
            f"D14 closure query limit must be between 1 and {EVIDENCE_LIFECYCLE_CLOSURE_MAX_LIMIT}"
        )
    normalized = require_non_empty(resource, "resource").casefold()
    try:
        resource_key = _ALIASES[normalized]
    except KeyError as exc:
        raise ValidationError(f"unknown D14 closure resource: {resource}") from exc
    value = _bundle(bundle)
    rows = list(all_rows(value)[resource_key])
    if operation is not None:
        rows = [row for row in rows if row.get("operation") == operation]
    if role is not None:
        rows = [row for row in rows if row.get("role") == role]
    if state is not None:
        wanted = state.casefold()
        rows = [
            row
            for row in rows
            if str(row.get("state", row.get("observed_state", ""))).casefold() == wanted
            or str(row.get("expected_state", "")).casefold() == wanted
            or (row.get("passed") is (wanted in {"passed", "true"}))
        ]
    if artifact_kind is not None:
        rows = [row for row in rows if row.get("kind") == artifact_kind]
    if event_type is not None:
        rows = [row for row in rows if row.get("event_type") == event_type]
    if disposition is not None:
        rows = [row for row in rows if row.get("disposition") == disposition]
    if scenario_id is not None:
        rows = [row for row in rows if row.get("scenario_id") == scenario_id]
    if text:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    filters = {
        "resource": resource_key,
        "operation": operation,
        "role": role,
        "state": state,
        "artifact_kind": artifact_kind,
        "event_type": event_type,
        "disposition": disposition,
        "scenario_id": scenario_id,
        "text": text,
    }
    page = tuple(rows[offset : offset + limit])
    body = {
        "bundle_id": value.bundle_id,
        "resource": resource_key,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": value.ready,
    }
    return EvidenceLifecycleClosureQueryResult(
        bundle_id=value.bundle_id,
        resource=resource_key,
        filters=filters,
        total=len(rows),
        offset=offset,
        limit=limit,
        items=page,
        accepted=value.ready,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-query"),
    )


def evidence_lifecycle_closure_resource_names() -> tuple[str, ...]:
    return tuple(sorted(set(_ALIASES.values())))


def export_evidence_lifecycle_closure_csv(result: EvidenceLifecycleClosureQueryResult) -> str:
    return csv_text(result.items)


def export_evidence_lifecycle_closure_markdown(result: EvidenceLifecycleClosureQueryResult) -> str:
    return markdown_table(result.items, f"D14 closure query: {result.resource}")


__all__ = [
    "evidence_lifecycle_closure_resource_names",
    "export_evidence_lifecycle_closure_csv",
    "export_evidence_lifecycle_closure_markdown",
    "query_evidence_lifecycle_closure",
]
