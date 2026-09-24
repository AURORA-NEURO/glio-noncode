"""Independently audit the source-free packet review catalog."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_MAX_CHECKS,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAuditCheck,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_check,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 8 * 1024 * 1024


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAuditCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAuditCheck(
        **body, content_address="pending"
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAuditCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_check(
            provisional
        ),
    )


def audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit:
    """Recompute catalog lineage, conservation, state, and public-boundary invariants."""

    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog):
        raise ValidationError("packet review catalog audit requires a typed catalog")
    entries = value.entries
    checks = tuple(
        sorted(
            (
                _check(
                    "catalog-address-replay",
                    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(value)
                    == value.content_address,
                    value.catalog_address,
                    "replayable",
                    "catalog descriptor address replays from public catalog fields",
                ),
                _check(
                    "entry-address-replay",
                    all(
                        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry(item)
                        == item.content_address
                        for item in entries
                    ),
                    "replayable",
                    "replayable",
                    "every entry address is independently recomputable",
                ),
                _check(
                    "entry-count-conservation",
                    value.entry_count == len(entries) and value.entry_count > 0,
                    value.entry_count,
                    len(entries),
                    "declared entry count conserves every catalog row",
                ),
                _check(
                    "entry-ordinal-conservation",
                    tuple(item.ordinal for item in entries) == tuple(range(len(entries))),
                    tuple(item.ordinal for item in entries),
                    tuple(range(len(entries))),
                    "catalog rows retain canonical ordinal order",
                ),
                _check(
                    "member-contract-conservation",
                    all(item.member_count == 5 for item in entries),
                    tuple(item.member_count for item in entries),
                    5,
                    "each entry records the exact five-member packet contract",
                ),
                _check(
                    "packet-address-uniqueness",
                    len({item.packet_address for item in entries}) == len(entries),
                    len({item.packet_address for item in entries}),
                    len(entries),
                    "packet binary addresses are unique",
                ),
                _check(
                    "packet-id-uniqueness",
                    len({item.packet_id for item in entries}) == len(entries),
                    len({item.packet_id for item in entries}),
                    len(entries),
                    "packet IDs are unique",
                ),
                _check(
                    "packet-byte-conservation",
                    value.total_packet_bytes == sum(item.packet_byte_count for item in entries),
                    value.total_packet_bytes,
                    sum(item.packet_byte_count for item in entries),
                    "catalog packet byte totals conserve every entry",
                ),
                _check(
                    "packet-state-conservation",
                    value.accepted == all(item.packet_accepted for item in entries),
                    value.accepted,
                    all(item.packet_accepted for item in entries),
                    "catalog acceptance conserves packet acceptance",
                ),
                _check(
                    "accepted-count-conservation",
                    value.accepted_count == sum(item.packet_accepted for item in entries),
                    value.accepted_count,
                    sum(item.packet_accepted for item in entries),
                    "accepted packet count conserves rows",
                ),
                _check(
                    "blocked-count-conservation",
                    value.blocked_count == sum(not item.packet_accepted for item in entries),
                    value.blocked_count,
                    sum(not item.packet_accepted for item in entries),
                    "blocked packet count conserves rows",
                ),
                _check(
                    "gate-state-conservation",
                    value.policy_gate_blocked_count == sum(not item.policy_gate_accepted for item in entries),
                    value.policy_gate_blocked_count,
                    sum(not item.policy_gate_accepted for item in entries),
                    "blocked policy-gate evidence remains visible",
                ),
                _check(
                    "audit-state-conservation",
                    value.policy_audit_rejected_count == sum(not item.policy_audit_accepted for item in entries),
                    value.policy_audit_rejected_count,
                    sum(not item.policy_audit_accepted for item in entries),
                    "independent-audit evidence remains visible",
                ),
                _check(
                    "public-boundary",
                    not _has_forbidden_key(value.to_dict()),
                    "clean" if not _has_forbidden_key(value.to_dict()) else "forbidden-key",
                    "clean",
                    "catalog audit input contains only public aggregate fields",
                ),
                _check(
                    "payload-free-catalog",
                    "packet_bytes" not in value.to_dict() and "zip_bytes" not in value.to_dict(),
                    "payload-free",
                    "payload-free",
                    "catalog retains descriptors and addresses rather than packet payloads",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit(
        catalog_address=value.catalog_address,
        entry_count=value.entry_count,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit(
        catalog_address=value.catalog_address,
        entry_count=value.entry_count,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit):
        raise ValidationError("packet review catalog audit verification requires a typed audit")
    for check in value.checks:
        if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_check(check) != check.content_address:
            raise ValidationError(f"packet review catalog audit check address mismatch: {check.check_id}")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(value) != value.content_address:
        raise ValidationError("packet review catalog audit address mismatch")
    return value


def _check_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAuditCheck:
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAuditCheck(
        check_id=str(value.get("check_id", "")),
        passed=value.get("passed"),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "")),
    )


def _audit_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit:
    raw_checks = value.get("checks")
    if not isinstance(raw_checks, list) or any(not isinstance(item, Mapping) for item in raw_checks):
        raise ValidationError("packet review catalog audit checks are invalid")
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit(
        catalog_address=str(value.get("catalog_address", "")),
        entry_count=value.get("entry_count"),
        checks=tuple(_check_from_mapping(item) for item in raw_checks),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(result)


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit:
    if isinstance(value, Mapping):
        return _audit_from_mapping(value)
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="packet review catalog audit", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse packet review catalog audit: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("packet review catalog audit must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("packet review catalog audit is not canonical JSON")
    return _audit_from_mapping(parsed)


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_from_path(
    value: str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit:
    return audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
        load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(value)
    )


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_MAX_LIMIT:
        raise ValidationError("packet review catalog audit paging is invalid")
    audit = (
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(value)
        if isinstance(
            value,
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
        )
        else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(value)
    )
    rows = list(audit.checks)
    if passed is not None:
        rows = [item for item in rows if item.passed == passed]
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item.to_dict()).casefold()]
    body = {
        "catalog_address": audit.catalog_address,
        "audit_address": audit.content_address,
        "passed": passed,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": [item.to_dict() for item in rows[offset : offset + limit]],
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=(
                "module-workbench-release-bundle-catalog-diff-policy-set-"
                "packet-diff-policy-packet-catalog-audit-query"
            ),
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet review catalog audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet review catalog audit destination is not a file")
    _validate_parent(path.parent, "packet review catalog audit destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_json(value).encode(_UTF8),
        field="packet review catalog audit destination",
    )
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(
        value, passed=passed, text=text, offset=offset, limit=limit
    )
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogAudit,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(value)
    lines = [
        "# Packet review catalog audit",
        "",
        f"- Catalog address: `{value.catalog_address}`",
        f"- Accepted: `{value.accepted}`",
        f"- Checks: `{value.passed_count}/{len(value.checks)}` passed",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_BOUNDARY,
        "maximum_checks": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_MAX_CHECKS,
        "independent": True,
        "source_free": True,
        "recomputes": ["catalog lineage", "entry uniqueness", "state conservation", "byte conservation", "public boundary"],
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_capabilities() -> dict[str, Any]:
    operations = (
        "audit_catalog_lineage",
        "audit_entry_addresses",
        "audit_state_conservation",
        "audit_byte_conservation",
        "audit_public_boundary",
        "load_source_free",
        "query_checks",
        "export_json",
        "export_csv",
        "render_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_AUDIT_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "independent": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_from_path",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit",
]
