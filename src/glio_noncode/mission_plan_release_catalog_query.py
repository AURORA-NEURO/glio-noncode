"""Bounded queries over deterministic public mission-plan release catalogs.

Catalog creation is intentionally append-free and deterministic.  This module
provides the read side: a consumer can filter by release identity, plan
identity, state, acceptance, workflow kind, and aggregate size, then page the
canonically ordered rows.  It accepts an in-memory catalog or a verified
offline catalog directory and returns only public catalog entries.

The query object is strict and bounded so it can be used by both the local
CLI and the JSON API without an unbounded scan contract.  Query results carry
their own content address and deterministic exports; no request text,
routing metadata, attribution, language, model, producer, or identity data is
copied into the result.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    MissionPlanReleaseCatalogBundle,
    MissionPlanReleaseCatalogEntry,
    MissionPlanReleaseCatalogOffline,
    load_mission_plan_release_catalog,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_QUERY_VERSION = "mission-plan-release-catalog-query-v1"
MISSION_PLAN_RELEASE_CATALOG_QUERY_SCHEMA_VERSION = "mission-plan-release-catalog-query-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_QUERY_CAPABILITIES_VERSION = "mission-plan-release-catalog-query-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_LIMIT = 256
MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_OFFSET = 1_000_000


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _text(value, field)


def _bounded_int(value: Any, field: str, *, maximum: int, allow_zero: bool) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    minimum = 0 if allow_zero else 1
    if number < minimum or number > maximum:
        raise ValidationError(f"{field} must be between {minimum} and {maximum}")
    return number


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogQuery:
    """Strict bounded catalog query."""

    release_id: str | None = None
    plan_id: str | None = None
    state: str | None = None
    accepted: bool | None = None
    workflow_kind: str | None = None
    min_step_count: int | None = None
    max_step_count: int | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        for field in ("release_id", "plan_id", "state", "workflow_kind"):
            value = getattr(self, field)
            if value is not None:
                _text(value, f"catalog_query.{field}")
        if self.accepted is not None and not isinstance(self.accepted, bool):
            raise ValidationError("catalog_query.accepted must be boolean or null")
        for field in ("min_step_count", "max_step_count"):
            value = getattr(self, field)
            if value is not None:
                _bounded_int(value, f"catalog_query.{field}", maximum=1_000_000, allow_zero=True)
        if self.min_step_count is not None and self.max_step_count is not None:
            if self.min_step_count > self.max_step_count:
                raise ValidationError("catalog query minimum step count exceeds maximum")
        _bounded_int(self.offset, "catalog_query.offset", maximum=MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_OFFSET, allow_zero=True)
        _bounded_int(self.limit, "catalog_query.limit", maximum=MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_LIMIT, allow_zero=False)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "MissionPlanReleaseCatalogQuery":
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValidationError("catalog query must be an object")
        body = dict(value)
        allowed = {
            "release_id",
            "plan_id",
            "state",
            "accepted",
            "workflow_kind",
            "min_step_count",
            "max_step_count",
            "offset",
            "limit",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog query contains unsupported fields: {sorted(unknown)}")
        return cls(
            release_id=_optional_text(body.get("release_id"), "catalog_query.release_id"),
            plan_id=_optional_text(body.get("plan_id"), "catalog_query.plan_id"),
            state=_optional_text(body.get("state"), "catalog_query.state"),
            accepted=body.get("accepted"),
            workflow_kind=_optional_text(body.get("workflow_kind"), "catalog_query.workflow_kind"),
            min_step_count=body.get("min_step_count"),
            max_step_count=body.get("max_step_count"),
            offset=body.get("offset", 0),
            limit=body.get("limit", 50),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "query_version": MISSION_PLAN_RELEASE_CATALOG_QUERY_VERSION,
                "release_id": self.release_id,
                "plan_id": self.plan_id,
                "state": self.state,
                "accepted": self.accepted,
                "workflow_kind": self.workflow_kind,
                "min_step_count": self.min_step_count,
                "max_step_count": self.max_step_count,
                "offset": self.offset,
                "limit": self.limit,
            }
        )


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogQueryResult:
    """Addressed page of catalog entries."""

    query_version: str
    catalog_id: str
    catalog_address: str
    total_matches: int
    offset: int
    limit: int
    has_more: bool
    query: MissionPlanReleaseCatalogQuery
    entries: tuple[MissionPlanReleaseCatalogEntry, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.query_version != MISSION_PLAN_RELEASE_CATALOG_QUERY_VERSION:
            raise ValidationError("catalog query result version is invalid")
        _text(self.catalog_id, "catalog_query_result.catalog_id", maximum=96)
        _text(self.catalog_address, "catalog_query_result.catalog_address")
        if self.total_matches < 0 or self.offset < 0 or self.limit <= 0:
            raise ValidationError("catalog query result bounds are invalid")
        if len(self.entries) > self.limit:
            raise ValidationError("catalog query result page exceeds limit")

    @property
    def returned_count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        body = {
            "query_version": self.query_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "total_matches": self.total_matches,
            "returned_count": self.returned_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "query": self.query,
            "entries": self.entries,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _as_catalog(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseCatalog:
    if isinstance(value, MissionPlanReleaseCatalog):
        return value
    if isinstance(value, MissionPlanReleaseCatalogBundle):
        return value.catalog
    if isinstance(value, MissionPlanReleaseCatalogOffline):
        return value.catalog
    if isinstance(value, (str, Path)):
        return load_mission_plan_release_catalog(value).catalog
    body = dict(value)
    if "catalog" in body and isinstance(body["catalog"], Mapping):
        body = dict(body["catalog"])
    return MissionPlanReleaseCatalog.from_mapping(body)


def _matches(entry: MissionPlanReleaseCatalogEntry, query: MissionPlanReleaseCatalogQuery) -> bool:
    if query.release_id is not None and entry.release_id != query.release_id:
        return False
    if query.plan_id is not None and entry.plan_id != query.plan_id:
        return False
    if query.state is not None and entry.state != query.state:
        return False
    if query.accepted is not None and entry.accepted is not query.accepted:
        return False
    if query.workflow_kind is not None and query.workflow_kind not in entry.workflow_kinds:
        return False
    if query.min_step_count is not None and entry.step_count < query.min_step_count:
        return False
    if query.max_step_count is not None and entry.step_count > query.max_step_count:
        return False
    return True


def query_mission_plan_release_catalog(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
    query: MissionPlanReleaseCatalogQuery | Mapping[str, Any] | None = None,
) -> MissionPlanReleaseCatalogQueryResult:
    """Return a stable bounded page from a public release catalog."""

    catalog = _as_catalog(value)
    selected_query = (
        query if isinstance(query, MissionPlanReleaseCatalogQuery) else MissionPlanReleaseCatalogQuery.from_mapping(query)
    )
    matches = tuple(entry for entry in catalog.entries if _matches(entry, selected_query))
    page = matches[selected_query.offset : selected_query.offset + selected_query.limit]
    body = {
        "query_version": MISSION_PLAN_RELEASE_CATALOG_QUERY_VERSION,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "total_matches": len(matches),
        "offset": selected_query.offset,
        "limit": selected_query.limit,
        "has_more": selected_query.offset + len(page) < len(matches),
        "query": selected_query,
        "entries": page,
        "accepted": catalog.accepted,
    }
    return MissionPlanReleaseCatalogQueryResult(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-query"),
    )


def mission_plan_release_catalog_query_json(value: MissionPlanReleaseCatalogQueryResult) -> str:
    """Render a query page as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_catalog_query_csv(value: MissionPlanReleaseCatalogQueryResult) -> str:
    """Render one deterministic row per returned release."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "release_id",
            "release_address",
            "plan_id",
            "plan_address",
            "state",
            "decision",
            "accepted",
            "step_count",
            "optional_step_count",
            "deterministic_step_count",
            "network_step_count",
            "artifact_count",
            "check_count",
            "warning_count",
            "workflow_kinds",
            "content_address",
        )
    )
    for item in value.entries:
        writer.writerow(
            (
                item.release_id,
                item.release_address,
                item.plan_id,
                item.plan_address,
                item.state,
                item.decision,
                item.accepted,
                item.step_count,
                item.optional_step_count,
                item.deterministic_step_count,
                item.network_step_count,
                item.artifact_count,
                item.check_count,
                item.warning_count,
                "|".join(item.workflow_kinds),
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_release_catalog_query_markdown(value: MissionPlanReleaseCatalogQueryResult) -> str:
    """Render a review-safe query page."""

    lines = [
        "# Mission plan release catalog query",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Matches: `{value.total_matches}`",
        f"- Page: `{value.offset}`–`{value.offset + value.returned_count}`",
        f"- Has more: `{value.has_more}`",
        "",
        "| Release | Plan | State | Accepted | Steps | Kinds |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    lines.extend(
        f"| `{item.release_id}` | `{item.plan_id}` | `{item.state}` | `{item.accepted}` | "
        f"{item.step_count} | `{', '.join(item.workflow_kinds)}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_query_export_payloads(
    value: MissionPlanReleaseCatalogQueryResult,
) -> dict[str, str]:
    """Return deterministic query projections."""

    return {
        "mission-plan-release-catalog-query.json": mission_plan_release_catalog_query_json(value),
        "mission-plan-release-catalog-query.csv": mission_plan_release_catalog_query_csv(value),
        "mission-plan-release-catalog-query.md": mission_plan_release_catalog_query_markdown(value),
    }


def mission_plan_release_catalog_query_schema() -> dict[str, Any]:
    """Return the catalog query contract."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_QUERY_SCHEMA_VERSION,
        "query_version": MISSION_PLAN_RELEASE_CATALOG_QUERY_VERSION,
        "filters": {
            "release_id": {"type": ["string", "null"]},
            "plan_id": {"type": ["string", "null"]},
            "state": {"type": ["string", "null"]},
            "accepted": {"type": ["boolean", "null"]},
            "workflow_kind": {"type": ["string", "null"]},
            "min_step_count": {"type": ["integer", "null"], "minimum": 0},
            "max_step_count": {"type": ["integer", "null"], "minimum": 0},
            "offset": {"type": "integer", "minimum": 0, "maximum": MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_OFFSET},
            "limit": {"type": "integer", "minimum": 1, "maximum": MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_LIMIT},
        },
        "result_fields": [
            "query_version",
            "catalog_id",
            "catalog_address",
            "total_matches",
            "returned_count",
            "offset",
            "limit",
            "has_more",
            "query",
            "entries",
            "accepted",
            "content_address",
        ],
        "stable_order": "catalog release ID then plan address",
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_catalog_query_capabilities() -> dict[str, Any]:
    """Return catalog query capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_QUERY_CAPABILITIES_VERSION,
        "bounded_pagination": True,
        "release_filter": True,
        "plan_filter": True,
        "state_filter": True,
        "acceptance_filter": True,
        "workflow_kind_filter": True,
        "step_count_filters": True,
        "verified_offline_input": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
        "timestamp_free": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_QUERY_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_LIMIT",
    "MISSION_PLAN_RELEASE_CATALOG_QUERY_MAX_OFFSET",
    "MISSION_PLAN_RELEASE_CATALOG_QUERY_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_QUERY_VERSION",
    "MissionPlanReleaseCatalogQuery",
    "MissionPlanReleaseCatalogQueryResult",
    "mission_plan_release_catalog_query_capabilities",
    "mission_plan_release_catalog_query_csv",
    "mission_plan_release_catalog_query_export_payloads",
    "mission_plan_release_catalog_query_json",
    "mission_plan_release_catalog_query_markdown",
    "mission_plan_release_catalog_query_schema",
    "query_mission_plan_release_catalog",
]
