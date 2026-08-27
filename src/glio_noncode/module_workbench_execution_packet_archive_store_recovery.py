"""Fail-closed recovery diagnostics for persisted archive stores."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECT_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY,
)
from .run_workspace import _has_forbidden_key
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_VERSION = (
    "module-workbench-execution-packet-archive-store-recovery-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_recovery"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_FINDING_PREFIX = (
    "module-workbench-execution-packet-archive-store-recovery-finding"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-recovery"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_MAX_LIMIT = 512


class ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane(StrEnum):
    DIRECTORY = "directory"
    MANIFEST = "manifest"
    OBJECTS = "objects"
    ADDRESS = "address"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity(StrEnum):
    PASS = "pass"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field)
    if ":" not in normalized:
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _safe_object_key(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.endswith(".zip")
        and "/" not in value
        and "\\" not in value
        and ":" not in value
        and value not in {".", ".."}
    )


def _object_key(payload: bytes) -> str:
    address = hash_bytes(
        payload, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECT_PREFIX
    )
    return address.replace(":", "-") + ".zip"


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding:
    ordinal: int
    plane: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane
    code: str
    severity: ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity
    accepted: bool
    expected: str
    observed: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(self.ordinal, "finding ordinal")
        _text(self.code, "finding code", maximum=256)
        _text(self.expected, "finding expected", maximum=4096)
        _text(self.observed, "finding observed", maximum=4096)
        _text(self.detail, "finding detail", maximum=4096)
        _address(self.content_address, "finding address")
        if not isinstance(self.plane, ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane):
            raise ValidationError("finding plane is invalid")
        if not isinstance(
            self.severity, ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity
        ):
            raise ValidationError("finding severity is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("finding acceptance must be boolean")
        expected_severity = (
            ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity.PASS
            if self.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity.BLOCKED
        )
        if self.severity is not expected_severity:
            raise ValidationError("finding severity and acceptance do not agree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "plane": self.plane,
            "code": self.code,
            "severity": self.severity,
            "accepted": self.accepted,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_recovery_finding(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_FINDING_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport:
    store_id: str
    manifest_address: str
    finding_count: int
    passed_count: int
    blocked_count: int
    findings: tuple[ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.store_id, "store ID")
        _address(self.manifest_address, "manifest address")
        _count(self.finding_count, "finding count")
        _count(self.passed_count, "passed count")
        _count(self.blocked_count, "blocked count")
        if self.finding_count != len(self.findings):
            raise ValidationError("finding count does not conserve")
        if self.passed_count != sum(item.accepted for item in self.findings):
            raise ValidationError("passed count does not conserve")
        if self.blocked_count != sum(not item.accepted for item in self.findings):
            raise ValidationError("blocked count does not conserve")
        if tuple(item.ordinal for item in self.findings) != tuple(range(self.finding_count)):
            raise ValidationError("finding ordinals must be contiguous")
        if not isinstance(self.accepted, bool) or self.accepted != (self.blocked_count == 0):
            raise ValidationError("recovery acceptance does not conserve findings")
        _address(self.content_address, "recovery report address")

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_BOUNDARY,
            "store_id": self.store_id,
            "manifest_address": self.manifest_address,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def address_module_workbench_execution_packet_archive_store_recovery(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_PREFIX
    )


def _finding(
    ordinal: int,
    plane: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane,
    code: str,
    accepted: bool,
    expected: Any,
    observed: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding:
    severity = (
        ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity.PASS
        if accepted
        else ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity.BLOCKED
    )
    body = {
        "ordinal": ordinal,
        "plane": plane,
        "code": code,
        "severity": severity,
        "accepted": accepted,
        "expected": canonical_json(expected),
        "observed": canonical_json(observed),
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding(
        **body,
        content_address="pending:finding",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_recovery_finding(
            provisional
        ),
    )


def _report(
    store_id: str,
    manifest_address: str,
    findings: list[ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding],
) -> ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport:
    rows = tuple(findings)
    body = {
        "store_id": store_id,
        "manifest_address": manifest_address,
        "finding_count": len(rows),
        "passed_count": sum(item.accepted for item in rows),
        "blocked_count": sum(not item.accepted for item in rows),
        "findings": rows,
        "accepted": all(item.accepted for item in rows),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport(
        **body,
        content_address="pending:report",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_recovery(
            provisional
        ),
    )


def _fallback_report(
    code: str, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport:
    return _report(
        "unknown-store",
        "unavailable:manifest",
        [
            _finding(
                0,
                ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.DIRECTORY,
                code,
                False,
                "inspectable archive store directory",
                "unavailable",
                detail,
            )
        ],
    )


def inspect_module_workbench_execution_packet_archive_store(
    path: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport:
    """Inspect store storage without hydrating a blocked typed store."""

    root = Path(path)
    findings: list[ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding] = []
    if not root.exists() or root.is_symlink() or not root.is_dir():
        return _fallback_report(
            "store-directory-unavailable",
            "store directory is missing, symlinked, or not a directory",
        )
    findings.append(
        _finding(
            len(findings),
            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.DIRECTORY,
            "store-directory-readable",
            True,
            "regular directory",
            "regular directory",
            "store directory is present and not a symlink",
        )
    )
    manifest_path = root / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST
    manifest_bytes: bytes | None = None
    manifest: Mapping[str, Any] | None = None
    if manifest_path.is_symlink() or not manifest_path.is_file():
        findings.append(
            _finding(
                len(findings),
                ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.MANIFEST,
                "manifest-readable",
                False,
                "regular manifest file",
                "missing-or-symlinked",
                "canonical manifest file cannot be inspected",
            )
        )
    else:
        try:
            manifest_bytes = manifest_path.read_bytes()
            decoded = json.loads(manifest_bytes.decode("utf-8"))
            manifest = decoded if isinstance(decoded, Mapping) else None
            findings.append(
                _finding(
                    len(findings),
                    ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.MANIFEST,
                    "manifest-readable",
                    manifest is not None,
                    "JSON object",
                    "JSON object" if manifest is not None else "non-object JSON",
                    "manifest can be decoded as a JSON object",
                )
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            findings.append(
                _finding(
                    len(findings),
                    ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.MANIFEST,
                    "manifest-readable",
                    False,
                    "UTF-8 JSON object",
                    "unreadable",
                    "manifest bytes are not readable canonical JSON",
                )
            )
    store_id = "unknown-store"
    manifest_address = "unavailable:manifest"
    if manifest is None:
        return _report(store_id, manifest_address, findings)
    candidate_store_id = manifest.get("store_id")
    if (
        isinstance(candidate_store_id, str)
        and candidate_store_id.strip()
        and len(candidate_store_id) <= 512
    ):
        store_id = candidate_store_id
    candidate_address = manifest.get("content_address")
    if isinstance(candidate_address, str) and ":" in candidate_address:
        manifest_address = candidate_address
    if manifest_bytes is not None:
        findings.append(
            _finding(
                len(findings),
                ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.MANIFEST,
                "manifest-canonical",
                manifest_bytes == canonical_bytes(manifest),
                "canonical UTF-8 JSON bytes",
                "canonical" if manifest_bytes == canonical_bytes(manifest) else "non-canonical",
                "manifest bytes match canonical serialization",
            )
        )
    entries = manifest.get("entries")
    entries_are_rows = isinstance(entries, list) and all(
        isinstance(item, Mapping) for item in entries
    )
    findings.append(
        _finding(
            len(findings),
            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.MANIFEST,
            "manifest-entries-shaped",
            entries_are_rows,
            "array of entry objects",
            "entry objects" if entries_are_rows else "invalid entries",
            "manifest entry rows can be inspected safely",
        )
    )
    declared_keys: set[str] = set()
    if entries_are_rows:
        for item in entries:
            key = item.get("object_key")
            if _safe_object_key(key):
                declared_keys.add(key)
            findings.append(
                _finding(
                    len(findings),
                    ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
                    "object-key-safe",
                    _safe_object_key(key),
                    "safe .zip object token",
                    key if isinstance(key, str) else "invalid",
                    "manifest object key cannot escape the objects directory",
                )
            )
    objects_root = root / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY
    objects_readable = (
        objects_root.exists() and not objects_root.is_symlink() and objects_root.is_dir()
    )
    findings.append(
        _finding(
            len(findings),
            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
            "objects-directory-readable",
            objects_readable,
            "regular objects directory",
            "regular directory" if objects_readable else "missing-or-symlinked",
            "object directory is safe to enumerate",
        )
    )
    actual_keys: set[str] = set()
    if objects_readable:
        try:
            children = tuple(objects_root.iterdir())
        except OSError:
            children = ()
            findings.append(
                _finding(
                    len(findings),
                    ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
                    "objects-enumerable",
                    False,
                    "enumerable directory",
                    "unreadable",
                    "object directory cannot be enumerated",
                )
            )
        for child in children:
            if child.is_symlink() or not child.is_file():
                findings.append(
                    _finding(
                        len(findings),
                        ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
                        "object-regular",
                        False,
                        "regular non-symlink object",
                        "unsafe-entry",
                        "object directory contains a symlink or non-regular entry",
                    )
                )
                continue
            actual_keys.add(child.name)
            findings.append(
                _finding(
                    len(findings),
                    ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
                    "object-regular",
                    _safe_object_key(child.name),
                    "safe regular .zip object",
                    child.name if _safe_object_key(child.name) else "unsafe-token",
                    "stored object names remain bounded and path-free",
                )
            )
            if child.name in declared_keys:
                try:
                    payload = child.read_bytes()
                    expected_key = _object_key(payload)
                    findings.append(
                        _finding(
                            len(findings),
                            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.ADDRESS,
                            "object-address-matches",
                            expected_key == child.name,
                            child.name,
                            expected_key,
                            "object filename is the address of its exact bytes",
                        )
                    )
                except OSError:
                    findings.append(
                        _finding(
                            len(findings),
                            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
                            "object-readable",
                            False,
                            "readable bytes",
                            "unreadable",
                            "declared object bytes cannot be read",
                        )
                    )
    missing = sorted(declared_keys - actual_keys)
    extra = sorted(actual_keys - declared_keys)
    findings.append(
        _finding(
            len(findings),
            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS,
            "object-set-conserved",
            not missing and not extra,
            "manifest and object sets equal",
            "equal" if not missing and not extra else "different",
            "declared and actual object names conserve exactly",
        )
    )
    findings.append(
        _finding(
            len(findings),
            ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.PUBLIC,
            "manifest-public-boundary",
            not _has_forbidden_key(manifest),
            "no forbidden public keys",
            "clean" if not _has_forbidden_key(manifest) else "forbidden-key",
            "recovery output can retain public metadata without identity attributes",
        )
    )
    return _report(store_id, manifest_address, findings)


def verify_module_workbench_execution_packet_archive_store_recovery(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport,
) -> ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport:
    """Verify recovery findings and report address without trusting the store."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport):
        raise ValidationError("recovery verification requires a typed report")
    for finding in value.findings:
        if (
            address_module_workbench_execution_packet_archive_store_recovery_finding(finding)
            != finding.content_address
        ):
            raise ValidationError("recovery finding address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_recovery(value)
        != value.content_address
    ):
        raise ValidationError("recovery report address mismatch")
    return value


def query_module_workbench_execution_packet_archive_store_recovery(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport,
    *,
    plane: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded recovery findings for a review surface."""

    verify_module_workbench_execution_packet_archive_store_recovery(value)
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_MAX_LIMIT
    ):
        raise ValidationError("recovery query paging is invalid")
    rows = [item.to_dict() for item in value.findings]
    if plane:
        rows = [item for item in rows if item.get("plane") == plane]
    if accepted is not None:
        rows = [item for item in rows if item.get("accepted") is accepted]
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item).casefold()]
    body = {
        "store_id": value.store_id,
        "recovery_address": value.content_address,
        "plane": plane,
        "accepted_filter": accepted,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-store-recovery-query",
        )
    }


def module_workbench_execution_packet_archive_store_recovery_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_recovery(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_recovery_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_recovery(value)
    fields = (
        "ordinal",
        "plane",
        "code",
        "severity",
        "accepted",
        "expected",
        "observed",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for finding in value.findings:
        writer.writerow(finding.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_recovery_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_recovery(value)
    lines = [
        "# Archive Store Recovery Report",
        "",
        f"- Store: `{value.store_id}`",
        f"- Manifest: `{value.manifest_address}`",
        f"- Findings / passed / blocked: `{value.finding_count}` / "
        f"`{value.passed_count}` / `{value.blocked_count}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Address: `{value.content_address}`",
        "",
        "| Ordinal | Plane | Code | Severity | Accepted | Detail |",
        "|---:|---|---|---|---|---|",
    ]
    for finding in value.findings:
        lines.append(
            f"| {finding.ordinal} | `{finding.plane}` | `{finding.code}` | `{finding.severity}` | "
            f"`{str(finding.accepted).lower()}` | {finding.detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_recovery_schema() -> dict[str, Any]:
    """Describe storage recovery findings and bounded review queries."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_BOUNDARY,
        "planes": [item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane],
        "severities": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity
        ],
        "filters": ["plane", "accepted", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_MAX_LIMIT,
        },
        "inputs": ["store_directory"],
        "outputs": ["findings", "verification", "json", "csv", "markdown"],
        "mutates_storage": False,
        "identity_free": True,
        "timestamp_free": True,
        "path_free": True,
    }


def module_workbench_execution_packet_archive_store_recovery_capabilities() -> dict[str, Any]:
    """Declare read-only recovery and integrity operations."""

    operations = (
        "inspect_store_directory",
        "inspect_manifest_file",
        "verify_manifest_canonical_bytes",
        "inspect_manifest_entries",
        "verify_object_tokens",
        "inspect_objects_directory",
        "verify_object_regular_files",
        "verify_object_byte_addresses",
        "detect_missing_objects",
        "detect_extra_objects",
        "verify_object_set_conservation",
        "verify_public_boundary",
        "query_recovery_findings",
        "filter_recovery_plane",
        "filter_recovery_acceptance",
        "page_recovery_findings",
        "export_recovery_json",
        "export_recovery_csv",
        "export_recovery_markdown",
        "verify_recovery_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "offline": True,
        "fail_closed": True,
        "deterministic": True,
        "mutates_storage": False,
        "identity_free": True,
    }


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_FINDING_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RECOVERY_VERSION",
    "ModuleWorkbenchExecutionPacketArchiveStoreRecoveryFinding",
    "ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane",
    "ModuleWorkbenchExecutionPacketArchiveStoreRecoveryReport",
    "ModuleWorkbenchExecutionPacketArchiveStoreRecoverySeverity",
    "address_module_workbench_execution_packet_archive_store_recovery",
    "address_module_workbench_execution_packet_archive_store_recovery_finding",
    "inspect_module_workbench_execution_packet_archive_store",
    "module_workbench_execution_packet_archive_store_recovery_capabilities",
    "module_workbench_execution_packet_archive_store_recovery_csv",
    "module_workbench_execution_packet_archive_store_recovery_json",
    "module_workbench_execution_packet_archive_store_recovery_schema",
    "query_module_workbench_execution_packet_archive_store_recovery",
    "render_module_workbench_execution_packet_archive_store_recovery_markdown",
    "verify_module_workbench_execution_packet_archive_store_recovery",
]
