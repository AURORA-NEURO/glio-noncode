"""Bounded queries over whole-product release-assurance evidence."""

from __future__ import annotations

import json
from typing import Any

from .errors import ValidationError
from .release_assurance_bundle import release_assurance_snapshot_rows
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_DEFAULT_LIMIT,
    RELEASE_ASSURANCE_MAX_LIMIT,
    RELEASE_ASSURANCE_RESOURCE_NAMES,
    ReleaseAssuranceQueryResult,
    ReleaseAssuranceSnapshot,
)
from .release_assurance_support import csv_payload, markdown_payload, text_matches
from .serialization import content_hash, jsonable


def _rows(snapshot: ReleaseAssuranceSnapshot, resource: str) -> list[dict[str, Any]]:
    rows = release_assurance_snapshot_rows(snapshot)
    if resource not in rows:
        raise ValidationError(f"unsupported release-assurance resource: {resource}")
    return [dict(item) for item in rows[resource]]


def _matches(
    row: dict[str, Any],
    *,
    domain_id: str | None,
    plane: str | None,
    state: str | None,
    passed_only: bool,
    text: str | None,
) -> bool:
    if domain_id and str(row.get("domain_id", "")) != domain_id:
        return False
    if plane and str(row.get("plane", "")).casefold() != plane.casefold():
        return False
    if state and str(row.get("state", "")).casefold() != state.casefold():
        return False
    if passed_only and not bool(row.get("passed", row.get("accepted", False))):
        return False
    return text_matches(row, text)


def query_release_assurance(
    snapshot: ReleaseAssuranceSnapshot,
    *,
    resource: str = "domains",
    domain_id: str | None = None,
    plane: str | None = None,
    state: str | None = None,
    passed_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = RELEASE_ASSURANCE_DEFAULT_LIMIT,
) -> ReleaseAssuranceQueryResult:
    """Return one deterministic, bounded page from the assurance snapshot."""

    if resource not in RELEASE_ASSURANCE_RESOURCE_NAMES or resource not in {
        "domains", "checks", "evidence"
    }:
        raise ValidationError(f"unsupported release-assurance resource: {resource}")
    if offset < 0 or limit < 1 or limit > RELEASE_ASSURANCE_MAX_LIMIT:
        raise ValidationError("release-assurance pagination is outside its contract")
    rows = [
        row for row in _rows(snapshot, resource)
        if _matches(
            row,
            domain_id=domain_id,
            plane=plane,
            state=state,
            passed_only=passed_only,
            text=text,
        )
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("domain_id", "")),
            str(row.get("check_id", row.get("link_id", row.get("title", "")))),
        )
    )
    page = tuple(rows[offset : offset + limit])
    filters = {
        "domain_id": domain_id,
        "plane": plane,
        "state": state,
        "passed_only": passed_only,
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
    return ReleaseAssuranceQueryResult(
        snapshot.bundle_id,
        resource,
        filters,
        len(rows),
        offset,
        limit,
        page,
        snapshot.accepted,
        content_hash(body, prefix="release-assurance-query"),
    )


def export_release_assurance_query_csv(result: ReleaseAssuranceQueryResult) -> bytes:
    """Export one bounded result as deterministic CSV."""

    return csv_payload(result.items)


def export_release_assurance_query_markdown(result: ReleaseAssuranceQueryResult) -> bytes:
    """Export one bounded result as reviewer-readable Markdown."""

    return markdown_payload(f"Release assurance: {result.resource}", result.items)


def release_assurance_query_text(result: ReleaseAssuranceQueryResult) -> str:
    """Render one query result as stable indented JSON text."""

    return json.dumps(jsonable(result), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


__all__ = [
    "export_release_assurance_query_csv",
    "export_release_assurance_query_markdown",
    "query_release_assurance",
    "release_assurance_query_text",
]
