"""Portable registry for independently verified series-release packages.

This boundary records which release packages were admitted to a bounded
publication set. It retains package and release addresses, never merges
nested scientific data, and requires every package to verify before admission.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_release as release_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = release_model.VERSION + "-registry-v1"
BOUNDARY = release_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = release_model.RELEASE_PREFIX + "-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
DIFF_PREFIX = REGISTRY_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
ENTRIES_NAME = "entries.json"
REGISTRY_NAME = "registry.json"
FILES = (MANIFEST_NAME, ENTRIES_NAME, REGISTRY_NAME)
DIFF_NAME = "diff.json"
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)
DEFAULT_REGISTRY_ID = "glio-noncode-decision-assurance-history-series-release-registry"
DEFAULT_DIFF_ID = "glio-noncode-decision-assurance-history-series-release-registry-diff"
MAX_ENTRIES = 4096
MAX_QUERY_ITEMS = 4096
_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _mapping_sequence(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return tuple(_mapping(item, field) for item in value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _state(value: Any, field: str = "registry state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in release_model.SeriesReleaseState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _action(value: Any, field: str = "registry diff action") -> str:
    value = _text(value, field, 32)
    if value not in {"added", "removed", "unchanged", "changed"}:
        raise ValidationError(f"{field} is invalid")
    return value


def _direction(value: Any, field: str = "registry diff direction") -> str:
    value = _text(value, field, 32)
    if value not in {"unchanged", "improved", "regressed", "changed"}:
        raise ValidationError(f"{field} is invalid")
    return value


class DecisionAssuranceHistorySeriesReleaseRegistryEntry:
    """One admitted release package with no nested source-path leakage."""

    def __init__(
        self,
        ordinal: int,
        package_id: str,
        release_id: str,
        package_address: str,
        release_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        content_address: str,
    ) -> None:
        self.ordinal, self.package_id, self.release_id = ordinal, package_id, release_id
        self.package_address, self.release_address = package_address, release_address
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "registry entry ordinal", MAX_ENTRIES - 1)
        _text(self.package_id, "registry entry package ID", 256)
        _text(self.release_id, "registry entry release ID", 256)
        _address(self.package_address, "registry entry package address")
        _address(self.release_address, "registry entry release address")
        _state(self.state)
        _bool(self.accepted, "registry entry accepted")
        _bool(self.release_ready, "registry entry release-ready")
        if self.release_ready and (not self.accepted or self.state != "ready"):
            raise ValidationError("registry entry release-ready state is inconsistent")
        if self.state == "ready" and not self.release_ready:
            raise ValidationError("ready registry entry must be release-ready")
        if self.state == "blocked" and self.accepted:
            raise ValidationError("blocked registry entry cannot be accepted")
        _address(self.content_address, "registry entry address")
        if (
            not self.content_address.startswith("pending:")
            and address_decision_assurance_history_series_release_registry_entry(self)
            != self.content_address
        ):
            raise ValidationError("registry entry address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("registry entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "package_id": self.package_id,
            "release_id": self.release_id,
            "package_address": self.package_address,
            "release_address": self.release_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }


def address_decision_assurance_history_series_release_registry_entry(
    value: DecisionAssuranceHistorySeriesReleaseRegistryEntry,
) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DecisionAssuranceHistorySeriesReleaseRegistry:
    """Sorted, unique admission registry for release packages."""

    def __init__(
        self,
        registry_id: str,
        version: str,
        boundary: str,
        entry_count: int,
        ready_count: int,
        hold_count: int,
        blocked_count: int,
        accepted_count: int,
        release_ready_count: int,
        entries: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryEntry],
        content_address: str,
    ) -> None:
        self.registry_id, self.version, self.boundary = registry_id, version, boundary
        self.entry_count, self.ready_count, self.hold_count = entry_count, ready_count, hold_count
        self.blocked_count, self.accepted_count, self.release_ready_count = (
            blocked_count,
            accepted_count,
            release_ready_count,
        )
        self.entries, self.content_address = tuple(entries), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.registry_id, "release registry ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release registry contract is invalid")
        _count(self.entry_count, "registry entry count", MAX_ENTRIES)
        for name, value in (
            ("ready", self.ready_count),
            ("hold", self.hold_count),
            ("blocked", self.blocked_count),
            ("accepted", self.accepted_count),
            ("release-ready", self.release_ready_count),
        ):
            _count(value, f"registry {name} count", MAX_ENTRIES)
        if (
            self.entry_count != len(self.entries)
            or self.ready_count + self.hold_count + self.blocked_count != self.entry_count
        ):
            raise ValidationError("registry state counts are not conserved")
        if self.accepted_count > self.entry_count or self.release_ready_count > self.accepted_count:
            raise ValidationError("registry acceptance counts are not conserved")
        package_ids, release_ids, addresses = set(), set(), set()
        for ordinal, entry in enumerate(self.entries):
            if (
                not isinstance(entry, DecisionAssuranceHistorySeriesReleaseRegistryEntry)
                or entry.ordinal != ordinal
            ):
                raise ValidationError("registry entries must have contiguous ordinals")
            if (
                entry.package_id in package_ids
                or entry.release_id in release_ids
                or entry.content_address in addresses
            ):
                raise ValidationError("registry entries must be unique")
            package_ids.add(entry.package_id)
            release_ids.add(entry.release_id)
            addresses.add(entry.content_address)
            if entry.state == "ready" and not entry.accepted:
                raise ValidationError("ready registry entry must be accepted")
            if entry.accepted != (entry.state != "blocked"):
                raise ValidationError("registry entry acceptance projection is invalid")
        if (
            self.ready_count != sum(entry.state == "ready" for entry in self.entries)
            or self.hold_count != sum(entry.state == "hold" for entry in self.entries)
            or self.blocked_count != sum(entry.state == "blocked" for entry in self.entries)
        ):
            raise ValidationError("registry state counts do not match entries")
        if self.accepted_count != sum(
            entry.accepted for entry in self.entries
        ) or self.release_ready_count != sum(entry.release_ready for entry in self.entries):
            raise ValidationError("registry readiness counts do not match entries")
        _address(self.content_address, "release registry address")
        if (
            not self.content_address.startswith("pending:")
            and address_decision_assurance_history_series_release_registry(self)
            != self.content_address
        ):
            raise ValidationError("release registry address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("release registry crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "version": self.version,
            "boundary": self.boundary,
            "entry_count": self.entry_count,
            "ready_count": self.ready_count,
            "hold_count": self.hold_count,
            "blocked_count": self.blocked_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"entries": [entry.to_dict() for entry in self.entries]}


def address_decision_assurance_history_series_release_registry(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=REGISTRY_PREFIX)


def _entry_from_package(
    ordinal: int, package: release_model.DecisionAssuranceHistorySeriesReleasePackage
) -> DecisionAssuranceHistorySeriesReleaseRegistryEntry:
    body = {
        "ordinal": ordinal,
        "package_id": package.package_id,
        "release_id": package.release.release_id,
        "package_address": package.content_address,
        "release_address": package.release.content_address,
        "state": package.release.state,
        "accepted": package.release.accepted,
        "release_ready": package.release.release_ready,
        "content_address": "pending:registry-entry",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryEntry(**body)
    body["content_address"] = address_decision_assurance_history_series_release_registry_entry(
        provisional
    )
    return DecisionAssuranceHistorySeriesReleaseRegistryEntry(**body)


def build_decision_assurance_history_series_release_registry(
    packages: Sequence[release_model.DecisionAssuranceHistorySeriesReleasePackage],
    *,
    registry_id: str = DEFAULT_REGISTRY_ID,
) -> DecisionAssuranceHistorySeriesReleaseRegistry:
    if not isinstance(packages, (list, tuple)) or not packages:
        raise ValidationError("release registry requires one or more packages")
    if len(packages) > MAX_ENTRIES:
        raise ValidationError("release registry exceeds its entry bound")
    verified = []
    for package in packages:
        if not isinstance(package, release_model.DecisionAssuranceHistorySeriesReleasePackage):
            raise ValidationError("release registry packages must be typed release packages")
        verified.append(
            release_model.verify_decision_assurance_history_series_release_package(package)
        )
    ordered = sorted(
        verified, key=lambda item: (item.package_id, item.release.release_id, item.content_address)
    )
    entries = tuple(
        _entry_from_package(ordinal, package) for ordinal, package in enumerate(ordered)
    )
    body = {
        "registry_id": registry_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "entry_count": len(entries),
        "ready_count": sum(entry.state == "ready" for entry in entries),
        "hold_count": sum(entry.state == "hold" for entry in entries),
        "blocked_count": sum(entry.state == "blocked" for entry in entries),
        "accepted_count": sum(entry.accepted for entry in entries),
        "release_ready_count": sum(entry.release_ready for entry in entries),
        "entries": entries,
        "content_address": "pending:release-registry",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistry(**body)
    body["content_address"] = address_decision_assurance_history_series_release_registry(
        provisional
    )
    return DecisionAssuranceHistorySeriesReleaseRegistry(**body)


def verify_decision_assurance_history_series_release_registry(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
) -> DecisionAssuranceHistorySeriesReleaseRegistry:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistry):
        raise ValidationError("release registry verification requires a typed registry")
    value._validate()
    if address_decision_assurance_history_series_release_registry(value) != value.content_address:
        raise ValidationError("release registry address mismatch")
    return value


def decision_assurance_history_series_release_registry_entry_from_mapping(
    value: Mapping[str, Any],
) -> DecisionAssuranceHistorySeriesReleaseRegistryEntry:
    body = dict(_mapping(value, "release registry entry"))
    _strict(
        body,
        {
            "ordinal",
            "package_id",
            "release_id",
            "package_address",
            "release_address",
            "state",
            "accepted",
            "release_ready",
            "content_address",
        },
        "release registry entry",
    )
    return DecisionAssuranceHistorySeriesReleaseRegistryEntry(**body)


def decision_assurance_history_series_release_registry_from_mapping(
    value: Mapping[str, Any],
) -> DecisionAssuranceHistorySeriesReleaseRegistry:
    body = dict(_mapping(value, "release registry"))
    _strict(
        body,
        {
            "registry_id",
            "version",
            "boundary",
            "entry_count",
            "ready_count",
            "hold_count",
            "blocked_count",
            "accepted_count",
            "release_ready_count",
            "entries",
            "content_address",
        },
        "release registry",
    )
    body["entries"] = tuple(
        decision_assurance_history_series_release_registry_entry_from_mapping(item)
        for item in _mapping_sequence(body["entries"], "release registry entries")
    )
    return verify_decision_assurance_history_series_release_registry(
        DecisionAssuranceHistorySeriesReleaseRegistry(**body)
    )


class ReleaseRegistryQuery:
    RESOURCES = (
        "summary",
        "entries",
        "ready",
        "hold",
        "blocked",
        "accepted",
        "release-ready",
        "rejected",
    )

    def __init__(
        self, resource: str = "summary", offset: int = 0, limit: int = 50, text: str | None = None
    ) -> None:
        self.resource = _text(resource, "registry query resource", 32)
        if self.resource not in self.RESOURCES:
            raise ValidationError("registry query resource is invalid")
        self.offset, self.limit = (
            _count(offset, "registry query offset"),
            _count(limit, "registry query limit"),
        )
        if self.limit < 1:
            raise ValidationError("registry query limit must be positive")
        self.text = None if text is None else _text(text, "registry query text", 256)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "offset": self.offset,
            "limit": self.limit,
            "text": self.text,
        }


class ReleaseRegistryQueryResult:
    def __init__(
        self,
        registry_address: str,
        query: ReleaseRegistryQuery,
        total_count: int,
        returned_count: int,
        items: Sequence[Mapping[str, Any]],
        content_address: str,
    ) -> None:
        self.registry_address, self.query = registry_address, query
        self.total_count, self.returned_count, self.items = (
            total_count,
            returned_count,
            tuple(dict(item) for item in items),
        )
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.registry_address, "registry query registry address")
        if not isinstance(self.query, ReleaseRegistryQuery):
            raise ValidationError("registry query must be typed")
        _count(self.total_count, "registry query total count")
        _count(self.returned_count, "registry query returned count")
        if (
            self.returned_count != len(self.items)
            or self.returned_count > self.total_count
            or self.returned_count > self.query.limit
        ):
            raise ValidationError("registry query counts are invalid")
        _address(self.content_address, "registry query address")
        if (
            not self.content_address.startswith("pending:")
            and address_decision_assurance_history_series_release_registry_query(self)
            != self.content_address
        ):
            raise ValidationError("registry query address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("registry query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_address": self.registry_address,
            "query": self.query.to_dict(),
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "items": list(self.items),
            "content_address": self.content_address,
        }


def address_decision_assurance_history_series_release_registry_query(
    value: ReleaseRegistryQueryResult,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None}, prefix=REGISTRY_PREFIX + "-query"
    )


def query_decision_assurance_history_series_release_registry(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
    query: ReleaseRegistryQuery | None = None,
    **kwargs: Any,
) -> ReleaseRegistryQueryResult:
    verify_decision_assurance_history_series_release_registry(value)
    if query is not None and kwargs:
        raise ValidationError("registry query cannot combine typed query and keyword filters")
    selected = query or ReleaseRegistryQuery(**kwargs)
    rows = (
        [value.summary()]
        if selected.resource == "summary"
        else [entry.to_dict() for entry in value.entries]
    )
    if selected.resource in {"ready", "hold", "blocked"}:
        rows = [row for row in rows if row["state"] == selected.resource]
    elif selected.resource == "accepted":
        rows = [row for row in rows if row["accepted"]]
    elif selected.resource == "release-ready":
        rows = [row for row in rows if row["release_ready"]]
    elif selected.resource == "rejected":
        rows = [row for row in rows if not row["accepted"]]
    if selected.text:
        needle = selected.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    total, page = len(rows), rows[selected.offset : selected.offset + selected.limit]
    body = {
        "registry_address": value.content_address,
        "query": selected,
        "total_count": total,
        "returned_count": len(page),
        "items": page,
        "content_address": "pending:registry-query",
    }
    provisional = ReleaseRegistryQueryResult(**body)
    body["content_address"] = address_decision_assurance_history_series_release_registry_query(
        provisional
    )
    return ReleaseRegistryQueryResult(**body)


def decision_assurance_history_series_release_registry_json(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
) -> str:
    verify_decision_assurance_history_series_release_registry(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_series_release_registry_query_json(
    value: ReleaseRegistryQueryResult,
) -> str:
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream, fieldnames=tuple(fields), extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def decision_assurance_history_series_release_registry_csv(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
) -> str:
    verify_decision_assurance_history_series_release_registry(value)
    return _csv_text(
        [entry.to_dict() for entry in value.entries],
        (
            "ordinal",
            "package_id",
            "release_id",
            "package_address",
            "release_address",
            "state",
            "accepted",
            "release_ready",
            "content_address",
        ),
    )


def decision_assurance_history_series_release_registry_query_csv(
    value: ReleaseRegistryQueryResult,
) -> str:
    return _csv_text(
        value.items,
        (
            "ordinal",
            "package_id",
            "release_id",
            "package_address",
            "release_address",
            "state",
            "accepted",
            "release_ready",
            "content_address",
        ),
    )


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""] + [
        f"- **{key}:** {json.dumps(value, ensure_ascii=False, sort_keys=True)}"
        for key, value in summary.items()
    ]
    if rows:
        fields = tuple(rows[0].keys())
        lines.extend(
            (
                "",
                "## Items",
                "",
                "| " + " | ".join(fields) + " |",
                "| " + " | ".join("---" for _ in fields) + " |",
            )
        )
        lines.extend(
            "| "
            + " | ".join(
                json.dumps(row.get(field), ensure_ascii=False, sort_keys=True) for field in fields
            )
            + " |"
            for row in rows
        )
    return "\n".join(lines) + "\n"


def render_decision_assurance_history_series_release_registry_markdown(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
) -> str:
    verify_decision_assurance_history_series_release_registry(value)
    return _markdown(
        "Decision Assurance History Series Release Registry",
        value.summary(),
        [entry.to_dict() for entry in value.entries],
    )


def render_decision_assurance_history_series_release_registry_query_markdown(
    value: ReleaseRegistryQueryResult,
) -> str:
    return _markdown(
        "Decision Assurance History Series Release Registry Query",
        {
            "registry_address": value.registry_address,
            "resource": value.query.resource,
            "total_count": value.total_count,
            "returned_count": value.returned_count,
        },
        value.items,
    )


def decision_assurance_history_series_release_registry_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistry",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "registry_id",
            "version",
            "boundary",
            "entry_count",
            "ready_count",
            "hold_count",
            "blocked_count",
            "accepted_count",
            "release_ready_count",
            "entries",
            "content_address",
        ],
        "properties": {
            "registry_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "hold_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "blocked_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "accepted_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "release_ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "entries": {
                "type": "array",
                "maxItems": MAX_ENTRIES,
                "items": {"$ref": "#/$defs/entry"},
            },
            "content_address": {"type": "string"},
        },
        "$defs": {"entry": decision_assurance_history_series_release_registry_entry_schema()},
    }


def decision_assurance_history_series_release_registry_entry_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryEntry",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ordinal",
            "package_id",
            "release_id",
            "package_address",
            "release_address",
            "state",
            "accepted",
            "release_ready",
            "content_address",
        ],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES - 1},
            "package_id": {"type": "string"},
            "release_id": {"type": "string"},
            "package_address": {"type": "string"},
            "release_address": {"type": "string"},
            "state": {"enum": ["ready", "hold", "blocked"]},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "content_address": {"type": "string"},
        },
    }


def decision_assurance_history_series_release_registry_query_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ReleaseRegistryQuery",
        "type": "object",
        "additionalProperties": False,
        "required": ["resource", "offset", "limit", "text"],
        "properties": {
            "resource": {"enum": list(ReleaseRegistryQuery.RESOURCES)},
            "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS},
            "text": {"type": ["string", "null"]},
        },
    }


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "admission": {
            "requires_verified_release_package": True,
            "sort": "package_id,release_id,package_address",
            "unique": ["package_id", "release_id", "entry_address"],
        },
        "states": ["ready", "hold", "blocked"],
        "package": {
            "files": list(FILES),
            "manifest": MANIFEST_NAME,
            "entries": ENTRIES_NAME,
            "registry": REGISTRY_NAME,
        },
        "diff": {
            "files": list(DIFF_FILES),
            "keys": ["package:<package_id>"],
            "actions": ["added", "removed", "unchanged", "changed"],
            "directions": ["unchanged", "improved", "regressed", "changed"],
        },
        "queries": {
            "resources": list(ReleaseRegistryQuery.RESOURCES),
            "max_limit": MAX_QUERY_ITEMS,
        },
        "public_boundary": {"forbidden_keys": sorted(_FORBIDDEN_KEYS), "source_paths": False},
    }


def _file_address(name: str, raw: bytes, *, prefix: str = REGISTRY_PREFIX + "-file") -> str:
    return content_hash({"name": name, "byte_address": hash_bytes(raw)}, prefix=prefix)


def _manifest_artifacts(
    raws: Mapping[str, bytes], *, prefix: str = REGISTRY_PREFIX + "-file"
) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "bytes": len(raw),
            "byte_address": hash_bytes(raw),
            "file_address": _file_address(name, raw, prefix=prefix),
        }
        for name, raw in raws.items()
    ]


def _manifest_address(value: Mapping[str, Any], *, prefix: str = MANIFEST_PREFIX) -> str:
    return content_hash(dict(value) | {"manifest_address": None}, prefix=prefix)


def write_decision_assurance_history_series_release_registry(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
    directory: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    verify_decision_assurance_history_series_release_registry(value)
    destination = Path(directory)
    if (
        destination.exists()
        and (not destination.is_dir() or any(destination.iterdir()))
        and not overwrite
    ):
        raise ValidationError("release registry destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    registry_raw, entries_raw = (
        canonical_bytes(value.to_dict()),
        canonical_bytes({"entries": [entry.to_dict() for entry in value.entries]}),
    )
    manifest = {
        "version": VERSION,
        "boundary": BOUNDARY,
        "registry_id": value.registry_id,
        "registry_address": value.content_address,
        "artifact_count": 2,
        "files": list(FILES),
        "artifacts": _manifest_artifacts({ENTRIES_NAME: entries_raw, REGISTRY_NAME: registry_raw}),
        "manifest_address": None,
    }
    manifest["manifest_address"] = _manifest_address(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=".glio-release-registry-", dir=str(destination.parent)))
    try:
        (temporary / ENTRIES_NAME).write_bytes(entries_raw)
        (temporary / REGISTRY_NAME).write_bytes(registry_raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("release registry destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("release registry destination already exists")
                shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is invalid JSON") from exc
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return dict(_mapping(value, field))


def _check_artifact(
    manifest: Mapping[str, Any], source: Path, name: str, *, prefix: str = REGISTRY_PREFIX + "-file"
) -> bytes:
    artifact = next(
        (
            item
            for item in _mapping_sequence(manifest.get("artifacts"), "registry artifacts")
            if item.get("name") == name
        ),
        None,
    )
    if artifact is None:
        raise ValidationError(f"release registry manifest is missing {name}")
    path = source / name
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"release registry artifact {name} must be a regular file")
    raw = path.read_bytes()
    if (
        artifact.get("bytes") != len(raw)
        or artifact.get("byte_address") != hash_bytes(raw)
        or artifact.get("file_address") != _file_address(name, raw, prefix=prefix)
    ):
        raise ValidationError(f"release registry artifact {name} address mismatch")
    return raw


def load_decision_assurance_history_series_release_registry(
    directory: str | Path,
) -> DecisionAssuranceHistorySeriesReleaseRegistry:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("release registry input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(
        FILES
    ):
        raise ValidationError("release registry file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "release registry manifest")
    _strict(
        manifest,
        {
            "version",
            "boundary",
            "registry_id",
            "registry_address",
            "artifact_count",
            "files",
            "artifacts",
            "manifest_address",
        },
        "release registry manifest",
    )
    if (
        manifest["version"] != VERSION
        or manifest["boundary"] != BOUNDARY
        or manifest["artifact_count"] != 2
        or tuple(manifest["files"]) != FILES
    ):
        raise ValidationError("release registry manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("release registry manifest address mismatch")
    entries_document = json.loads(_check_artifact(manifest, source, ENTRIES_NAME).decode("utf-8"))
    registry_document = json.loads(_check_artifact(manifest, source, REGISTRY_NAME).decode("utf-8"))
    if list(
        _mapping_sequence(entries_document.get("entries"), "release registry entries document")
    ) != list(_mapping_sequence(registry_document.get("entries"), "release registry entries")):
        raise ValidationError("release registry entry projection differs from registry document")
    value = decision_assurance_history_series_release_registry_from_mapping(registry_document)
    if (
        manifest["registry_id"] != value.registry_id
        or manifest["registry_address"] != value.content_address
    ):
        raise ValidationError("release registry manifest linkage is invalid")
    return verify_decision_assurance_history_series_release_registry(value)


def verify_decision_assurance_history_series_release_registry_directory(
    directory: str | Path,
) -> DecisionAssuranceHistorySeriesReleaseRegistry:
    return load_decision_assurance_history_series_release_registry(directory)


class DecisionAssuranceHistorySeriesReleaseRegistryDiffItem:
    def __init__(
        self,
        ordinal: int,
        key: str,
        action: str,
        direction: str,
        baseline_value: Mapping[str, Any] | None,
        candidate_value: Mapping[str, Any] | None,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal, self.key, self.action, self.direction = ordinal, key, action, direction
        self.baseline_value, self.candidate_value = (
            None if baseline_value is None else dict(baseline_value),
            None if candidate_value is None else dict(candidate_value),
        )
        self.detail, self.content_address = detail, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "registry diff item ordinal", MAX_ENTRIES * 2 - 1)
        _text(self.key, "registry diff item key", 512)
        _action(self.action)
        _direction(self.direction)
        if self.action == "added" and (
            self.baseline_value is not None or self.candidate_value is None
        ):
            raise ValidationError("added registry diff item values are invalid")
        if self.action == "removed" and (
            self.baseline_value is None or self.candidate_value is not None
        ):
            raise ValidationError("removed registry diff item values are invalid")
        if self.action in {"unchanged", "changed"} and (
            self.baseline_value is None or self.candidate_value is None
        ):
            raise ValidationError("joined registry diff item values are invalid")
        _text(self.detail, "registry diff item detail", 1024)
        _address(self.content_address, "registry diff item address")
        if (
            not self.content_address.startswith("pending:")
            and address_decision_assurance_history_series_release_registry_diff_item(self)
            != self.content_address
        ):
            raise ValidationError("registry diff item address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("registry diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "key": self.key,
            "action": self.action,
            "direction": self.direction,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_decision_assurance_history_series_release_registry_diff_item(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiffItem,
) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


def _registry_entry_records(
    value: DecisionAssuranceHistorySeriesReleaseRegistry,
) -> dict[str, Mapping[str, Any]]:
    return {f"package:{entry.package_id}": entry.to_dict() for entry in value.entries}


def _entry_direction(
    action: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None
) -> str:
    if action == "unchanged":
        return "unchanged"
    if action == "added":
        return "improved" if candidate and candidate.get("release_ready") else "changed"
    if action == "removed":
        return "regressed" if baseline and baseline.get("release_ready") else "changed"
    left, right = (
        bool(baseline and baseline.get("release_ready")),
        bool(candidate and candidate.get("release_ready")),
    )
    return (
        "changed"
        if left == right and baseline != candidate
        else "unchanged"
        if left == right
        else "improved"
        if right
        else "regressed"
    )


class DecisionAssuranceHistorySeriesReleaseRegistryDiff:
    def __init__(
        self,
        diff_id: str,
        version: str,
        boundary: str,
        baseline_address: str,
        candidate_address: str,
        item_count: int,
        added_count: int,
        removed_count: int,
        unchanged_count: int,
        changed_count: int,
        improved_count: int,
        regressed_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        items: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryDiffItem],
        content_address: str,
    ) -> None:
        self.diff_id, self.version, self.boundary = diff_id, version, boundary
        self.baseline_address, self.candidate_address = baseline_address, candidate_address
        (
            self.item_count,
            self.added_count,
            self.removed_count,
            self.unchanged_count,
            self.changed_count,
        ) = item_count, added_count, removed_count, unchanged_count, changed_count
        self.improved_count, self.regressed_count, self.state = (
            improved_count,
            regressed_count,
            state,
        )
        self.accepted, self.release_ready = accepted, release_ready
        self.items, self.content_address = tuple(items), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "registry diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release registry diff contract is invalid")
        _address(self.baseline_address, "registry diff baseline address")
        _address(self.candidate_address, "registry diff candidate address")
        _count(self.item_count, "registry diff item count", MAX_ENTRIES * 2)
        for name, value in (
            ("added", self.added_count),
            ("removed", self.removed_count),
            ("unchanged", self.unchanged_count),
            ("changed", self.changed_count),
            ("improved", self.improved_count),
            ("regressed", self.regressed_count),
        ):
            _count(value, f"registry diff {name} count", MAX_ENTRIES * 2)
        if (
            self.item_count != len(self.items)
            or self.added_count + self.removed_count + self.unchanged_count + self.changed_count
            != self.item_count
        ):
            raise ValidationError("registry diff action counts are not conserved")
        if self.improved_count + self.regressed_count > self.item_count:
            raise ValidationError("registry diff direction counts are not conserved")
        for ordinal, item in enumerate(self.items):
            if (
                not isinstance(item, DecisionAssuranceHistorySeriesReleaseRegistryDiffItem)
                or item.ordinal != ordinal
            ):
                raise ValidationError("registry diff items must have contiguous ordinals")
            if (
                address_decision_assurance_history_series_release_registry_diff_item(item)
                != item.content_address
            ):
                raise ValidationError("registry diff item address mismatch")
        _direction(self.state, "registry diff state")
        _bool(self.accepted, "registry diff accepted")
        _bool(self.release_ready, "registry diff release-ready")
        if not self.accepted or self.release_ready != (self.regressed_count == 0):
            raise ValidationError("registry diff readiness is invalid")
        _address(self.content_address, "registry diff address")
        if (
            not self.content_address.startswith("pending:")
            and address_decision_assurance_history_series_release_registry_diff(self)
            != self.content_address
        ):
            raise ValidationError("registry diff address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("registry diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "item_count": self.item_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"items": [item.to_dict() for item in self.items]}


def address_decision_assurance_history_series_release_registry_diff(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=DIFF_PREFIX)


def _diff_item(
    ordinal: int,
    key: str,
    action: str,
    baseline: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiffItem:
    body = {
        "ordinal": ordinal,
        "key": key,
        "action": action,
        "direction": _entry_direction(action, baseline, candidate),
        "baseline_value": baseline,
        "candidate_value": candidate,
        "detail": {
            "added": "package entered the registry",
            "removed": "package left the registry",
            "unchanged": "package admission is identical",
            "changed": "package admission changed",
        }[action],
        "content_address": "pending:registry-diff-item",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryDiffItem(**body)
    body["content_address"] = address_decision_assurance_history_series_release_registry_diff_item(
        provisional
    )
    return DecisionAssuranceHistorySeriesReleaseRegistryDiffItem(**body)


def build_decision_assurance_history_series_release_registry_diff(
    baseline: DecisionAssuranceHistorySeriesReleaseRegistry,
    candidate: DecisionAssuranceHistorySeriesReleaseRegistry,
    *,
    diff_id: str = DEFAULT_DIFF_ID,
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiff:
    verify_decision_assurance_history_series_release_registry(baseline)
    verify_decision_assurance_history_series_release_registry(candidate)
    left, right = _registry_entry_records(baseline), _registry_entry_records(candidate)
    items = []
    for ordinal, key in enumerate(sorted(set(left) | set(right))):
        action = (
            "added"
            if key not in left
            else "removed"
            if key not in right
            else "unchanged"
            if left[key] == right[key]
            else "changed"
        )
        items.append(_diff_item(ordinal, key, action, left.get(key), right.get(key)))
    items = tuple(items)
    improved, regressed, changed = (
        sum(item.direction == "improved" for item in items),
        sum(item.direction == "regressed" for item in items),
        sum(item.direction == "changed" for item in items),
    )
    state = (
        "regressed"
        if regressed
        else "improved"
        if improved
        else "changed"
        if changed
        else "unchanged"
    )
    body = {
        "diff_id": diff_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "baseline_address": baseline.content_address,
        "candidate_address": candidate.content_address,
        "item_count": len(items),
        "added_count": sum(item.action == "added" for item in items),
        "removed_count": sum(item.action == "removed" for item in items),
        "unchanged_count": sum(item.action == "unchanged" for item in items),
        "changed_count": sum(item.action == "changed" for item in items),
        "improved_count": improved,
        "regressed_count": regressed,
        "state": state,
        "accepted": True,
        "release_ready": regressed == 0,
        "items": items,
        "content_address": "pending:registry-diff",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryDiff(**body)
    body["content_address"] = address_decision_assurance_history_series_release_registry_diff(
        provisional
    )
    return DecisionAssuranceHistorySeriesReleaseRegistryDiff(**body)


def verify_decision_assurance_history_series_release_registry_diff(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiff:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryDiff):
        raise ValidationError("release registry diff verification requires a typed diff")
    value._validate()
    if (
        address_decision_assurance_history_series_release_registry_diff(value)
        != value.content_address
    ):
        raise ValidationError("release registry diff address mismatch")
    return value


def decision_assurance_history_series_release_registry_diff_item_from_mapping(
    value: Mapping[str, Any],
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiffItem:
    body = dict(_mapping(value, "release registry diff item"))
    _strict(
        body,
        {
            "ordinal",
            "key",
            "action",
            "direction",
            "baseline_value",
            "candidate_value",
            "detail",
            "content_address",
        },
        "release registry diff item",
    )
    return DecisionAssuranceHistorySeriesReleaseRegistryDiffItem(**body)


def decision_assurance_history_series_release_registry_diff_from_mapping(
    value: Mapping[str, Any],
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiff:
    body = dict(_mapping(value, "release registry diff"))
    _strict(
        body,
        {
            "diff_id",
            "version",
            "boundary",
            "baseline_address",
            "candidate_address",
            "item_count",
            "added_count",
            "removed_count",
            "unchanged_count",
            "changed_count",
            "improved_count",
            "regressed_count",
            "state",
            "accepted",
            "release_ready",
            "items",
            "content_address",
        },
        "release registry diff",
    )
    body["items"] = tuple(
        decision_assurance_history_series_release_registry_diff_item_from_mapping(item)
        for item in _mapping_sequence(body["items"], "release registry diff items")
    )
    return verify_decision_assurance_history_series_release_registry_diff(
        DecisionAssuranceHistorySeriesReleaseRegistryDiff(**body)
    )


class ReleaseRegistryDiffQuery:
    RESOURCES = (
        "summary",
        "items",
        "added",
        "removed",
        "unchanged",
        "changed",
        "improved",
        "regressed",
    )

    def __init__(
        self, resource: str = "summary", offset: int = 0, limit: int = 50, text: str | None = None
    ) -> None:
        self.resource = _text(resource, "registry diff query resource", 32)
        if self.resource not in self.RESOURCES:
            raise ValidationError("registry diff query resource is invalid")
        self.offset, self.limit = (
            _count(offset, "registry diff query offset"),
            _count(limit, "registry diff query limit"),
        )
        if self.limit < 1:
            raise ValidationError("registry diff query limit must be positive")
        self.text = None if text is None else _text(text, "registry diff query text", 256)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "offset": self.offset,
            "limit": self.limit,
            "text": self.text,
        }


class ReleaseRegistryDiffQueryResult:
    def __init__(
        self,
        diff_address: str,
        query: ReleaseRegistryDiffQuery,
        total_count: int,
        returned_count: int,
        items: Sequence[Mapping[str, Any]],
        content_address: str,
    ) -> None:
        (
            self.diff_address,
            self.query,
            self.total_count,
            self.returned_count,
            self.items,
            self.content_address,
        ) = (
            diff_address,
            query,
            total_count,
            returned_count,
            tuple(dict(item) for item in items),
            content_address,
        )
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "registry diff query diff address")
        if not isinstance(self.query, ReleaseRegistryDiffQuery):
            raise ValidationError("registry diff query must be typed")
        _count(self.total_count, "registry diff query total count", MAX_ENTRIES * 2)
        _count(self.returned_count, "registry diff query returned count", MAX_ENTRIES * 2)
        if (
            self.returned_count != len(self.items)
            or self.returned_count > self.total_count
            or self.returned_count > self.query.limit
        ):
            raise ValidationError("registry diff query counts are invalid")
        _address(self.content_address, "registry diff query address")
        if (
            not self.content_address.startswith("pending:")
            and address_decision_assurance_history_series_release_registry_diff_query(self)
            != self.content_address
        ):
            raise ValidationError("registry diff query address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("registry diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_address": self.diff_address,
            "query": self.query.to_dict(),
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "items": list(self.items),
            "content_address": self.content_address,
        }


def address_decision_assurance_history_series_release_registry_diff_query(
    value: ReleaseRegistryDiffQueryResult,
) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX + "-query")


def query_decision_assurance_history_series_release_registry_diff(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
    query: ReleaseRegistryDiffQuery | None = None,
    **kwargs: Any,
) -> ReleaseRegistryDiffQueryResult:
    verify_decision_assurance_history_series_release_registry_diff(value)
    if query is not None and kwargs:
        raise ValidationError("registry diff query cannot combine typed query and keyword filters")
    selected = query or ReleaseRegistryDiffQuery(**kwargs)
    rows = (
        [value.summary()]
        if selected.resource == "summary"
        else [item.to_dict() for item in value.items]
    )
    if selected.resource not in {"summary", "items"}:
        rows = [
            row
            for row in rows
            if row["action"] == selected.resource or row["direction"] == selected.resource
        ]
    if selected.text:
        needle = selected.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    total, page = len(rows), rows[selected.offset : selected.offset + selected.limit]
    body = {
        "diff_address": value.content_address,
        "query": selected,
        "total_count": total,
        "returned_count": len(page),
        "items": page,
        "content_address": "pending:registry-diff-query",
    }
    provisional = ReleaseRegistryDiffQueryResult(**body)
    body["content_address"] = address_decision_assurance_history_series_release_registry_diff_query(
        provisional
    )
    return ReleaseRegistryDiffQueryResult(**body)


def decision_assurance_history_series_release_registry_diff_json(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
) -> str:
    verify_decision_assurance_history_series_release_registry_diff(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_series_release_registry_diff_csv(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
) -> str:
    verify_decision_assurance_history_series_release_registry_diff(value)
    return _csv_text(
        [item.to_dict() for item in value.items],
        ("ordinal", "key", "action", "direction", "detail", "content_address"),
    )


def decision_assurance_history_series_release_registry_diff_query_json(
    value: ReleaseRegistryDiffQueryResult,
) -> str:
    return canonical_json(value.to_dict())


def decision_assurance_history_series_release_registry_diff_query_csv(
    value: ReleaseRegistryDiffQueryResult,
) -> str:
    return _csv_text(
        value.items, ("ordinal", "key", "action", "direction", "detail", "content_address")
    )


def render_decision_assurance_history_series_release_registry_diff_markdown(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
) -> str:
    verify_decision_assurance_history_series_release_registry_diff(value)
    return _markdown(
        "Decision Assurance History Series Release Registry Diff",
        value.summary(),
        [item.to_dict() for item in value.items],
    )


def render_decision_assurance_history_series_release_registry_diff_query_markdown(
    value: ReleaseRegistryDiffQueryResult,
) -> str:
    return _markdown(
        "Decision Assurance History Series Release Registry Diff Query",
        {
            "diff_address": value.diff_address,
            "resource": value.query.resource,
            "total_count": value.total_count,
            "returned_count": value.returned_count,
        },
        value.items,
    )


def decision_assurance_history_series_release_registry_diff_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryDiff",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "diff_id",
            "version",
            "boundary",
            "baseline_address",
            "candidate_address",
            "item_count",
            "added_count",
            "removed_count",
            "unchanged_count",
            "changed_count",
            "improved_count",
            "regressed_count",
            "state",
            "accepted",
            "release_ready",
            "items",
            "content_address",
        ],
        "properties": {
            "diff_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "baseline_address": {"type": "string"},
            "candidate_address": {"type": "string"},
            "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "added_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "removed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "unchanged_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "changed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "improved_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "regressed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES * 2},
            "state": {"enum": ["unchanged", "improved", "regressed", "changed"]},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "items": {
                "type": "array",
                "maxItems": MAX_ENTRIES * 2,
                "items": {"$ref": "#/$defs/item"},
            },
            "content_address": {"type": "string"},
        },
        "$defs": {"item": decision_assurance_history_series_release_registry_diff_item_schema()},
    }


def decision_assurance_history_series_release_registry_diff_item_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryDiffItem",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ordinal",
            "key",
            "action",
            "direction",
            "baseline_value",
            "candidate_value",
            "detail",
            "content_address",
        ],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0},
            "key": {"type": "string"},
            "action": {"enum": ["added", "removed", "unchanged", "changed"]},
            "direction": {"enum": ["unchanged", "improved", "regressed", "changed"]},
            "baseline_value": {"type": ["object", "null"]},
            "candidate_value": {"type": ["object", "null"]},
            "detail": {"type": "string"},
            "content_address": {"type": "string"},
        },
    }


def decision_assurance_history_series_release_registry_diff_query_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ReleaseRegistryDiffQuery",
        "type": "object",
        "additionalProperties": False,
        "required": ["resource", "offset", "limit", "text"],
        "properties": {
            "resource": {"enum": list(ReleaseRegistryDiffQuery.RESOURCES)},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1},
            "text": {"type": ["string", "null"]},
        },
    }


def write_decision_assurance_history_series_release_registry_diff(
    value: DecisionAssuranceHistorySeriesReleaseRegistryDiff,
    directory: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    verify_decision_assurance_history_series_release_registry_diff(value)
    destination = Path(directory)
    if (
        destination.exists()
        and (not destination.is_dir() or any(destination.iterdir()))
        and not overwrite
    ):
        raise ValidationError("release registry diff destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    diff_raw = canonical_bytes(value.to_dict())
    manifest = {
        "version": VERSION,
        "boundary": BOUNDARY,
        "diff_id": value.diff_id,
        "baseline_address": value.baseline_address,
        "candidate_address": value.candidate_address,
        "diff_address": value.content_address,
        "artifact_count": 1,
        "files": list(DIFF_FILES),
        "artifacts": _manifest_artifacts({DIFF_NAME: diff_raw}, prefix=DIFF_PREFIX + "-file"),
        "manifest_address": None,
    }
    manifest["manifest_address"] = _manifest_address(manifest, prefix=DIFF_MANIFEST_PREFIX)
    temporary = Path(tempfile.mkdtemp(prefix=".glio-release-registry-diff-", dir=str(destination.parent)))
    try:
        (temporary / DIFF_NAME).write_bytes(diff_raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("release registry diff destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("release registry diff destination already exists")
                shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_decision_assurance_history_series_release_registry_diff(
    directory: str | Path,
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiff:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("release registry diff input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(
        DIFF_FILES
    ):
        raise ValidationError("release registry diff file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "release registry diff manifest")
    _strict(
        manifest,
        {
            "version",
            "boundary",
            "diff_id",
            "baseline_address",
            "candidate_address",
            "diff_address",
            "artifact_count",
            "files",
            "artifacts",
            "manifest_address",
        },
        "release registry diff manifest",
    )
    if (
        manifest["version"] != VERSION
        or manifest["boundary"] != BOUNDARY
        or manifest["artifact_count"] != 1
        or tuple(manifest["files"]) != DIFF_FILES
    ):
        raise ValidationError("release registry diff manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address(
        {**manifest, "manifest_address": None}, prefix=DIFF_MANIFEST_PREFIX
    ):
        raise ValidationError("release registry diff manifest address mismatch")
    value = decision_assurance_history_series_release_registry_diff_from_mapping(
        json.loads(
            _check_artifact(manifest, source, DIFF_NAME, prefix=DIFF_PREFIX + "-file").decode(
                "utf-8"
            )
        )
    )
    if (
        manifest["diff_id"] != value.diff_id
        or manifest["baseline_address"] != value.baseline_address
        or manifest["candidate_address"] != value.candidate_address
        or manifest["diff_address"] != value.content_address
    ):
        raise ValidationError("release registry diff manifest linkage is invalid")
    return verify_decision_assurance_history_series_release_registry_diff(value)


def verify_decision_assurance_history_series_release_registry_diff_directory(
    directory: str | Path,
) -> DecisionAssuranceHistorySeriesReleaseRegistryDiff:
    return load_decision_assurance_history_series_release_registry_diff(directory)


__all__ = [
    "BOUNDARY",
    "DEFAULT_DIFF_ID",
    "DEFAULT_REGISTRY_ID",
    "DIFF_FILES",
    "DIFF_NAME",
    "ENTRIES_NAME",
    "FILES",
    "MANIFEST_NAME",
    "MAX_ENTRIES",
    "MAX_QUERY_ITEMS",
    "REGISTRY_NAME",
    "REGISTRY_PREFIX",
    "VERSION",
    "DecisionAssuranceHistorySeriesReleaseRegistry",
    "DecisionAssuranceHistorySeriesReleaseRegistryDiff",
    "DecisionAssuranceHistorySeriesReleaseRegistryDiffItem",
    "DecisionAssuranceHistorySeriesReleaseRegistryEntry",
    "ReleaseRegistryDiffQuery",
    "ReleaseRegistryDiffQueryResult",
    "ReleaseRegistryQuery",
    "ReleaseRegistryQueryResult",
    "address_decision_assurance_history_series_release_registry",
    "address_decision_assurance_history_series_release_registry_diff",
    "address_decision_assurance_history_series_release_registry_diff_item",
    "address_decision_assurance_history_series_release_registry_diff_query",
    "address_decision_assurance_history_series_release_registry_entry",
    "address_decision_assurance_history_series_release_registry_query",
    "build_decision_assurance_history_series_release_registry",
    "build_decision_assurance_history_series_release_registry_diff",
    "capabilities",
    "decision_assurance_history_series_release_registry_csv",
    "decision_assurance_history_series_release_registry_diff_csv",
    "decision_assurance_history_series_release_registry_diff_from_mapping",
    "decision_assurance_history_series_release_registry_diff_item_from_mapping",
    "decision_assurance_history_series_release_registry_diff_item_schema",
    "decision_assurance_history_series_release_registry_diff_json",
    "decision_assurance_history_series_release_registry_diff_query_csv",
    "decision_assurance_history_series_release_registry_diff_query_json",
    "decision_assurance_history_series_release_registry_diff_query_schema",
    "decision_assurance_history_series_release_registry_diff_schema",
    "decision_assurance_history_series_release_registry_entry_from_mapping",
    "decision_assurance_history_series_release_registry_entry_schema",
    "decision_assurance_history_series_release_registry_from_mapping",
    "decision_assurance_history_series_release_registry_json",
    "decision_assurance_history_series_release_registry_query_csv",
    "decision_assurance_history_series_release_registry_query_json",
    "decision_assurance_history_series_release_registry_query_schema",
    "decision_assurance_history_series_release_registry_schema",
    "load_decision_assurance_history_series_release_registry",
    "load_decision_assurance_history_series_release_registry_diff",
    "query_decision_assurance_history_series_release_registry",
    "query_decision_assurance_history_series_release_registry_diff",
    "render_decision_assurance_history_series_release_registry_diff_markdown",
    "render_decision_assurance_history_series_release_registry_diff_query_markdown",
    "render_decision_assurance_history_series_release_registry_markdown",
    "render_decision_assurance_history_series_release_registry_query_markdown",
    "verify_decision_assurance_history_series_release_registry",
    "verify_decision_assurance_history_series_release_registry_diff",
    "verify_decision_assurance_history_series_release_registry_diff_directory",
    "verify_decision_assurance_history_series_release_registry_directory",
    "write_decision_assurance_history_series_release_registry",
    "write_decision_assurance_history_series_release_registry_diff",
]
