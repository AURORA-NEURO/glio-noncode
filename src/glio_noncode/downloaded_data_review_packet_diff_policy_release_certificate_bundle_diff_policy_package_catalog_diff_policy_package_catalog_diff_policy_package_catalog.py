"""Build and query bounded catalogs of packet-catalog diff policy packages."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package as package_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_contracts import (
    BOUNDARY, CATALOG_FIELDS, CATALOG_PREFIX, ENTRY_FIELDS, ENTRY_PREFIX, MAX_ENTRIES, MAX_PACKAGE_BYTES, MAX_TOTAL_PACKAGE_BYTES, VERSION,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog as Catalog,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry as Entry,
    address_catalog, address_entry, capabilities, catalog_schema, entry_schema,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

MAX_LIMIT = MAX_ENTRIES
DEFAULT_CATALOG_ID = CATALOG_PREFIX
DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog = Catalog
DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry = Entry


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if not value or value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _sequence(value: Any, field: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence) or len(value) > MAX_ENTRIES:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _entry_from_mapping(value: Mapping[str, Any]) -> Entry:
    if not isinstance(value, Mapping):
        raise ValidationError("packet-catalog policy package catalog entry must be an object")
    _strict(value, set(ENTRY_FIELDS), "packet-catalog policy package catalog entry")
    return Entry(*(value[field] for field in ENTRY_FIELDS))


def _catalog_from_mapping(value: Mapping[str, Any]) -> Catalog:
    if not isinstance(value, Mapping):
        raise ValidationError("packet-catalog policy package catalog must be an object")
    _strict(value, set(CATALOG_FIELDS), "packet-catalog policy package catalog")
    return Catalog(value["catalog_id"], value["version"], value["boundary"], value["entry_count"], value["accepted_count"], value["ready_count"], value["blocked_count"], value["total_package_bytes"], tuple(_entry_from_mapping(item) for item in value["entries"]), value["content_address"])


def _addressed_entry(ordinal: int, entry_id: str, package: Any) -> Entry:
    manifest = package.manifest
    body = {"ordinal": ordinal, "entry_id": entry_id, "package_id": manifest.package_id, "package_address": package.package_address, "diff_address": manifest.diff_address, "policy_address": manifest.policy_address, "audit_address": manifest.audit_address, "policy_state": manifest.policy_state, "policy_accepted": manifest.policy_accepted, "audit_accepted": manifest.audit_accepted, "member_count": len(manifest.members), "package_byte_count": len(package.package_bytes), "content_address": ENTRY_PREFIX + ":pending"}
    provisional = Entry(**body)
    return Entry(**(body | {"content_address": address_entry(provisional)}))


def build_catalog(packages: Sequence[Any], *, entry_ids: Sequence[str] | None = None, catalog_id: str = DEFAULT_CATALOG_ID) -> Catalog:
    sources = _sequence(packages, "packet-catalog policy package catalog packages")
    if entry_ids is not None and len(entry_ids) != len(sources):
        raise ValidationError("packet-catalog policy package catalog entry ID count must match package count")
    loaded: list[tuple[str, Any]] = []
    for index, source in enumerate(sources):
        package = package_model.verify_package(source)
        entry_id = _label(entry_ids[index] if entry_ids is not None else package.manifest.package_id, "packet-catalog policy package catalog entry ID")
        loaded.append((entry_id, package))
    if len({entry_id for entry_id, _package in loaded}) != len(loaded) or len({package.manifest.package_id for _entry_id, package in loaded}) != len(loaded) or len({package.package_address for _entry_id, package in loaded}) != len(loaded):
        raise ValidationError("packet-catalog policy package catalog IDs, entry IDs, and addresses must be unique")
    loaded.sort(key=lambda item: (item[0], item[1].package_address))
    entries = tuple(_addressed_entry(index, entry_id, package) for index, (entry_id, package) in enumerate(loaded, start=1))
    total_bytes = sum(item.package_byte_count for item in entries)
    if total_bytes > MAX_TOTAL_PACKAGE_BYTES:
        raise ValidationError("packet-catalog policy package catalog byte total exceeds its bound")
    body = {"catalog_id": catalog_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.policy_accepted and item.audit_accepted for item in entries), "ready_count": sum(item.policy_state == "ready" for item in entries), "blocked_count": sum(item.policy_state == "blocked" for item in entries), "total_package_bytes": total_bytes, "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


def verify_catalog(value: Any) -> Catalog:
    if isinstance(value, (str, Path, bytes, bytearray)):
        return load_catalog(value)
    catalog = _catalog_from_mapping(value) if isinstance(value, Mapping) else value
    if not isinstance(catalog, Catalog):
        raise ValidationError("packet-catalog policy package catalog verification requires a typed catalog or mapping")
    if tuple((item.entry_id, item.package_address) for item in catalog.entries) != tuple(sorted((item.entry_id, item.package_address) for item in catalog.entries)):
        raise ValidationError("packet-catalog policy package catalog entries are not canonically sorted")
    if _has_forbidden_key(catalog.to_dict()) or address_catalog(catalog) != catalog.content_address:
        raise ValidationError("packet-catalog policy package catalog address or public boundary verification failed")
    if any(address_entry(item) != item.content_address for item in catalog.entries):
        raise ValidationError("packet-catalog policy package catalog entry address verification failed")
    return catalog


def catalog_from_mapping(value: Mapping[str, Any]) -> Catalog:
    return verify_catalog(value)


def load_catalog(value: str | Path | bytes | bytearray | Mapping[str, Any] | Catalog) -> Catalog:
    if isinstance(value, Catalog):
        return verify_catalog(value)
    if isinstance(value, Mapping):
        return catalog_from_mapping(value)
    raw = _strict_json_loads(bytes(value).decode("utf-8") if isinstance(value, (bytes, bytearray)) else read_text(value, field="packet-catalog policy package catalog", max_bytes=16 * 1024 * 1024))
    return catalog_from_mapping(raw)


def catalog_json(value: Any) -> str:
    return canonical_json(verify_catalog(value).to_dict()) + "\n"


def write_catalog(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Catalog:
    catalog = verify_catalog(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-catalog policy package catalog destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-catalog policy package catalog destination is not a file")
    _validate_parent(path.parent, "packet-catalog policy package catalog destination")
    atomic_write_text(path, catalog_json(catalog), field="packet-catalog policy package catalog destination")
    return catalog


def query_catalog(value: Any, *, resource: str = "summary", state: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    if resource not in {"summary", "entries", "accepted", "ready", "blocked", "lineage"} or state not in {"", "ready", "blocked"} or not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("packet-catalog policy package catalog query bounds are invalid")
    catalog = verify_catalog(value)
    if resource == "summary":
        result: dict[str, Any] = {"resource": resource, "value": catalog.summary()}
    else:
        items = catalog.entries
        if resource == "accepted":
            items = tuple(item for item in items if item.policy_accepted and item.audit_accepted)
        elif resource == "ready":
            items = tuple(item for item in items if item.policy_state == "ready")
        elif resource == "blocked":
            items = tuple(item for item in items if item.policy_state == "blocked")
        if state:
            items = tuple(item for item in items if item.policy_state == state)
        if text:
            needle = text.casefold()
            items = tuple(item for item in items if needle in " ".join((item.entry_id, item.package_id, item.package_address, item.diff_address, item.policy_address, item.audit_address, item.policy_state)).casefold())
        selected = items[offset:offset + limit]
        selected_values = tuple({"entry_id": item.entry_id, "package_id": item.package_id, "package_address": item.package_address, "diff_address": item.diff_address, "policy_address": item.policy_address, "audit_address": item.audit_address} if resource == "lineage" else item.to_dict() for item in selected)
        result = {"resource": resource, "state": state, "text": text, "offset": offset, "limit": limit, "total": len(catalog.entries), "matched": len(items), "returned": len(selected_values), "truncated": offset + len(selected_values) < len(items), "items": selected_values}
    return result | {"catalog_address": catalog.content_address, "content_address": content_hash(result, prefix=CATALOG_PREFIX + "-query")}


def catalog_csv(value: Any, *, state: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_catalog(value, resource="entries", state=state, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return stream.getvalue()


def render_catalog_markdown(value: Any) -> str:
    catalog = verify_catalog(value)
    lines = ["# Downloaded Data Packet-Catalog Policy Package Catalog", "", f"- Catalog: `{catalog.catalog_id}`", f"- Entries: **{catalog.entry_count}**", f"- Accepted: **{catalog.accepted_count}**", f"- Ready / blocked: **{catalog.ready_count} / {catalog.blocked_count}**", f"- Package bytes: **{catalog.total_package_bytes}**", f"- Address: `{catalog.content_address}`", "", "| # | entry | package | state | accepted | bytes |", "| ---: | --- | --- | --- | --- | ---:|"]
    lines.extend(f"| {item.ordinal} | `{item.entry_id}` | `{item.package_id}` | `{item.policy_state}` | {str(item.policy_accepted and item.audit_accepted).lower()} | {item.package_byte_count} |" for item in catalog.entries)
    return "\n".join(lines) + "\n"


__all__ = ["BOUNDARY", "CATALOG_FIELDS", "CATALOG_PREFIX", "DEFAULT_CATALOG_ID", "ENTRY_FIELDS", "ENTRY_PREFIX", "MAX_ENTRIES", "MAX_LIMIT", "MAX_PACKAGE_BYTES", "MAX_TOTAL_PACKAGE_BYTES", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry", "address_catalog", "address_entry", "build_catalog", "capabilities", "catalog_csv", "catalog_from_mapping", "catalog_json", "catalog_schema", "entry_schema", "load_catalog", "query_catalog", "render_catalog_markdown", "verify_catalog", "write_catalog"]
