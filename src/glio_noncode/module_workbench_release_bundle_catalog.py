"""Build, verify, and query a source-free catalog of release bundles."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle import (
    load_module_workbench_release_bundle,
    verify_module_workbench_release_bundle,
    verify_module_workbench_release_bundle_value,
)
from .module_workbench_release_bundle_catalog_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_FORMAT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_CHECKS,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_QUERY_PREFIX,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION,
    ModuleWorkbenchReleaseBundleCatalog,
    ModuleWorkbenchReleaseBundleCatalogCheck,
    ModuleWorkbenchReleaseBundleCatalogCheckPlane,
    ModuleWorkbenchReleaseBundleCatalogEntry,
    ModuleWorkbenchReleaseBundleCatalogState,
    ModuleWorkbenchReleaseBundleCatalogVerification,
    address_module_workbench_release_bundle_catalog,
    address_module_workbench_release_bundle_catalog_check,
    address_module_workbench_release_bundle_catalog_entry,
    address_module_workbench_release_bundle_catalog_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"


def _read_catalog(value: bytes | bytearray | str | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, (str, Path)):
        raw = read_bytes(
            value,
            field="module workbench release bundle catalog",
            max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES,
        )
    else:
        raise ValidationError("catalog input must be bytes or a path")
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES:
        raise ValidationError("catalog exceeds byte limit")
    return raw


def _document(body: Mapping[str, Any]) -> bytes:
    return (canonical_json(body) + "\n").encode(_UTF8)


def _logical_catalog_body(body: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result.pop("catalog_address", None)
    result.pop("catalog_byte_count", None)
    result.pop("content_address", None)
    return result


def _entry(
    ordinal: int,
    bundle: Any,
    verification: Any,
) -> ModuleWorkbenchReleaseBundleCatalogEntry:
    body = {
        "bundle_id": bundle.bundle_id,
        "bundle_address": bundle.bundle_address,
        "bundle_content_address": bundle.content_address,
        "verification_address": verification.content_address,
        "previous_archive_address": bundle.previous_archive_address,
        "current_archive_address": bundle.current_archive_address,
        "diff_address": bundle.diff_address,
        "policy_gate_address": bundle.policy_gate_address,
        "bundle_byte_count": bundle.bundle_byte_count,
        "bundle_entry_count": bundle.entry_count,
        "verification_failed_count": verification.failed_count,
        "ordinal": ordinal,
        "state": (
            ModuleWorkbenchReleaseBundleCatalogState.ACCEPTED
            if bundle.accepted
            else ModuleWorkbenchReleaseBundleCatalogState.BLOCKED
        ),
        "accepted": bundle.accepted,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogEntry(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogEntry(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_entry(provisional),
    )


def _verified_bundle(value: Any) -> tuple[Any, Any]:
    if hasattr(value, "bundle_bytes"):
        bundle = value
        verify_module_workbench_release_bundle_value(bundle)
        raw = bundle.bundle_bytes
    else:
        bundle = load_module_workbench_release_bundle(value)
        raw = bundle.bundle_bytes
    verification = verify_module_workbench_release_bundle(raw)
    if not verification.accepted:
        raise ValidationError("catalog bundle reference is structurally invalid")
    return bundle, verification


def build_module_workbench_release_bundle_catalog(
    bundles: Sequence[Any],
    *,
    catalog_id: str = "glio-noncode-module-workbench-release-bundle-catalog",
) -> ModuleWorkbenchReleaseBundleCatalog:
    """Aggregate verified bundle descriptors without copying their ZIP payloads."""

    if not isinstance(catalog_id, str) or not catalog_id.strip():
        raise ValidationError("catalog ID is required")
    if isinstance(bundles, (str, bytes, bytearray)) or not isinstance(bundles, Sequence):
        raise ValidationError("catalog bundles must be a sequence")
    if not bundles or len(bundles) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES:
        raise ValidationError("catalog bundle count is outside the supported range")
    loaded = tuple(_verified_bundle(value) for value in bundles)
    bundle_ids = tuple(bundle.bundle_id for bundle, _ in loaded)
    bundle_addresses = tuple(bundle.bundle_address for bundle, _ in loaded)
    if len(set(bundle_ids)) != len(bundle_ids):
        raise ValidationError("catalog bundle IDs must be unique")
    if len(set(bundle_addresses)) != len(bundle_addresses):
        raise ValidationError("catalog bundle addresses must be unique")
    entries = tuple(
        _entry(index, bundle, verification) for index, (bundle, verification) in enumerate(loaded)
    )
    accepted = all(item.accepted for item in entries)
    state = (
        ModuleWorkbenchReleaseBundleCatalogState.ACCEPTED
        if accepted
        else ModuleWorkbenchReleaseBundleCatalogState.BLOCKED
    )
    body: dict[str, Any] = {
        "catalog_id": catalog_id,
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_BOUNDARY,
        "catalog_format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_FORMAT,
        "catalog_address": "pending",
        "catalog_byte_count": 0,
        "total_bundle_bytes": sum(item.bundle_byte_count for item in entries),
        "entry_count": len(entries),
        "entries": entries,
        "state": state,
        "accepted": accepted,
        "content_address": "pending",
    }
    body["catalog_address"] = content_hash(
        _logical_catalog_body(body), prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX
    )
    for _ in range(8):
        raw = _document(body)
        if len(raw) != body["catalog_byte_count"]:
            body["catalog_byte_count"] = len(raw)
            continue
        provisional = ModuleWorkbenchReleaseBundleCatalog(
            **body,
            catalog_bytes=raw,
        )
        content_address = address_module_workbench_release_bundle_catalog(provisional)
        if body["content_address"] != content_address:
            body["content_address"] = content_address
            continue
        return ModuleWorkbenchReleaseBundleCatalog(**body, catalog_bytes=raw)
    else:
        raise ValidationError("catalog address sizing did not converge")


def write_module_workbench_release_bundle_catalog(
    value: ModuleWorkbenchReleaseBundleCatalog,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalog:
    verify_module_workbench_release_bundle_catalog_value(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("catalog destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("catalog destination is not a file")
    _validate_parent(path.parent, "catalog destination")
    atomic_write_bytes(path, value.catalog_bytes, field="catalog destination")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _entry_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogEntry:
    return ModuleWorkbenchReleaseBundleCatalogEntry(
        bundle_id=str(value.get("bundle_id", "")),
        bundle_address=str(value.get("bundle_address", "")),
        bundle_content_address=str(value.get("bundle_content_address", "")),
        verification_address=str(value.get("verification_address", "")),
        previous_archive_address=str(value.get("previous_archive_address", "")),
        current_archive_address=str(value.get("current_archive_address", "")),
        diff_address=str(value.get("diff_address", "")),
        policy_gate_address=str(value.get("policy_gate_address", "")),
        bundle_byte_count=value.get("bundle_byte_count"),
        bundle_entry_count=value.get("bundle_entry_count"),
        verification_failed_count=value.get("verification_failed_count"),
        ordinal=value.get("ordinal"),
        state=ModuleWorkbenchReleaseBundleCatalogState(str(value.get("state"))),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )


def _catalog_from_mapping(
    payload: Mapping[str, Any],
    raw: bytes,
) -> ModuleWorkbenchReleaseBundleCatalog:
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValidationError("catalog entries are invalid")
    entries = tuple(_entry_from_mapping(_mapping(item, "catalog entry")) for item in raw_entries)
    body = {
        "catalog_id": str(payload.get("catalog_id", "")),
        "version": str(payload.get("version", "")),
        "boundary": str(payload.get("boundary", "")),
        "catalog_format": str(payload.get("catalog_format", "")),
        "catalog_address": str(payload.get("catalog_address", "")),
        "catalog_byte_count": payload.get("catalog_byte_count"),
        "total_bundle_bytes": payload.get("total_bundle_bytes"),
        "entry_count": payload.get("entry_count"),
        "entries": entries,
        "state": ModuleWorkbenchReleaseBundleCatalogState(str(payload.get("state"))),
        "accepted": payload.get("accepted"),
        "content_address": str(payload.get("content_address", "")),
    }
    return ModuleWorkbenchReleaseBundleCatalog(**body, catalog_bytes=raw)


def _check(
    check_id: str,
    plane: ModuleWorkbenchReleaseBundleCatalogCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_check(provisional),
    )


def _verification(
    catalog_id: str,
    catalog_address: str,
    entry_count: int,
    checks: list[ModuleWorkbenchReleaseBundleCatalogCheck],
) -> ModuleWorkbenchReleaseBundleCatalogVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {
        "catalog_id": catalog_id,
        "catalog_address": catalog_address,
        "entry_count": entry_count,
        "checks": ordered,
        "accepted": bool(ordered) and all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogVerification(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_verification(provisional),
    )


def verify_module_workbench_release_bundle_catalog(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogVerification:
    """Verify canonical catalog structure and every retained bundle reference."""

    raw = _read_catalog(value)
    payload: Mapping[str, Any] | None = None
    parse_error = ""
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
        payload = parsed if isinstance(parsed, Mapping) else None
    except (UnicodeDecodeError, ValueError) as exc:
        parse_error = str(exc)
    catalog_id = str(payload.get("catalog_id", "unavailable")) if payload else "unavailable"
    catalog_address = (
        str(payload.get("catalog_address", "unavailable")) if payload else "unavailable"
    )
    raw_entries = payload.get("entries") if payload else None
    entry_count = payload.get("entry_count", 0) if payload else 0
    if not isinstance(entry_count, int) or isinstance(entry_count, bool) or entry_count < 0:
        entry_count = 0
    if entry_count > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES:
        entry_count = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES
    checks: list[ModuleWorkbenchReleaseBundleCatalogCheck] = []
    canonical_ok = payload is not None and raw == _document(payload)
    checks.append(
        _check(
            "canonical-json",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.STRUCTURE,
            canonical_ok,
            "canonical" if canonical_ok else (parse_error or "non-canonical"),
            "canonical",
            "catalog is one canonical UTF-8 JSON document",
        )
    )
    parsed_entries: tuple[ModuleWorkbenchReleaseBundleCatalogEntry, ...] = ()
    entry_error = ""
    if isinstance(raw_entries, list):
        try:
            parsed_entries = tuple(
                _entry_from_mapping(_mapping(item, "catalog entry")) for item in raw_entries
            )
        except (TypeError, ValueError, ValidationError) as exc:
            entry_error = str(exc)
    shape_ok = (
        payload is not None
        and isinstance(raw_entries, list)
        and len(parsed_entries) == entry_count
        and entry_count > 0
    )
    checks.append(
        _check(
            "entry-shape",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.STRUCTURE,
            shape_ok,
            len(parsed_entries) if not entry_error else entry_error,
            entry_count,
            "catalog entry rows are bounded and reconstructable",
        )
    )
    ids = tuple(item.bundle_id for item in parsed_entries)
    addresses = tuple(item.bundle_address for item in parsed_entries)
    unique_ok = len(ids) == len(set(ids)) and len(addresses) == len(set(addresses))
    checks.append(
        _check(
            "unique-bundles",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.REFERENCES,
            unique_ok,
            {
                "duplicate_ids": sorted({item for item in ids if ids.count(item) > 1}),
                "duplicate_addresses": sorted(
                    {item for item in addresses if addresses.count(item) > 1}
                ),
            },
            {"duplicate_ids": [], "duplicate_addresses": []},
            "bundle identity and binary addresses are unique",
        )
    )
    entry_address_failures = [
        item.bundle_id
        for item in parsed_entries
        if address_module_workbench_release_bundle_catalog_entry(item) != item.content_address
    ]
    checks.append(
        _check(
            "entry-addresses",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.REFERENCES,
            not entry_address_failures,
            entry_address_failures,
            [],
            "each catalog entry preserves its content address",
        )
    )
    reference_failures = [
        item.bundle_id
        for item in parsed_entries
        if item.verification_failed_count != 0
        or not all(
            isinstance(field, str) and bool(field.strip())
            for field in (
                item.bundle_address,
                item.bundle_content_address,
                item.verification_address,
                item.previous_archive_address,
                item.current_archive_address,
                item.diff_address,
                item.policy_gate_address,
            )
        )
    ]
    checks.append(
        _check(
            "verified-references",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.REFERENCES,
            not reference_failures,
            reference_failures,
            [],
            "catalog rows retain structurally verified bundle references",
        )
    )
    state_ok = all(
        item.accepted == (item.state is ModuleWorkbenchReleaseBundleCatalogState.ACCEPTED)
        for item in parsed_entries
    )
    if payload is not None:
        aggregate_accepted = bool(payload.get("accepted"))
        aggregate_state = str(payload.get("state"))
        state_ok = state_ok and aggregate_accepted == all(item.accepted for item in parsed_entries)
        state_ok = state_ok and aggregate_state == (
            ModuleWorkbenchReleaseBundleCatalogState.ACCEPTED.value
            if aggregate_accepted
            else ModuleWorkbenchReleaseBundleCatalogState.BLOCKED.value
        )
    checks.append(
        _check(
            "state-conservation",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.STATE,
            state_ok,
            "conserved" if state_ok else "mismatch",
            "conserved",
            "aggregate state conserves every retained bundle decision",
        )
    )
    total_bytes = sum(item.bundle_byte_count for item in parsed_entries)
    bytes_ok = payload is not None and payload.get("total_bundle_bytes") == total_bytes
    checks.append(
        _check(
            "byte-conservation",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.BYTES,
            bytes_ok,
            total_bytes,
            payload.get("total_bundle_bytes") if payload else None,
            "aggregate bundle byte count conserves entry sizes",
        )
    )
    address_ok = False
    descriptor_ok = False
    if payload is not None:
        expected_address = content_hash(
            _logical_catalog_body(payload), prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX
        )
        address_ok = expected_address == payload.get("catalog_address")
        try:
            catalog = _catalog_from_mapping(payload, raw)
            descriptor_ok = (
                address_module_workbench_release_bundle_catalog(catalog) == catalog.content_address
            )
        except (TypeError, ValueError, ValidationError):
            descriptor_ok = False
    checks.append(
        _check(
            "catalog-address",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.REFERENCES,
            address_ok,
            "conserved" if address_ok else "mismatch",
            "conserved",
            "catalog address replays from public logical fields",
        )
    )
    checks.append(
        _check(
            "descriptor-address",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.REFERENCES,
            descriptor_ok,
            "conserved" if descriptor_ok else "mismatch",
            "conserved",
            "catalog descriptor address replays from the canonical document",
        )
    )
    public_ok = payload is not None and not _has_forbidden_key(payload)
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchReleaseBundleCatalogCheckPlane.PUBLIC,
            public_ok,
            "clean" if public_ok else "forbidden-or-invalid",
            "clean",
            "catalog contains only public aggregate evidence",
        )
    )
    return _verification(catalog_id, catalog_address, entry_count, checks)


def verify_module_workbench_release_bundle_catalog_value(
    value: ModuleWorkbenchReleaseBundleCatalog,
) -> ModuleWorkbenchReleaseBundleCatalog:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalog):
        raise ValidationError("typed catalog verification requires a catalog")
    if _document(value.to_dict()) != value.catalog_bytes:
        raise ValidationError("catalog binary bytes are not canonical")
    if (
        content_hash(
            _logical_catalog_body(value.to_dict()),
            prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX,
        )
        != value.catalog_address
    ):
        raise ValidationError("catalog binary address mismatch")
    if address_module_workbench_release_bundle_catalog(value) != value.content_address:
        raise ValidationError("catalog descriptor address mismatch")
    return value


def load_module_workbench_release_bundle_catalog(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalog:
    verification = verify_module_workbench_release_bundle_catalog(value)
    if not verification.accepted:
        raise ValidationError("cannot load malformed release bundle catalog")
    raw = _read_catalog(value)
    parsed = _strict_json_loads(raw.decode(_UTF8))
    return _catalog_from_mapping(_mapping(parsed, "catalog"), raw)


def query_module_workbench_release_bundle_catalog(
    value: ModuleWorkbenchReleaseBundleCatalog | bytes | bytearray | str | Path,
    *,
    resource: str = "entries",
    state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_LIMIT:
        raise ValidationError("catalog paging is invalid")
    if state is not None and state not in {
        item.value for item in ModuleWorkbenchReleaseBundleCatalogState
    }:
        raise ValidationError("catalog state filter is invalid")
    catalog = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundleCatalog)
        else load_module_workbench_release_bundle_catalog(value)
    )
    verify_module_workbench_release_bundle_catalog_value(catalog)
    if resource == "entries":
        rows = [item.to_dict() for item in catalog.entries]
    elif resource == "summary":
        rows = [catalog.to_dict(include_entries=False)]
    else:
        raise ValidationError("catalog resource must be entries or summary")
    if state is not None:
        rows = [item for item in rows if item.get("state") == state]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "catalog_address": catalog.catalog_address,
        "resource": resource,
        "state": state,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": catalog.accepted,
    }
    return body | {
        "content_address": content_hash(
            body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_QUERY_PREFIX
        )
    }


def module_workbench_release_bundle_catalog_json(
    value: ModuleWorkbenchReleaseBundleCatalog,
) -> str:
    verify_module_workbench_release_bundle_catalog_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_catalog_csv(
    value: ModuleWorkbenchReleaseBundleCatalog,
    *,
    state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog(
        value, state=state, text=text, offset=offset, limit=limit
    )
    output = io.StringIO(newline="")
    fields = tuple(sorted({key for row in result["items"] for key in row}))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_markdown(
    value: ModuleWorkbenchReleaseBundleCatalog,
) -> str:
    verify_module_workbench_release_bundle_catalog_value(value)
    lines = [
        "# Module Workbench Release Bundle Catalog",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Catalog address: `{value.catalog_address}`",
        f"- Bundle count: {value.entry_count}",
        f"- Total bundle bytes: {value.total_bundle_bytes}",
        f"- State: `{value.state.value}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Ordinal | Bundle | State | Bytes | Diff address | Policy address |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.bundle_id}` | `{item.state.value}` "
        f"| {item.bundle_byte_count} | `{item.diff_address}` | `{item.policy_gate_address}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_BOUNDARY,
        "format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_FORMAT,
        "resources": ["entries", "summary"],
        "max_entries": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES,
        "max_checks": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_CHECKS,
        "max_bytes": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
        "retains_payloads": False,
    }


def module_workbench_release_bundle_catalog_capabilities() -> dict[str, Any]:
    operations = (
        "aggregate_verified_bundle_references",
        "reject_duplicate_bundle_identity",
        "fold_accepted_and_blocked_state",
        "replay_reference_addresses",
        "load_without_source_access",
        "query_entries",
        "filter_state",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
        "payload_free": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog",
    "load_module_workbench_release_bundle_catalog",
    "module_workbench_release_bundle_catalog_capabilities",
    "module_workbench_release_bundle_catalog_csv",
    "module_workbench_release_bundle_catalog_json",
    "module_workbench_release_bundle_catalog_schema",
    "query_module_workbench_release_bundle_catalog",
    "render_module_workbench_release_bundle_catalog_markdown",
    "verify_module_workbench_release_bundle_catalog",
    "verify_module_workbench_release_bundle_catalog_value",
    "write_module_workbench_release_bundle_catalog",
]
