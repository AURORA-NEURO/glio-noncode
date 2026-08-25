"""Bounded offline queries over the D13 closure resources."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, require_non_empty
from .validation_design_frontier_bundle_closure_contracts import (
    VALIDATION_DESIGN_CLOSURE_DEFAULT_LIMIT,
    VALIDATION_DESIGN_CLOSURE_MAX_LIMIT,
    ValidationDesignClosureQueryResult,
)
from .validation_design_frontier_bundle_closure_support import all_rows, csv_text, markdown_table
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle
from .validation_design_frontier_bundle_query import load_validation_design_offline_bundle

_RESOURCE_ALIASES = {
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
    "stage": "stages",
    "stages": "stages",
    "plane": "planes",
    "planes": "planes",
    "operation": "operations",
    "operations": "operations",
    "issue": "issues",
    "issues": "issues",
    "state": "states",
    "states": "states",
    "review": "reviews",
    "reviews": "reviews",
}


def _bundle(value: ValidationDesignBundle | str | Path) -> ValidationDesignBundle:
    if isinstance(value, ValidationDesignBundle):
        return value
    return load_validation_design_offline_bundle(value, include_payloads=True)


def _text_matches(row: Mapping[str, Any], value: str | None) -> bool:
    return not value or value.casefold() in canonical_json(dict(row)).casefold()


def query_validation_design_closure(
    bundle: ValidationDesignBundle | str | Path,
    *,
    resource: str = "artifacts",
    operation: str | None = None,
    role: str | None = None,
    state: str | None = None,
    artifact_kind: str | None = None,
    plane_id: str | None = None,
    stage_id: str | None = None,
    issue_code: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = VALIDATION_DESIGN_CLOSURE_DEFAULT_LIMIT,
) -> ValidationDesignClosureQueryResult:
    """Return a deterministic, bounded page from an addressable resource."""

    if offset < 0:
        raise ValidationError("D13 closure query offset cannot be negative")
    if limit < 1 or limit > VALIDATION_DESIGN_CLOSURE_MAX_LIMIT:
        raise ValidationError(
            f"D13 closure query limit must be between 1 and {VALIDATION_DESIGN_CLOSURE_MAX_LIMIT}"
        )
    normalized = require_non_empty(resource, "resource").casefold()
    try:
        resource_key = _RESOURCE_ALIASES[normalized]
    except KeyError as exc:
        raise ValidationError(f"unknown D13 closure resource: {resource}") from exc
    value = _bundle(bundle)
    rows = list(all_rows(value)[resource_key])
    if operation is not None:
        rows = [row for row in rows if row.get("operation") == operation]
    if role is not None:
        rows = [row for row in rows if row.get("role") == role]
    if state is not None:
        state_value = state.casefold()
        rows = [
            row
            for row in rows
            if str(row.get("state", "")).casefold() == state_value
            or str(row.get("expected_state", "")).casefold() == state_value
            or str(row.get("observed_state", "")).casefold() == state_value
            or (row.get("passed") is (state_value == "passed"))
        ]
    if artifact_kind is not None:
        rows = [row for row in rows if row.get("kind") == artifact_kind]
    if plane_id is not None:
        rows = [
            row for row in rows if row.get("plane_id") == plane_id or row.get("plane") == plane_id
        ]
    if stage_id is not None:
        rows = [row for row in rows if row.get("stage_id") == stage_id]
    if issue_code is not None:
        rows = [
            row
            for row in rows
            if issue_code in row.get("issue_codes", ()) or row.get("issue_code") == issue_code
        ]
    rows = [row for row in rows if _text_matches(row, text)]
    selected = tuple(rows[offset : offset + limit])
    filters = {
        "resource": resource_key,
        "operation": operation,
        "role": role,
        "state": state,
        "artifact_kind": artifact_kind,
        "plane_id": plane_id,
        "stage_id": stage_id,
        "issue_code": issue_code,
        "text": text,
    }
    body = {
        "bundle_id": value.bundle_id,
        "resource": resource_key,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": selected,
        "accepted": value.accepted,
    }
    return ValidationDesignClosureQueryResult(
        bundle_id=value.bundle_id,
        resource=resource_key,
        filters=filters,
        total=len(rows),
        offset=offset,
        limit=limit,
        items=selected,
        accepted=value.accepted,
        content_address=content_hash(body, prefix="validation-design-closure-query"),
    )


def export_validation_design_closure_csv(result: ValidationDesignClosureQueryResult) -> str:
    return csv_text(result.items)


def export_validation_design_closure_markdown(result: ValidationDesignClosureQueryResult) -> str:
    return markdown_table(result.items, f"D13 closure query: {result.resource}")


def closure_query_resource_names() -> tuple[str, ...]:
    return tuple(sorted(set(_RESOURCE_ALIASES.values())))


def closure_query_summary(bundle: ValidationDesignBundle | str | Path) -> dict[str, Any]:
    value = _bundle(bundle)
    rows = all_rows(value)
    return {
        "bundle_id": value.bundle_id,
        "resources": {name: len(items) for name, items in sorted(rows.items())},
        "resource_names": list(closure_query_resource_names()),
        "accepted": value.accepted,
        "content_address": content_hash(
            {
                "bundle_id": value.bundle_id,
                "resources": {name: len(items) for name, items in sorted(rows.items())},
                "accepted": value.accepted,
            },
            prefix="validation-design-closure-query-summary",
        ),
    }


__all__ = [
    "closure_query_resource_names",
    "closure_query_summary",
    "export_validation_design_closure_csv",
    "export_validation_design_closure_markdown",
    "query_validation_design_closure",
]
