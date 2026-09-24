"""Build and verify a single portable release-evidence bundle."""

from __future__ import annotations

import csv
import io
import stat
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_archive import (
    _read_archive,
    load_module_workbench_archive,
    verify_module_workbench_archive,
    verify_module_workbench_archive_value,
)
from .module_workbench_archive_contracts import ModuleWorkbenchArchive
from .module_workbench_archive_diff import (
    build_module_workbench_archive_diff,
    load_module_workbench_archive_diff,
    module_workbench_archive_diff_json,
    verify_module_workbench_archive_diff_value,
)
from .module_workbench_archive_diff_contracts import ModuleWorkbenchArchiveDiff
from .module_workbench_archive_diff_policy import (
    default_module_workbench_archive_diff_policy,
    evaluate_module_workbench_archive_diff_policy,
    load_module_workbench_archive_diff_policy_gate,
    module_workbench_archive_diff_policy_json,
    verify_module_workbench_archive_diff_policy_gate,
)
from .module_workbench_archive_diff_policy_contracts import (
    ModuleWorkbenchArchiveDiffPolicyGate,
)
from .module_workbench_release_bundle_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
    MODULE_WORKBENCH_RELEASE_BUNDLE_ENTRY_PREFIX,
    MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST,
    MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX,
    MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS,
    MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW,
    MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION,
    ModuleWorkbenchReleaseBundle,
    ModuleWorkbenchReleaseBundleCheck,
    ModuleWorkbenchReleaseBundleCheckPlane,
    ModuleWorkbenchReleaseBundleEntry,
    ModuleWorkbenchReleaseBundleEntryKind,
    ModuleWorkbenchReleaseBundleState,
    ModuleWorkbenchReleaseBundleVerification,
    address_module_workbench_release_bundle,
    address_module_workbench_release_bundle_check,
    address_module_workbench_release_bundle_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"


def _safe_path(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
    ):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _line_count(payload: bytes) -> int:
    try:
        return len(payload.decode(_UTF8).splitlines())
    except UnicodeDecodeError:
        return 0


def _zip_member(name: str) -> zipfile.ZipInfo:
    if not _safe_path(name):
        raise ValidationError(f"unsafe release bundle member: {name}")
    info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.external_attr = 0
    info.extra = b""
    info.comment = b""
    return info


def _read_bundle(value: bytes | bytearray | str | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, (str, Path)):
        raw = read_bytes(
            value,
            field="module workbench release bundle",
            max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES,
        )
    else:
        raise ValidationError("release bundle input must be bytes or a path")
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES:
        raise ValidationError("release bundle exceeds byte limit")
    return raw


def _archive_payload(
    value: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
) -> tuple[bytes, str, bool]:
    if isinstance(value, ModuleWorkbenchArchive):
        verify_module_workbench_archive_value(value)
        raw = value.archive_bytes
    else:
        raw = _read_archive(value)
    verification = verify_module_workbench_archive(raw)
    if not verification.accepted:
        raise ValidationError("release bundle workbench archive is malformed")
    report = load_module_workbench_archive(raw)
    return raw, verification.archive_address, report.accepted


def _diff_value(
    value: ModuleWorkbenchArchiveDiff | bytes | bytearray | str | Path,
) -> ModuleWorkbenchArchiveDiff:
    if isinstance(value, ModuleWorkbenchArchiveDiff):
        return verify_module_workbench_archive_diff_value(value)
    return load_module_workbench_archive_diff(value)


def _policy_value(
    value: ModuleWorkbenchArchiveDiffPolicyGate | bytes | bytearray | str | Path,
) -> ModuleWorkbenchArchiveDiffPolicyGate:
    if isinstance(value, ModuleWorkbenchArchiveDiffPolicyGate):
        return verify_module_workbench_archive_diff_policy_gate(value)
    return load_module_workbench_archive_diff_policy_gate(value)


def _review_bytes(
    diff: ModuleWorkbenchArchiveDiff,
    gate: ModuleWorkbenchArchiveDiffPolicyGate,
    previous_address: str,
    current_address: str,
) -> bytes:
    lines = [
        "# Module Workbench Release Evidence",
        "",
        f"- Previous archive: `{previous_address}`",
        f"- Current archive: `{current_address}`",
        f"- Archive diff: `{diff.content_address}`",
        f"- Policy gate: `{gate.content_address}`",
        "- Added / changed / removed / unchanged: **"
        f"{diff.diff.added_count} / {diff.diff.changed_count} / "
        f"{diff.diff.removed_count} / {diff.diff.unchanged_count}**",
        f"- Score delta: **{diff.diff.score_delta}**",
        f"- Policy accepted: **{str(gate.accepted).lower()}**",
        "",
        "| Policy check | Passed | Observed | Required |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | {str(item.passed).lower()} | `{item.observed}` "
        f"| `{item.required}` |"
        for item in gate.checks
    )
    return ("\n".join(lines) + "\n").encode(_UTF8)


def _manifest_bytes(
    bundle_id: str,
    previous_address: str,
    current_address: str,
    diff: ModuleWorkbenchArchiveDiff,
    gate: ModuleWorkbenchArchiveDiffPolicyGate,
    review: bytes,
    accepted: bool,
) -> bytes:
    body = {
        "bundle_id": bundle_id,
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY,
        "bundle_format": MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT,
        "previous_archive_path": MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS,
        "current_archive_path": MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT,
        "diff_path": MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
        "policy_path": MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY,
        "review_path": MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW,
        "previous_archive_address": previous_address,
        "current_archive_address": current_address,
        "diff_address": diff.content_address,
        "policy_gate_address": gate.content_address,
        "review_byte_count": len(review),
        "review_line_count": _line_count(review),
        "entry_count": MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES,
        "state": ModuleWorkbenchReleaseBundleState.ACCEPTED
        if accepted
        else ModuleWorkbenchReleaseBundleState.BLOCKED,
        "accepted": accepted,
    }
    return (canonical_json(body) + "\n").encode(_UTF8)


def _zip_bytes(members: tuple[tuple[str, bytes], ...]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as handle:
        for name, payload in members:
            handle.writestr(_zip_member(name), payload)
    raw = output.getvalue()
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES:
        raise ValidationError("release bundle exceeds byte limit")
    return raw


def _entry(
    ordinal: int,
    path: str,
    kind: ModuleWorkbenchReleaseBundleEntryKind,
    payload: bytes,
    media_type: str,
    entry_id: str,
) -> ModuleWorkbenchReleaseBundleEntry:
    body = {
        "entry_id": entry_id,
        "relative_path": path,
        "kind": kind,
        "media_type": media_type,
        "ordinal": ordinal,
        "byte_count": len(payload),
        "line_count": _line_count(payload),
    }
    provisional = ModuleWorkbenchReleaseBundleEntry(
        **body,
        content_address=hash_bytes(payload, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_ENTRY_PREFIX),
    )
    return provisional


def build_module_workbench_release_bundle(
    previous: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
    current: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
    *,
    diff: ModuleWorkbenchArchiveDiff | bytes | bytearray | str | Path | None = None,
    policy_gate: ModuleWorkbenchArchiveDiffPolicyGate
    | bytes
    | bytearray
    | str
    | Path
    | None = None,
    bundle_id: str = "glio-noncode-module-workbench-release-bundle",
) -> ModuleWorkbenchReleaseBundle:
    """Build one deterministic ZIP containing both archives and their decisions."""

    if not isinstance(bundle_id, str) or not bundle_id.strip():
        raise ValidationError("release bundle ID is required")
    previous_raw, previous_address, previous_accepted = _archive_payload(previous)
    current_raw, current_address, current_accepted = _archive_payload(current)
    selected_diff = (
        _diff_value(diff)
        if diff is not None
        else build_module_workbench_archive_diff(previous_raw, current_raw)
    )
    if (
        selected_diff.previous_archive_address != previous_address
        or selected_diff.current_archive_address != current_address
    ):
        raise ValidationError("release bundle diff does not conserve archive addresses")
    selected_gate = (
        _policy_value(policy_gate)
        if policy_gate is not None
        else evaluate_module_workbench_archive_diff_policy(
            selected_diff,
            default_module_workbench_archive_diff_policy(),
        )
    )
    if selected_gate.diff_address != selected_diff.content_address:
        raise ValidationError("release bundle policy gate does not conserve diff address")
    accepted = (
        previous_accepted and current_accepted and selected_diff.accepted and selected_gate.accepted
    )
    diff_raw = module_workbench_archive_diff_json(selected_diff).encode(_UTF8)
    policy_raw = module_workbench_archive_diff_policy_json(selected_gate).encode(_UTF8)
    review_raw = _review_bytes(selected_diff, selected_gate, previous_address, current_address)
    manifest_raw = _manifest_bytes(
        bundle_id,
        previous_address,
        current_address,
        selected_diff,
        selected_gate,
        review_raw,
        accepted,
    )
    members = (
        (MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST, manifest_raw),
        (MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS, previous_raw),
        (MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT, current_raw),
        (MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF, diff_raw),
        (MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY, policy_raw),
        (MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW, review_raw),
    )
    raw = _zip_bytes(members)
    kinds = (
        ModuleWorkbenchReleaseBundleEntryKind.MANIFEST,
        ModuleWorkbenchReleaseBundleEntryKind.WORKBENCH_ARCHIVE,
        ModuleWorkbenchReleaseBundleEntryKind.WORKBENCH_ARCHIVE,
        ModuleWorkbenchReleaseBundleEntryKind.DIFF,
        ModuleWorkbenchReleaseBundleEntryKind.POLICY,
        ModuleWorkbenchReleaseBundleEntryKind.REVIEW,
    )
    media_types = (
        "application/json",
        "application/zip",
        "application/zip",
        "application/json",
        "application/json",
        "text/markdown",
    )
    entry_ids = ("manifest", "previous", "current", "diff", "policy", "review")
    entries = tuple(
        _entry(index, path, kinds[index], payload, media_types[index], entry_ids[index])
        for index, (path, payload) in enumerate(members)
    )
    body = {
        "bundle_id": bundle_id,
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY,
        "bundle_format": MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT,
        "previous_archive_address": previous_address,
        "current_archive_address": current_address,
        "diff_address": selected_diff.content_address,
        "policy_gate_address": selected_gate.content_address,
        "bundle_address": hash_bytes(raw, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX),
        "bundle_byte_count": len(raw),
        "entry_count": len(entries),
        "entries": entries,
        "state": ModuleWorkbenchReleaseBundleState.ACCEPTED
        if accepted
        else ModuleWorkbenchReleaseBundleState.BLOCKED,
        "accepted": accepted,
    }
    provisional = ModuleWorkbenchReleaseBundle(**body, content_address="pending", bundle_bytes=raw)
    return ModuleWorkbenchReleaseBundle(
        **body,
        content_address=address_module_workbench_release_bundle(provisional),
        bundle_bytes=raw,
    )


def module_workbench_release_bundle_bytes(value: ModuleWorkbenchReleaseBundle) -> bytes:
    verify_module_workbench_release_bundle_value(value)
    return value.bundle_bytes


def write_module_workbench_release_bundle(
    value: ModuleWorkbenchReleaseBundle,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundle:
    verify_module_workbench_release_bundle_value(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("release bundle destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("release bundle destination is not a file")
    _validate_parent(path.parent, "release bundle destination")
    atomic_write_bytes(path, value.bundle_bytes, field="release bundle destination")
    return value


def _zip_infos(raw: bytes) -> tuple[zipfile.ZipInfo, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return tuple(handle.infolist())
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read release bundle ZIP: {exc}") from exc


def _read_members(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return {info.filename: handle.read(info) for info in handle.infolist()}
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read release bundle members: {exc}") from exc


def _manifest_payload(members: Mapping[str, bytes]) -> Mapping[str, Any] | None:
    raw = members.get(MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST)
    if raw is None:
        return None
    try:
        value = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, Mapping) else None


def _check(
    check_id: str,
    plane: ModuleWorkbenchReleaseBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCheck(
        **body,
        content_address=address_module_workbench_release_bundle_check(provisional),
    )


def _verification(
    bundle_id: str,
    bundle_address: str,
    names: tuple[str, ...],
    checks: list[ModuleWorkbenchReleaseBundleCheck],
) -> ModuleWorkbenchReleaseBundleVerification:
    expected = {
        MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
        MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY,
        MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW,
    }
    actual = set(names)
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {
        "bundle_id": bundle_id,
        "bundle_address": bundle_address,
        "entry_count": MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES,
        "present_count": len(expected & actual),
        "missing_count": len(expected - actual),
        "checks": ordered,
        "accepted": bool(ordered) and all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchReleaseBundleVerification(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleVerification(
        **body,
        content_address=address_module_workbench_release_bundle_verification(provisional),
    )


def verify_module_workbench_release_bundle(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleVerification:
    """Verify ZIP safety, exact nested artifacts, and all address links."""

    raw = _read_bundle(value)
    bundle_address = hash_bytes(raw, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX)
    checks: list[ModuleWorkbenchReleaseBundleCheck] = []
    names: tuple[str, ...] = ()
    members: dict[str, bytes] = {}
    bundle_id = "unavailable"
    try:
        infos = _zip_infos(raw)
        names = tuple(info.filename for info in infos)
        members = _read_members(raw)
        zip_ok = True
    except ValidationError:
        infos = ()
        zip_ok = False
    checks.append(
        _check(
            "zip-readable",
            ModuleWorkbenchReleaseBundleCheckPlane.ZIP,
            zip_ok,
            "readable" if zip_ok else "unreadable",
            "readable",
            "bundle ZIP members are readable",
        )
    )
    duplicates = tuple(sorted(name for name in set(names) if names.count(name) > 1))
    checks.append(
        _check(
            "unique-members",
            ModuleWorkbenchReleaseBundleCheckPlane.ZIP,
            not duplicates,
            duplicates,
            (),
            "bundle member names are unique",
        )
    )
    unsafe = tuple(sorted(name for name in names if not _safe_path(name)))
    checks.append(
        _check(
            "safe-paths",
            ModuleWorkbenchReleaseBundleCheckPlane.PATH,
            not unsafe,
            unsafe,
            (),
            "bundle member paths are relative and traversal-free",
        )
    )
    special = tuple(
        sorted(
            info.filename
            for info in infos
            if info.is_dir()
            or (info.create_system == 3 and stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF))
        )
    )
    checks.append(
        _check(
            "regular-members",
            ModuleWorkbenchReleaseBundleCheckPlane.ZIP,
            not special,
            special,
            (),
            "bundle contains regular files only",
        )
    )
    manifest = _manifest_payload(members) if zip_ok else None
    if manifest is not None:
        bundle_id = str(manifest.get("bundle_id", "unavailable"))
    checks.append(
        _check(
            "manifest-present",
            ModuleWorkbenchReleaseBundleCheckPlane.MANIFEST,
            manifest is not None,
            "present" if manifest is not None else "missing-or-invalid",
            "present",
            "bundle has a readable manifest",
        )
    )
    manifest_raw = members.get(MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST, b"")
    checks.append(
        _check(
            "manifest-canonical",
            ModuleWorkbenchReleaseBundleCheckPlane.MANIFEST,
            manifest is not None
            and manifest_raw == (canonical_json(manifest) + "\n").encode(_UTF8),
            "canonical"
            if manifest is not None
            and manifest_raw == (canonical_json(manifest) + "\n").encode(_UTF8)
            else "non-canonical",
            "canonical",
            "manifest is canonical UTF-8 JSON",
        )
    )
    expected = {
        MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
        MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY,
        MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW,
    }
    checks.append(
        _check(
            "declared-members",
            ModuleWorkbenchReleaseBundleCheckPlane.MANIFEST,
            manifest is not None and set(names) == expected,
            {"missing": sorted(expected - set(names)), "extra": sorted(set(names) - expected)},
            {"missing": [], "extra": []},
            "bundle contains the exact six-member allowlist",
        )
    )
    nested: dict[str, Any] = {}
    nested_errors: dict[str, str] = {}
    for path, loader in (
        (MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS, verify_module_workbench_archive),
        (MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT, verify_module_workbench_archive),
    ):
        try:
            nested[path] = loader(members[path])
        except (KeyError, ValidationError) as exc:
            nested_errors[path] = str(exc)
    checks.append(
        _check(
            "nested-archives",
            ModuleWorkbenchReleaseBundleCheckPlane.ARCHIVE,
            len(nested) == 2 and all(item.accepted for item in nested.values()),
            "verified" if len(nested) == 2 else nested_errors,
            "verified",
            "both nested workbench archives verify structurally",
        )
    )
    try:
        nested_diff = load_module_workbench_archive_diff(
            members[MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF]
        )
        nested_policy = load_module_workbench_archive_diff_policy_gate(
            members[MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY]
        )
        diff_ok = True
    except (KeyError, ValidationError) as exc:
        nested_diff = None
        nested_policy = None
        diff_ok = False
        nested_errors["decision"] = str(exc)
    checks.append(
        _check(
            "nested-decisions",
            ModuleWorkbenchReleaseBundleCheckPlane.DIFF,
            diff_ok,
            "verified" if diff_ok else nested_errors,
            "verified",
            "diff and policy documents reload canonically",
        )
    )
    link_ok = bool(manifest and nested_diff and nested_policy)
    if link_ok:
        link_ok = (
            str(manifest.get("previous_archive_address"))
            == nested_diff.previous_archive_address
            == hash_bytes(
                members[MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS], prefix="module-workbench-archive"
            )
            and str(manifest.get("current_archive_address"))
            == nested_diff.current_archive_address
            == hash_bytes(
                members[MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT], prefix="module-workbench-archive"
            )
            and str(manifest.get("diff_address")) == nested_diff.content_address
            and str(manifest.get("policy_gate_address")) == nested_policy.content_address
            and nested_policy.diff_address == nested_diff.content_address
        )
    checks.append(
        _check(
            "address-links",
            ModuleWorkbenchReleaseBundleCheckPlane.ARCHIVE,
            link_ok,
            "conserved" if link_ok else "mismatch",
            "conserved",
            "manifest, archives, diff, and policy gate addresses agree",
        )
    )
    review_raw = members.get(MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW, b"")
    review_ok = bool(
        nested_diff
        and nested_policy
        and review_raw
        == _review_bytes(
            nested_diff,
            nested_policy,
            str(manifest.get("previous_archive_address")) if manifest else "unavailable",
            str(manifest.get("current_archive_address")) if manifest else "unavailable",
        )
    )
    checks.append(
        _check(
            "review-replay",
            ModuleWorkbenchReleaseBundleCheckPlane.DIFF,
            review_ok,
            "replayed" if review_ok else "mismatch",
            "replayed",
            "review Markdown is regenerated from nested decisions",
        )
    )
    byte_failures = []
    if manifest is not None:
        if manifest.get("review_byte_count") != len(review_raw) or manifest.get(
            "review_line_count"
        ) != _line_count(review_raw):
            byte_failures.append("review")
    checks.append(
        _check(
            "member-bytes",
            ModuleWorkbenchReleaseBundleCheckPlane.BYTES,
            not byte_failures,
            byte_failures,
            [],
            "declared member byte metadata is stable",
        )
    )
    public_ok = (
        manifest is not None
        and nested_diff is not None
        and nested_policy is not None
        and not _has_forbidden_key(manifest)
        and not _has_forbidden_key(nested_diff.to_dict())
        and not _has_forbidden_key(nested_policy.to_dict())
    )
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchReleaseBundleCheckPlane.PUBLIC,
            public_ok,
            "clean" if public_ok else "forbidden-or-invalid",
            "clean",
            "bundle contains only public aggregate evidence",
        )
    )
    return _verification(bundle_id, bundle_address, names, checks)


def verify_module_workbench_release_bundle_value(
    value: ModuleWorkbenchReleaseBundle,
) -> ModuleWorkbenchReleaseBundle:
    if not isinstance(value, ModuleWorkbenchReleaseBundle):
        raise ValidationError("typed release bundle verification requires a bundle")
    if (
        hash_bytes(value.bundle_bytes, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX)
        != value.bundle_address
    ):
        raise ValidationError("release bundle binary address mismatch")
    if address_module_workbench_release_bundle(value) != value.content_address:
        raise ValidationError("release bundle descriptor address mismatch")
    return value


def _entry_from_payload(index: int, name: str, payload: bytes) -> ModuleWorkbenchReleaseBundleEntry:
    kinds = {
        MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST: ModuleWorkbenchReleaseBundleEntryKind.MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS: (
            ModuleWorkbenchReleaseBundleEntryKind.WORKBENCH_ARCHIVE
        ),
        MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT: (
            ModuleWorkbenchReleaseBundleEntryKind.WORKBENCH_ARCHIVE
        ),
        MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF: ModuleWorkbenchReleaseBundleEntryKind.DIFF,
        MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY: ModuleWorkbenchReleaseBundleEntryKind.POLICY,
        MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW: ModuleWorkbenchReleaseBundleEntryKind.REVIEW,
    }
    media = (
        "text/markdown"
        if name.endswith(".md")
        else "application/zip"
        if name.endswith(".zip")
        else "application/json"
    )
    entry_ids = {
        MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST: "manifest",
        MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS: "previous",
        MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT: "current",
        MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF: "diff",
        MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY: "policy",
        MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW: "review",
    }
    return _entry(index, name, kinds[name], payload, media, entry_ids[name])


def load_module_workbench_release_bundle(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundle:
    verification = verify_module_workbench_release_bundle(value)
    if not verification.accepted:
        raise ValidationError("cannot load malformed release bundle")
    raw = _read_bundle(value)
    members = _read_members(raw)
    manifest = _manifest_payload(members)
    if manifest is None:
        raise ValidationError("release bundle manifest is unavailable")
    entries = tuple(
        _entry_from_payload(index, name, members[name])
        for index, name in enumerate(
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST,
                MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS,
                MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT,
                MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
                MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY,
                MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW,
            )
        )
    )
    body = {
        "bundle_id": str(manifest.get("bundle_id")),
        "version": str(manifest.get("version")),
        "boundary": str(manifest.get("boundary")),
        "bundle_format": str(manifest.get("bundle_format")),
        "previous_archive_address": str(manifest.get("previous_archive_address")),
        "current_archive_address": str(manifest.get("current_archive_address")),
        "diff_address": str(manifest.get("diff_address")),
        "policy_gate_address": str(manifest.get("policy_gate_address")),
        "bundle_address": hash_bytes(raw, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX),
        "bundle_byte_count": len(raw),
        "entry_count": len(entries),
        "entries": entries,
        "state": ModuleWorkbenchReleaseBundleState(str(manifest.get("state"))),
        "accepted": bool(manifest.get("accepted")),
    }
    provisional = ModuleWorkbenchReleaseBundle(**body, content_address="pending", bundle_bytes=raw)
    return ModuleWorkbenchReleaseBundle(
        **body,
        content_address=address_module_workbench_release_bundle(provisional),
        bundle_bytes=raw,
    )


def query_module_workbench_release_bundle(
    value: ModuleWorkbenchReleaseBundle | bytes | bytearray | str | Path,
    *,
    resource: str = "entries",
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_LIMIT:
        raise ValidationError("release bundle paging is invalid")
    bundle = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundle)
        else load_module_workbench_release_bundle(value)
    )
    verify_module_workbench_release_bundle_value(bundle)
    if resource == "entries":
        rows = [item.to_dict() for item in bundle.entries]
    elif resource == "summary":
        rows = [bundle.to_dict(include_entries=False)]
    else:
        raise ValidationError("release bundle resource must be entries or summary")
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "bundle_address": bundle.bundle_address,
        "resource": resource,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": bundle.accepted,
    }
    return body | {
        "content_address": content_hash(body, prefix="module-workbench-release-bundle-query")
    }


def module_workbench_release_bundle_json(value: ModuleWorkbenchReleaseBundle) -> str:
    verify_module_workbench_release_bundle_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_csv(value: ModuleWorkbenchReleaseBundle) -> str:
    result = query_module_workbench_release_bundle(value)
    output = io.StringIO(newline="")
    fields = tuple(sorted({key for row in result["items"] for key in row}))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_markdown(value: ModuleWorkbenchReleaseBundle) -> str:
    verify_module_workbench_release_bundle_value(value)
    lines = [
        "# Module Workbench Release Evidence",
        "",
        f"- Bundle: `{value.bundle_id}`",
        f"- Bundle address: `{value.bundle_address}`",
        f"- Previous archive: `{value.previous_archive_address}`",
        f"- Current archive: `{value.current_archive_address}`",
        f"- Diff: `{value.diff_address}`",
        f"- Policy gate: `{value.policy_gate_address}`",
        f"- Bytes: {value.bundle_byte_count}",
        f"- State: `{value.state.value}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Ordinal | Member | Kind | Bytes | Address |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.relative_path}` | `{item.kind.value}` "
        f"| {item.byte_count} | `{item.content_address}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY,
        "format": MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT,
        "members": [
            MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST,
            MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT,
            MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
            MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY,
            MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW,
        ],
        "resources": ["entries", "summary"],
        "max_entries": MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES,
        "max_bytes": MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_capabilities() -> dict[str, Any]:
    operations = (
        "bundle_two_workbench_archives",
        "bundle_archive_diff",
        "bundle_policy_gate",
        "generate_review_projection",
        "verify_nested_archives",
        "verify_nested_decisions",
        "verify_address_links",
        "verify_public_boundary",
        "load_without_source_access",
        "query_entries",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


__all__ = [
    "build_module_workbench_release_bundle",
    "load_module_workbench_release_bundle",
    "module_workbench_release_bundle_bytes",
    "module_workbench_release_bundle_capabilities",
    "module_workbench_release_bundle_csv",
    "module_workbench_release_bundle_json",
    "module_workbench_release_bundle_schema",
    "query_module_workbench_release_bundle",
    "render_module_workbench_release_bundle_markdown",
    "verify_module_workbench_release_bundle",
    "verify_module_workbench_release_bundle_value",
    "write_module_workbench_release_bundle",
]
