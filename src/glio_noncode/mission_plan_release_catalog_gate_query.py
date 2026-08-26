"""Bounded query projections for public mission-plan catalog-gate checks."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGate,
    MissionPlanReleaseCatalogGateCheck,
)
from .mission_plan_release_catalog_gate_packet import (
    MissionPlanReleaseCatalogGatePacket,
    MissionPlanReleaseCatalogGatePacketOffline,
    load_mission_plan_release_catalog_gate_packet,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_VERSION = "mission-plan-release-catalog-gate-query-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_SCHEMA_VERSION = "mission-plan-release-catalog-gate-query-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_CAPABILITIES_VERSION = "mission-plan-release-catalog-gate-query-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_DEFAULT_LIMIT = 50
MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_LIMIT = 200
MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_OFFSET = 100_000


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _bounded_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValidationError(f"{field} must be between {minimum} and {maximum}")
    return parsed


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateQuery:
    """Strict bounded filter for catalog-gate checks."""

    check_id: str | None = None
    category: str | None = None
    accepted: bool | None = None
    text: str | None = None
    offset: int = 0
    limit: int = MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_DEFAULT_LIMIT

    def __post_init__(self) -> None:
        for field in ("check_id", "category", "text"):
            value = getattr(self, field)
            if value is not None:
                _text(value, f"catalog_gate_query.{field}", maximum=180)
        if self.accepted is not None:
            _bool(self.accepted, "catalog_gate_query.accepted")
        _bounded_int(self.offset, "catalog_gate_query.offset", 0, MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_OFFSET)
        _bounded_int(self.limit, "catalog_gate_query.limit", 1, MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_LIMIT)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "MissionPlanReleaseCatalogGateQuery":
        if value is None:
            return cls()
        body = _mapping(value, "catalog gate query")
        allowed = {"check_id", "category", "accepted", "text", "offset", "limit"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate query contains unsupported fields: {sorted(unknown)}")
        return cls(
            check_id=None if body.get("check_id") is None else _text(body.get("check_id"), "catalog_gate_query.check_id"),
            category=None if body.get("category") is None else _text(body.get("category"), "catalog_gate_query.category"),
            accepted=None if body.get("accepted") is None else _bool(body.get("accepted"), "catalog_gate_query.accepted"),
            text=None if body.get("text") is None else _text(body.get("text"), "catalog_gate_query.text"),
            offset=_bounded_int(body.get("offset", 0), "catalog_gate_query.offset", 0, MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_OFFSET),
            limit=_bounded_int(body.get("limit", MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_DEFAULT_LIMIT), "catalog_gate_query.limit", 1, MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_LIMIT),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateQueryResult:
    """Addressed page of public gate checks."""

    query_version: str
    catalog_id: str
    catalog_address: str
    gate_address: str
    query: MissionPlanReleaseCatalogGateQuery
    total_matches: int
    checks: tuple[MissionPlanReleaseCatalogGateCheck, ...]
    has_more: bool
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.query_version != MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_VERSION:
            raise ValidationError("catalog gate query version is invalid")
        for field in ("catalog_id", "catalog_address", "gate_address", "content_address"):
            _text(getattr(self, field), f"catalog_gate_query_result.{field}")
        if isinstance(self.total_matches, bool) or not isinstance(self.total_matches, int) or self.total_matches < 0:
            raise ValidationError("catalog gate query total must be non-negative")
        if len(self.checks) > self.query.limit:
            raise ValidationError("catalog gate query page exceeds its limit")
        _bool(self.has_more, "catalog_gate_query_result.has_more")
        _bool(self.accepted, "catalog_gate_query_result.accepted")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateQueryResult":
        body = _mapping(value, "catalog gate query result")
        allowed = {
            "query_version",
            "catalog_id",
            "catalog_address",
            "gate_address",
            "query",
            "total_matches",
            "checks",
            "has_more",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate query result contains unsupported fields: {sorted(unknown)}")
        raw_checks = body.get("checks", ())
        if not isinstance(raw_checks, (list, tuple)):
            raise ValidationError("catalog gate query result checks must be an array")
        result = cls(
            query_version=_text(body.get("query_version"), "catalog_gate_query_result.query_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_gate_query_result.catalog_id"),
            catalog_address=_text(body.get("catalog_address"), "catalog_gate_query_result.catalog_address"),
            gate_address=_text(body.get("gate_address"), "catalog_gate_query_result.gate_address"),
            query=MissionPlanReleaseCatalogGateQuery.from_mapping(body.get("query")),
            total_matches=_bounded_int(body.get("total_matches"), "catalog_gate_query_result.total_matches", 0, MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_OFFSET),
            checks=tuple(MissionPlanReleaseCatalogGateCheck.from_mapping(item) for item in raw_checks),
            has_more=_bool(body.get("has_more"), "catalog_gate_query_result.has_more"),
            accepted=_bool(body.get("accepted"), "catalog_gate_query_result.accepted"),
            content_address=_text(body.get("content_address"), "catalog_gate_query_result.content_address"),
        )
        expected = {
            "query_version": result.query_version,
            "catalog_id": result.catalog_id,
            "catalog_address": result.catalog_address,
            "gate_address": result.gate_address,
            "query": result.query,
            "total_matches": result.total_matches,
            "checks": result.checks,
            "has_more": result.has_more,
            "accepted": result.accepted,
        }
        if result.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-query"):
            raise ValidationError("catalog gate query result content address does not reconcile")
        return result

    def to_dict(self) -> dict[str, Any]:
        body = {
            "query_version": self.query_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "gate_address": self.gate_address,
            "query": self.query.to_dict(),
            "total_matches": self.total_matches,
            "checks": self.checks,
            "has_more": self.has_more,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _as_gate(value: MissionPlanReleaseCatalogGate | MissionPlanReleaseCatalogGatePacket | MissionPlanReleaseCatalogGatePacketOffline | Mapping[str, Any] | str | Path) -> MissionPlanReleaseCatalogGate:
    if isinstance(value, MissionPlanReleaseCatalogGate):
        return value
    if isinstance(value, MissionPlanReleaseCatalogGatePacket):
        return value.gate
    if isinstance(value, MissionPlanReleaseCatalogGatePacketOffline):
        return value.gate
    if isinstance(value, (str, Path)):
        return load_mission_plan_release_catalog_gate_packet(value).gate
    body = _mapping(value, "catalog gate query source")
    if isinstance(body.get("gate"), Mapping):
        body = _mapping(body["gate"], "catalog gate query gate")
    return MissionPlanReleaseCatalogGate.from_mapping(body)


def _matches(item: MissionPlanReleaseCatalogGateCheck, query: MissionPlanReleaseCatalogGateQuery) -> bool:
    if query.check_id is not None and item.check_id != query.check_id:
        return False
    if query.category is not None and item.category != query.category:
        return False
    if query.accepted is not None and item.accepted != query.accepted:
        return False
    if query.text is not None:
        needle = query.text.casefold()
        haystack = " ".join((item.check_id, item.category, item.message, canonical_json(item.observed), canonical_json(item.expected))).casefold()
        if needle not in haystack:
            return False
    return True


def query_mission_plan_release_catalog_gate(
    value: MissionPlanReleaseCatalogGate | MissionPlanReleaseCatalogGatePacket | MissionPlanReleaseCatalogGatePacketOffline | Mapping[str, Any] | str | Path,
    query: MissionPlanReleaseCatalogGateQuery | Mapping[str, Any] | None = None,
) -> MissionPlanReleaseCatalogGateQueryResult:
    """Return a stable bounded page of checks."""

    gate = _as_gate(value)
    selected = query if isinstance(query, MissionPlanReleaseCatalogGateQuery) else MissionPlanReleaseCatalogGateQuery.from_mapping(query)
    matches = tuple(item for item in gate.checks if _matches(item, selected))
    page = matches[selected.offset : selected.offset + selected.limit]
    body = {
        "query_version": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_VERSION,
        "catalog_id": gate.catalog_id,
        "catalog_address": gate.catalog_address,
        "gate_address": gate.content_address,
        "query": selected,
        "total_matches": len(matches),
        "checks": page,
        "has_more": selected.offset + len(page) < len(matches),
        "accepted": gate.accepted,
    }
    return MissionPlanReleaseCatalogGateQueryResult(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-query"),
    )


def mission_plan_release_catalog_gate_query_json(result: MissionPlanReleaseCatalogGateQueryResult | Mapping[str, Any]) -> str:
    value = result if isinstance(result, MissionPlanReleaseCatalogGateQueryResult) else MissionPlanReleaseCatalogGateQueryResult.from_mapping(result)
    return canonical_json(value.to_dict())


def mission_plan_release_catalog_gate_query_csv(result: MissionPlanReleaseCatalogGateQueryResult | Mapping[str, Any]) -> str:
    value = result if isinstance(result, MissionPlanReleaseCatalogGateQueryResult) else MissionPlanReleaseCatalogGateQueryResult.from_mapping(result)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("check_id", "category", "accepted", "observed", "expected", "message", "content_address"))
    for item in value.checks:
        writer.writerow((item.check_id, item.category, str(item.accepted).lower(), canonical_json(item.observed), canonical_json(item.expected), item.message, item.content_address))
    return output.getvalue()


def mission_plan_release_catalog_gate_query_markdown(result: MissionPlanReleaseCatalogGateQueryResult | Mapping[str, Any]) -> str:
    value = result if isinstance(result, MissionPlanReleaseCatalogGateQueryResult) else MissionPlanReleaseCatalogGateQueryResult.from_mapping(result)
    lines = [
        "# Mission plan release catalog gate query",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Gate address: `{value.gate_address}`",
        f"- Matches: {value.total_matches}",
        f"- Offset: {value.query.offset}",
        f"- Limit: {value.query.limit}",
        f"- Has more: {str(value.has_more).lower()}",
        "",
        "| Check | Category | Accepted | Message |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| `{item.check_id}` | `{item.category}` | `{str(item.accepted).lower()}` | {item.message} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_gate_query_export_payloads(result: MissionPlanReleaseCatalogGateQueryResult | Mapping[str, Any]) -> dict[str, str]:
    value = result if isinstance(result, MissionPlanReleaseCatalogGateQueryResult) else MissionPlanReleaseCatalogGateQueryResult.from_mapping(result)
    return {
        "mission-plan-release-catalog-gate-query.json": mission_plan_release_catalog_gate_query_json(value),
        "mission-plan-release-catalog-gate-query.csv": mission_plan_release_catalog_gate_query_csv(value),
        "mission-plan-release-catalog-gate-query.md": mission_plan_release_catalog_gate_query_markdown(value),
    }


def mission_plan_release_catalog_gate_query_schema() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_SCHEMA_VERSION,
        "query_version": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_VERSION,
        "default_limit": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_DEFAULT_LIMIT,
        "max_limit": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_LIMIT,
        "max_offset": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_OFFSET,
        "filters": ["check_id", "category", "accepted", "text"],
        "page_fields": ["total_matches", "checks", "has_more", "content_address"],
        "timestamp_free": True,
        "read_only": True,
    }


def mission_plan_release_catalog_gate_query_capabilities() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_CAPABILITIES_VERSION,
        "check_id_filter": True,
        "category_filter": True,
        "accepted_filter": True,
        "text_filter": True,
        "bounded_pagination": True,
        "verified_offline_input": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "read_only": True,
        "timestamp_free": True,
        "handler_execution": False,
        "clinical_authorization": False,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_DEFAULT_LIMIT",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_LIMIT",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_MAX_OFFSET",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_QUERY_VERSION",
    "MissionPlanReleaseCatalogGateQuery",
    "MissionPlanReleaseCatalogGateQueryResult",
    "mission_plan_release_catalog_gate_query_capabilities",
    "mission_plan_release_catalog_gate_query_csv",
    "mission_plan_release_catalog_gate_query_export_payloads",
    "mission_plan_release_catalog_gate_query_json",
    "mission_plan_release_catalog_gate_query_markdown",
    "mission_plan_release_catalog_gate_query_schema",
    "query_mission_plan_release_catalog_gate",
]
