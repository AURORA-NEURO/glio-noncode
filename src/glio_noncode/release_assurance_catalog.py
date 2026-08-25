"""Stable public resource catalog for release-assurance clients."""

from __future__ import annotations

from collections.abc import Iterable

from .release_assurance_contracts import (
    ReleaseAssuranceCatalog,
    ReleaseAssuranceCatalogEntry,
    ReleaseAssurancePlane,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceSnapshot,
)
from .release_assurance_support import text_matches
from .serialization import content_hash


def _entry(
    resource: str,
    title: str,
    key_field: str,
    plane: ReleaseAssurancePlane,
    row_count: int,
    address: str,
    *,
    queryable: bool,
    exportable: bool,
) -> ReleaseAssuranceCatalogEntry:
    body = {
        "resource": resource,
        "title": title,
        "key_field": key_field,
        "source_plane": plane,
        "row_count": row_count,
        "address": address,
        "public": True,
        "queryable": queryable,
        "exportable": exportable,
    }
    return ReleaseAssuranceCatalogEntry(
        **body,
        content_address=content_hash(body, prefix="release-assurance-catalog-entry"),
    )


def build_release_assurance_catalog(
    snapshot: ReleaseAssuranceSnapshot,
    runtime: ReleaseAssuranceRuntimeReport | None = None,
) -> ReleaseAssuranceCatalog:
    """Build ten public resource entries with address-only lineage."""

    source_address = snapshot.content_address
    runtime_address = runtime.content_address if runtime is not None else source_address
    entries = (
        _entry("snapshot", "Four-plane assurance snapshot", "content_address",
               ReleaseAssurancePlane.CROSS_PLANE, 1, snapshot.content_address,
               queryable=False, exportable=True),
        _entry("domains", "Assurance domain rows", "domain_id", ReleaseAssurancePlane.CROSS_PLANE,
               len(snapshot.domains), content_hash(snapshot.domains, prefix="release-assurance-domains"),
               queryable=True, exportable=True),
        _entry("checks", "Cross-plane check rows", "check_id", ReleaseAssurancePlane.CROSS_PLANE,
               len(snapshot.checks), content_hash(snapshot.checks, prefix="release-assurance-checks"),
               queryable=True, exportable=True),
        _entry("evidence", "Evidence address links", "link_id", ReleaseAssurancePlane.CROSS_PLANE,
               len(snapshot.evidence), content_hash(snapshot.evidence, prefix="release-assurance-evidence"),
               queryable=True, exportable=True),
        _entry("summary", "Conserved readiness summary", "bundle_id", ReleaseAssurancePlane.RUNTIME,
               1, content_hash({"bundle_id": snapshot.bundle_id, "overall_percent": snapshot.overall_percent}, prefix="release-assurance-summary-catalog"),
               queryable=False, exportable=True),
        _entry("observability", "Events and metrics", "event_id", ReleaseAssurancePlane.RUNTIME,
               64, content_hash({"snapshot": source_address, "events": 48, "metrics": 16}, prefix="release-assurance-observability-catalog"),
               queryable=False, exportable=True),
        _entry("graph", "Connected lineage graph", "node_id", ReleaseAssurancePlane.RUNTIME,
               53, content_hash({"snapshot": source_address, "nodes": 53, "edges": 52}, prefix="release-assurance-graph-catalog"),
               queryable=False, exportable=True),
        _entry("plan", "Ordered release plan", "step_id", ReleaseAssurancePlane.RUNTIME,
               20, content_hash({"snapshot": source_address, "steps": 20}, prefix="release-assurance-plan-catalog"),
               queryable=False, exportable=True),
        _entry("views", "Reviewer views", "view_id", ReleaseAssurancePlane.RUNTIME,
               4, content_hash({"snapshot": source_address, "views": 4}, prefix="release-assurance-views-catalog"),
               queryable=False, exportable=True),
        _entry("runtime", "Staged replay runtime", "stage_id", ReleaseAssurancePlane.RUNTIME,
               12, runtime_address, queryable=False, exportable=True),
    )
    accepted = snapshot.accepted and all(item.public for item in entries)
    body = {"bundle_id": snapshot.bundle_id, "entries": entries, "accepted": accepted}
    return ReleaseAssuranceCatalog(
        snapshot.bundle_id,
        entries,
        accepted,
        content_hash(body, prefix="release-assurance-catalog"),
    )


def query_release_assurance_catalog(
    catalog: ReleaseAssuranceCatalog,
    *,
    resource: str | None = None,
    source_plane: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[ReleaseAssuranceCatalogEntry, ...]:
    """Return a deterministic bounded catalog page."""

    if offset < 0 or limit < 1 or limit > 500:
        raise ValueError("release-assurance catalog pagination is outside its contract")
    rows: Iterable[ReleaseAssuranceCatalogEntry] = catalog.entries
    if resource:
        rows = (item for item in rows if item.resource == resource)
    if source_plane:
        rows = (item for item in rows if item.source_plane.value == source_plane)
    if text:
        rows = (item for item in rows if text_matches(item.to_dict(), text))
    return tuple(sorted(rows, key=lambda item: item.resource)[offset : offset + limit])


__all__ = ["build_release_assurance_catalog", "query_release_assurance_catalog"]
