"""Bounded deterministic queries over the service-release registry."""

from __future__ import annotations

import json
from typing import Any

from .errors import ValidationError
from .service_release_bundle import service_release_snapshot_rows
from .service_release_contracts import (
    SERVICE_RELEASE_DEFAULT_LIMIT,
    SERVICE_RELEASE_MAX_LIMIT,
    SERVICE_RELEASE_RESOURCE_NAMES,
    ServiceReleaseQueryResult,
    ServiceReleaseSnapshot,
)
from .service_release_support import csv_payload, markdown_payload, text_matches
from .serialization import content_hash, jsonable


def _rows(snapshot: ServiceReleaseSnapshot, resource: str) -> list[dict[str, Any]]:
    values = service_release_snapshot_rows(snapshot)
    if resource not in values:
        raise ValidationError(f"unsupported service release resource: {resource}")
    return [dict(item) for item in values[resource]]


def _matches(
    row: dict[str, Any],
    *,
    surface_id: str | None,
    state: str | None,
    relation: str | None,
    accepted_only: bool,
    text: str | None,
) -> bool:
    if surface_id and str(row.get("surface_id", row.get("source_surface_id", ""))) != surface_id:
        return False
    if state and str(row.get("state", "")).casefold() != state.casefold():
        return False
    if relation and str(row.get("relation", "")).casefold() != relation.casefold():
        return False
    if accepted_only and not bool(row.get("accepted", row.get("passed", False))):
        return False
    return text_matches(row, text)


def query_service_release(
    snapshot: ServiceReleaseSnapshot,
    *,
    resource: str = "surfaces",
    surface_id: str | None = None,
    state: str | None = None,
    relation: str | None = None,
    accepted_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = SERVICE_RELEASE_DEFAULT_LIMIT,
) -> ServiceReleaseQueryResult:
    """Return one stable, bounded page from the release registry."""

    if resource not in SERVICE_RELEASE_RESOURCE_NAMES or resource not in {
        "surfaces",
        "artifacts",
        "dependencies",
        "gates",
    }:
        raise ValidationError(f"unsupported service release resource: {resource}")
    if offset < 0 or limit < 1 or limit > SERVICE_RELEASE_MAX_LIMIT:
        raise ValidationError("service release pagination is outside its contract")
    rows = [
        row
        for row in _rows(snapshot, resource)
        if _matches(
            row,
            surface_id=surface_id,
            state=state,
            relation=relation,
            accepted_only=accepted_only,
            text=text,
        )
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("surface_id", row.get("source_surface_id", ""))),
            str(
                row.get(
                    "dependency_order",
                    row.get("artifact_ref", row.get("dependency_id", row.get("gate_id", ""))),
                )
            ),
        )
    )
    page = tuple(rows[offset : offset + limit])
    filters = {
        "surface_id": surface_id,
        "state": state,
        "relation": relation,
        "accepted_only": accepted_only,
        "text": text,
    }
    body = {
        "bundle_id": snapshot.bundle_id,
        "resource": resource,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": snapshot.accepted,
    }
    return ServiceReleaseQueryResult(
        snapshot.bundle_id,
        resource,
        filters,
        len(rows),
        offset,
        limit,
        page,
        snapshot.accepted,
        content_hash(body, prefix="service-release-query"),
    )


def export_service_release_query_csv(result: ServiceReleaseQueryResult) -> bytes:
    """Export one query page as deterministic CSV."""

    return csv_payload(result.items)


def export_service_release_query_markdown(result: ServiceReleaseQueryResult) -> bytes:
    """Export one query page as reviewer-readable Markdown."""

    return markdown_payload(f"Service release registry: {result.resource}", result.items)


def service_release_query_text(result: ServiceReleaseQueryResult) -> str:
    """Render one bounded query result without introducing metadata fields."""

    return json.dumps(jsonable(result), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


__all__ = [
    "export_service_release_query_csv",
    "export_service_release_query_markdown",
    "query_service_release",
    "service_release_query_text",
]
