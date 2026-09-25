"""Build, verify, query, and persist source-free module663 transport catalogs."""
# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_663 as transport_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_663_aud as transport_audit_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_664_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = contract_model.VERSION
BOUNDARY = contract_model.BOUNDARY
CATALOG_PREFIX = contract_model.CATALOG_PREFIX
ENTRY_PREFIX = contract_model.ENTRY_PREFIX
MAX_ENTRIES = contract_model.MAX_ENTRIES
MAX_LIMIT = 256
DEFAULT_CATALOG_ID = CATALOG_PREFIX

def _entry(package: Any, entry_id: str) -> contract_model.Entry:
    package_value = transport_model.verify_package(package)
    receipt = transport_audit_model.audit_package(package_value)
    if not receipt.accepted:
        raise ValidationError("module664 catalog requires an accepted module663 transport audit")
    manifest = package_value.manifest
    body = {"entry_id": entry_id, "package_id": manifest.package_id, "package_address": package_value.package_address, "manifest_address": manifest.content_address, "diff_address": manifest.diff_address, "policy_address": manifest.policy_address, "audit_address": manifest.audit_address, "policy_state": manifest.policy_state, "policy_accepted": manifest.policy_accepted, "audit_accepted": manifest.audit_accepted, "package_byte_count": len(package_value.package_bytes), "member_count": len(manifest.members), "content_address": contract_model.ENTRY_PREFIX + ":pending"}
    provisional = contract_model.Entry(**body)
    return contract_model.Entry(**(body | {"content_address": contract_model.address_entry(provisional)}))


def build_catalog(packages: Sequence[Any], *, entry_ids: Sequence[str] | None = None, catalog_id: str = DEFAULT_CATALOG_ID) -> contract_model.Catalog:
    if isinstance(packages, (str, bytes, bytearray)) or not isinstance(packages, Sequence) or len(packages) > MAX_ENTRIES:
        raise ValidationError("module664 packages must be a bounded sequence")
    if entry_ids is not None and (isinstance(entry_ids, (str, bytes, bytearray)) or not isinstance(entry_ids, Sequence) or len(entry_ids) != len(packages)):
        raise ValidationError("module664 entry IDs must align with packages")
    identifiers = tuple(entry_ids) if entry_ids is not None else tuple(transport_model.verify_package(package).manifest.package_id for package in packages)
    built_entries = tuple(_entry(package, entry_id) for package, entry_id in zip(packages, identifiers, strict=True))
    if len({item.package_address for item in built_entries}) != len(built_entries):
        raise ValidationError("module664 catalog contains duplicate package addresses")
    entries = tuple(sorted(built_entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = contract_model.Catalog(**body)
    return contract_model.Catalog(**(body | {"content_address": contract_model.address_catalog(provisional)}))


def _catalog_from_mapping(value: Mapping[str, Any]) -> contract_model.Catalog:
    if not isinstance(value, Mapping):
        raise ValidationError("module664 catalog must be an object")
    return contract_model.Catalog.from_mapping(dict(value))


def load_catalog(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> contract_model.Catalog:
    raw = value if isinstance(value, Mapping) else _strict_json_loads(bytes(value).decode("utf-8")) if isinstance(value, (bytes, bytearray)) else _strict_json_loads(read_text(value, field="module664 catalog", max_bytes=32 * 1024 * 1024))
    return _catalog_from_mapping(raw)


def verify_catalog(value: Any) -> contract_model.Catalog:
    catalog = load_catalog(value) if isinstance(value, (str, Path, bytes, bytearray, Mapping)) else value
    if not isinstance(catalog, contract_model.Catalog) or contract_model.address_catalog(catalog) != catalog.content_address or _has_forbidden_key(catalog.to_dict()):
        raise ValidationError("module664 catalog address or public boundary does not replay")
    return contract_model.Catalog.from_mapping(catalog.to_dict())


def catalog_json(value: Any) -> str:
    return canonical_json(verify_catalog(value).to_dict()) + "\n"


def write_catalog(value: Any, destination: str | Path, *, allow_existing: bool = False) -> contract_model.Catalog:
    catalog = verify_catalog(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module664 catalog destination already exists")
    _validate_parent(path.parent, "module664 catalog destination")
    atomic_write_text(path, catalog_json(catalog), field="module664 catalog destination")
    return catalog


def query_catalog(value: Any, *, resource: str = "summary", state: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    catalog = verify_catalog(value)
    if resource not in {"summary", "entries", "lineage", "state"} or state not in {"", "ready", "blocked"} or not isinstance(text, str) or len(text) > 4096 or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module664 catalog query filters are invalid")
    values = (catalog.summary(),) if resource in {"summary", "state"} else tuple(item.to_dict() for item in catalog.entries)
    if state:
        values = tuple(item for item in values if (item.get("policy_state") if isinstance(item, dict) and "policy_state" in item else item.get("state")) == state)
    total = len(values)
    matches = tuple(item for item in values if not text or text.casefold() in canonical_json(item).casefold())
    selected = matches[offset:offset + limit]
    result = {"catalog_address": catalog.content_address, "resource": resource, "state": state, "text": text, "offset": offset, "limit": limit, "total": total, "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "values": selected}
    return result | {"content_address": content_hash(result, prefix=CATALOG_PREFIX + "-query")}


def catalog_csv(value: Any, *, resource: str = "entries", state: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_catalog(value, resource=resource, state=state, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("resource", "value"))
    for item in result["values"]:
        writer.writerow((resource, item if isinstance(item, str) else canonical_json(item)))
    return stream.getvalue()


def render_catalog_markdown(value: Any) -> str:
    catalog = verify_catalog(value)
    lines = ["# Module664 Fixed Policy Decision Transport Catalog", "", f"- Catalog: `{catalog.content_address}`", f"- State: **{catalog.state}**", f"- Entries: **{catalog.entry_count}**", f"- Audited: **{catalog.accepted_count}/{catalog.entry_count}**", "", "| entry | policy state | policy accepted | bytes | package |", "| --- | --- | --- | ---: | --- |"]
    lines.extend(f"| `{item.entry_id}` | {item.policy_state} | {str(item.policy_accepted).lower()} | {item.package_byte_count} | `{item.package_address}` |" for item in catalog.entries)
    return "\n".join(lines) + "\n"


build_transport_catalog = build_catalog
verify_transport_catalog = verify_catalog
load_transport_catalog = load_catalog
write_transport_catalog = write_catalog
transport_catalog_json = catalog_json
transport_catalog_csv = catalog_csv
render_transport_catalog_markdown = render_catalog_markdown
transport_catalog_schema = contract_model.catalog_schema
transport_catalog_entry_schema = contract_model.entry_schema
Catalog = contract_model.Catalog
Entry = contract_model.Entry
address_catalog = contract_model.address_catalog
address_entry = contract_model.address_entry
capabilities = contract_model.capabilities
catalog_schema = contract_model.catalog_schema
entry_schema = contract_model.entry_schema

__all__ = ["BOUNDARY", "CATALOG_PREFIX", "DEFAULT_CATALOG_ID", "ENTRY_PREFIX", "MAX_ENTRIES", "VERSION", "build_catalog", "build_transport_catalog", "capabilities", "catalog_csv", "catalog_json", "catalog_schema", "entry_schema", "load_catalog", "load_transport_catalog", "query_catalog", "render_catalog_markdown", "render_transport_catalog_markdown", "transport_catalog_csv", "transport_catalog_entry_schema", "transport_catalog_json", "transport_catalog_schema", "verify_catalog", "verify_transport_catalog", "write_catalog", "write_transport_catalog"]
