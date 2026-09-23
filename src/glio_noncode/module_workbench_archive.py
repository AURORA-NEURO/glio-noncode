"""Build, verify, reload, and query portable module workbench archives."""

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
from .module_workbench import query_module_workbench, verify_module_workbench
from .module_workbench_contracts import (
    ModuleWorkbenchAssessment,
    ModuleWorkbenchDepthBand,
    ModuleWorkbenchDimension,
    ModuleWorkbenchFamilyRollup,
    ModuleWorkbenchReport,
    ModuleWorkbenchRisk,
    ModuleWorkbenchTask,
    ModuleWorkbenchTaskKind,
)
from .module_workbench_archive_contracts import (
    MODULE_WORKBENCH_ARCHIVE_BOUNDARY,
    MODULE_WORKBENCH_ARCHIVE_CHECK_PREFIX,
    MODULE_WORKBENCH_ARCHIVE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_ARCHIVE_ENTRY_PREFIX,
    MODULE_WORKBENCH_ARCHIVE_FORMAT,
    MODULE_WORKBENCH_ARCHIVE_MANIFEST,
    MODULE_WORKBENCH_ARCHIVE_MAX_BYTES,
    MODULE_WORKBENCH_ARCHIVE_MAX_CHECKS,
    MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES,
    MODULE_WORKBENCH_ARCHIVE_MAX_LIMIT,
    MODULE_WORKBENCH_ARCHIVE_PREFIX,
    MODULE_WORKBENCH_ARCHIVE_REPORT,
    MODULE_WORKBENCH_ARCHIVE_VERSION,
    ModuleWorkbenchArchive,
    ModuleWorkbenchArchiveCheck,
    ModuleWorkbenchArchiveCheckPlane,
    ModuleWorkbenchArchiveEntry,
    ModuleWorkbenchArchiveEntryKind,
    ModuleWorkbenchArchiveState,
    ModuleWorkbenchArchiveVerification,
    address_module_workbench_archive,
    address_module_workbench_archive_check,
    address_module_workbench_archive_entry,
    address_module_workbench_archive_verification,
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
    parts = tuple(value.split("/"))
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _line_count(payload: bytes) -> int:
    try:
        return len(payload.decode(_UTF8).splitlines())
    except UnicodeDecodeError:
        return 0


def _zip_member(name: str) -> zipfile.ZipInfo:
    if not _safe_path(name):
        raise ValidationError(f"unsafe workbench archive member: {name}")
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


def _read_archive(value: bytes | bytearray | str | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, (str, Path)):
        try:
            raw = read_bytes(value, field="module workbench archive", max_bytes=MODULE_WORKBENCH_ARCHIVE_MAX_BYTES)
        except (OSError, ValidationError) as exc:
            raise ValidationError(f"cannot read module workbench archive: {exc}") from exc
    else:
        raise ValidationError("module workbench archive input must be bytes or a path")
    if len(raw) > MODULE_WORKBENCH_ARCHIVE_MAX_BYTES:
        raise ValidationError("module workbench archive exceeds byte limit")
    return raw


def _report(value: ModuleWorkbenchReport) -> ModuleWorkbenchReport:
    if not isinstance(value, ModuleWorkbenchReport):
        raise ValidationError("module workbench archive requires a typed report")
    return verify_module_workbench(value)


def _report_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReport:
    """Restore a report without source access, then verify every nested address."""

    def mapping(item: Any, field: str) -> Mapping[str, Any]:
        if not isinstance(item, Mapping):
            raise ValidationError(f"{field} must be an object")
        return item

    dimensions: dict[str, tuple[ModuleWorkbenchDimension, ...]] = {}
    assessments: list[ModuleWorkbenchAssessment] = []
    raw_assessments = value.get("assessments")
    if not isinstance(raw_assessments, list):
        raise ValidationError("workbench archive assessments are invalid")
    for raw in raw_assessments:
        row = mapping(raw, "assessment")
        raw_dimensions = row.get("dimensions")
        if not isinstance(raw_dimensions, list):
            raise ValidationError("workbench assessment dimensions are invalid")
        dimensions[row.get("module_id", "")] = tuple(
            ModuleWorkbenchDimension(
                name=str(item.get("name", "")),
                score=item.get("score"),
                observed=item.get("observed"),
                target=item.get("target"),
                detail=str(item.get("detail", "")),
                content_address=str(item.get("content_address", "")),
            )
            for item in (mapping(item, "dimension") for item in raw_dimensions)
        )
        assessments.append(
            ModuleWorkbenchAssessment(
                module_id=str(row.get("module_id", "")),
                family=str(row.get("family", "")),
                role=str(row.get("role", "")),
                state=str(row.get("state", "")),
                physical_lines=row.get("physical_lines"),
                nonblank_lines=row.get("nonblank_lines"),
                public_symbol_count=row.get("public_symbol_count"),
                function_count=row.get("function_count"),
                class_count=row.get("class_count"),
                import_count=row.get("import_count"),
                local_dependency_count=row.get("local_dependency_count"),
                fan_in=row.get("fan_in"),
                fan_out=row.get("fan_out"),
                test_reference_count=row.get("test_reference_count"),
                evidence_count=row.get("evidence_count"),
                evidence_kinds=tuple(row.get("evidence_kinds", ())),
                dimensions=dimensions[str(row.get("module_id", ""))],
                score=row.get("score"),
                depth_band=ModuleWorkbenchDepthBand(str(row.get("depth_band"))),
                risk=ModuleWorkbenchRisk(str(row.get("risk"))),
                blockers=tuple(row.get("blockers", ())),
                strengths=tuple(row.get("strengths", ())),
                source_address=str(row.get("source_address", "")),
                content_address=str(row.get("content_address", "")),
            )
        )
    raw_tasks = value.get("tasks")
    if not isinstance(raw_tasks, list):
        raise ValidationError("workbench archive tasks are invalid")
    tasks = tuple(
        ModuleWorkbenchTask(
            task_id=str(row.get("task_id", "")),
            module_id=str(row.get("module_id", "")),
            kind=ModuleWorkbenchTaskKind(str(row.get("kind"))),
            priority=row.get("priority"),
            title=str(row.get("title", "")),
            rationale=str(row.get("rationale", "")),
            acceptance=str(row.get("acceptance", "")),
            estimated_impact=row.get("estimated_impact"),
            evidence=tuple(row.get("evidence", ())),
            content_address=str(row.get("content_address", "")),
        )
        for row in (mapping(item, "task") for item in raw_tasks)
    )
    raw_families = value.get("families")
    if not isinstance(raw_families, list):
        raise ValidationError("workbench archive families are invalid")
    families = tuple(
        ModuleWorkbenchFamilyRollup(
            family=str(row.get("family", "")),
            module_count=row.get("module_count"),
            deep_count=row.get("deep_count"),
            comprehensive_count=row.get("comprehensive_count"),
            blocked_count=row.get("blocked_count"),
            high_risk_count=row.get("high_risk_count"),
            average_score=row.get("average_score"),
            average_test_references=row.get("average_test_references"),
            average_evidence=row.get("average_evidence"),
            average_fan_out=row.get("average_fan_out"),
            top_task_kinds=tuple(row.get("top_task_kinds", ())),
            content_address=str(row.get("content_address", "")),
        )
        for row in (mapping(item, "family") for item in raw_families)
    )
    report = ModuleWorkbenchReport(
        inventory_address=str(value.get("inventory_address", "")),
        matrix_address=str(value.get("matrix_address", "")),
        lineage_address=str(value.get("lineage_address", "")),
        quality_address=str(value.get("quality_address", "")),
        assessments=tuple(assessments),
        tasks=tasks,
        families=families,
        overall_score=value.get("overall_score"),
        overall_percent=value.get("overall_percent"),
        depth_percent=value.get("depth_percent"),
        deep_count=value.get("deep_count"),
        comprehensive_count=value.get("comprehensive_count"),
        starter_count=value.get("starter_count"),
        blocked_count=value.get("blocked_count"),
        high_risk_count=value.get("high_risk_count"),
        risk_counts=value.get("risk_counts"),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    return verify_module_workbench(report)


def _check(
    check_id: str,
    plane: ModuleWorkbenchArchiveCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchArchiveCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchArchiveCheck(**body, content_address="pending")
    return ModuleWorkbenchArchiveCheck(
        **body,
        content_address=address_module_workbench_archive_check(provisional),
    )


def _manifest_bytes(
    archive_id: str,
    report: ModuleWorkbenchReport,
    report_bytes: bytes,
) -> bytes:
    body = {
        "archive_id": archive_id,
        "version": MODULE_WORKBENCH_ARCHIVE_VERSION,
        "boundary": MODULE_WORKBENCH_ARCHIVE_BOUNDARY,
        "archive_format": MODULE_WORKBENCH_ARCHIVE_FORMAT,
        "workbench_address": report.content_address,
        "report_path": MODULE_WORKBENCH_ARCHIVE_REPORT,
        "report_address": report.content_address,
        "report_byte_count": len(report_bytes),
        "report_line_count": _line_count(report_bytes),
        "state": ModuleWorkbenchArchiveState.ACCEPTED
        if report.accepted
        else ModuleWorkbenchArchiveState.BLOCKED,
        "accepted": report.accepted,
    }
    return (canonical_json(body) + "\n").encode(_UTF8)


def _archive_bytes(manifest_bytes: bytes, report_bytes: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as handle:
        handle.writestr(_zip_member(MODULE_WORKBENCH_ARCHIVE_MANIFEST), manifest_bytes)
        handle.writestr(_zip_member(MODULE_WORKBENCH_ARCHIVE_REPORT), report_bytes)
    return output.getvalue()


def _entry(
    entry_id: str,
    relative_path: str,
    kind: ModuleWorkbenchArchiveEntryKind,
    payload: bytes,
    ordinal: int,
    media_type: str,
) -> ModuleWorkbenchArchiveEntry:
    body = {
        "entry_id": entry_id,
        "relative_path": relative_path,
        "kind": kind,
        "media_type": media_type,
        "ordinal": ordinal,
        "byte_count": len(payload),
        "line_count": _line_count(payload),
    }
    return ModuleWorkbenchArchiveEntry(
        **body,
        content_address=hash_bytes(payload, prefix=MODULE_WORKBENCH_ARCHIVE_ENTRY_PREFIX),
    )


def build_module_workbench_archive(
    value: ModuleWorkbenchReport,
    *,
    archive_id: str = "glio-noncode-module-workbench-archive",
) -> ModuleWorkbenchArchive:
    """Build deterministic ZIP_STORED bytes for a complete workbench report."""

    if not isinstance(archive_id, str) or not archive_id.strip():
        raise ValidationError("module workbench archive ID is required")
    report = _report(value)
    report_bytes = (canonical_json(report.to_dict()) + "\n").encode(_UTF8)
    manifest_bytes = _manifest_bytes(archive_id, report, report_bytes)
    raw = _archive_bytes(manifest_bytes, report_bytes)
    entries = (
        _entry(
            "manifest",
            MODULE_WORKBENCH_ARCHIVE_MANIFEST,
            ModuleWorkbenchArchiveEntryKind.MANIFEST,
            manifest_bytes,
            0,
            "application/json",
        ),
        _entry(
            "workbench",
            MODULE_WORKBENCH_ARCHIVE_REPORT,
            ModuleWorkbenchArchiveEntryKind.REPORT,
            report_bytes,
            1,
            "application/json",
        ),
    )
    body = {
        "archive_id": archive_id,
        "version": MODULE_WORKBENCH_ARCHIVE_VERSION,
        "boundary": MODULE_WORKBENCH_ARCHIVE_BOUNDARY,
        "archive_format": MODULE_WORKBENCH_ARCHIVE_FORMAT,
        "workbench_address": report.content_address,
        "archive_address": hash_bytes(raw, prefix=MODULE_WORKBENCH_ARCHIVE_PREFIX),
        "archive_byte_count": len(raw),
        "report_byte_count": len(report_bytes),
        "entry_count": len(entries),
        "entries": entries,
        "state": ModuleWorkbenchArchiveState.ACCEPTED
        if report.accepted
        else ModuleWorkbenchArchiveState.BLOCKED,
        "accepted": report.accepted,
    }
    provisional = ModuleWorkbenchArchive(
        **body,
        content_address="pending",
        archive_bytes=raw,
    )
    return ModuleWorkbenchArchive(
        **body,
        content_address=address_module_workbench_archive(provisional),
        archive_bytes=raw,
    )


def module_workbench_archive_bytes(value: ModuleWorkbenchArchive) -> bytes:
    verify_module_workbench_archive_value(value)
    return value.archive_bytes


def write_module_workbench_archive(
    value: ModuleWorkbenchArchive | ModuleWorkbenchReport,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchArchive:
    """Write exact archive bytes atomically."""

    archive = value if isinstance(value, ModuleWorkbenchArchive) else build_module_workbench_archive(value)
    verify_module_workbench_archive_value(archive)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module workbench archive destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("module workbench archive destination is not a file")
    _validate_parent(path.parent, "module workbench archive destination")
    atomic_write_bytes(path, archive.archive_bytes, field="module workbench archive destination")
    return archive


def _zip_infos(raw: bytes) -> tuple[zipfile.ZipInfo, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return tuple(handle.infolist())
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read module workbench archive ZIP: {exc}") from exc


def _read_members(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return {info.filename: handle.read(info) for info in handle.infolist()}
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read module workbench archive members: {exc}") from exc


def _manifest_payload(members: Mapping[str, bytes]) -> Mapping[str, Any] | None:
    payload = members.get(MODULE_WORKBENCH_ARCHIVE_MANIFEST)
    if payload is None:
        return None
    try:
        parsed = _strict_json_loads(payload.decode(_UTF8))
    except (UnicodeDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _verification(
    archive_id: str,
    workbench_address: str,
    archive_address: str,
    entry_count: int,
    present_count: int,
    missing_count: int,
    checks: list[ModuleWorkbenchArchiveCheck],
) -> ModuleWorkbenchArchiveVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    if len(ordered) > MODULE_WORKBENCH_ARCHIVE_MAX_CHECKS:
        raise ValidationError("workbench archive produced too many checks")
    body = {
        "archive_id": archive_id,
        "workbench_address": workbench_address,
        "archive_address": archive_address,
        "entry_count": entry_count,
        "present_count": present_count,
        "missing_count": missing_count,
        "checks": ordered,
        "accepted": bool(ordered) and all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchArchiveVerification(**body, content_address="pending")
    return ModuleWorkbenchArchiveVerification(
        **body,
        content_address=address_module_workbench_archive_verification(provisional),
    )


def verify_module_workbench_archive(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchArchiveVerification:
    """Verify ZIP safety, canonical manifest, exact report bytes, and report addresses."""

    raw = _read_archive(value)
    archive_address = hash_bytes(raw, prefix=MODULE_WORKBENCH_ARCHIVE_PREFIX)
    checks: list[ModuleWorkbenchArchiveCheck] = []
    archive_id = "unavailable"
    workbench_address = "unavailable"
    infos: tuple[zipfile.ZipInfo, ...] = ()
    members: dict[str, bytes] = {}
    try:
        infos = _zip_infos(raw)
        members = _read_members(raw)
        zip_ok = True
        zip_detail = "ZIP members are readable"
    except ValidationError as exc:
        zip_ok = False
        zip_detail = str(exc)
    checks.append(_check("zip-readable", ModuleWorkbenchArchiveCheckPlane.ZIP, zip_ok, "readable" if zip_ok else "unreadable", "readable", zip_detail))
    names = tuple(info.filename for info in infos)
    duplicate_names = tuple(sorted(name for name in set(names) if names.count(name) > 1))
    checks.append(_check("unique-members", ModuleWorkbenchArchiveCheckPlane.ZIP, not duplicate_names, duplicate_names, (), "archive member names are unique"))
    unsafe_names = tuple(sorted(name for name in names if not _safe_path(name)))
    checks.append(_check("safe-paths", ModuleWorkbenchArchiveCheckPlane.PATH, not unsafe_names, unsafe_names, (), "archive member paths are relative and traversal-free"))
    special_names = tuple(sorted(info.filename for info in infos if info.is_dir() or (info.create_system == 3 and stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF))))
    checks.append(_check("regular-members", ModuleWorkbenchArchiveCheckPlane.ZIP, not special_names, special_names, (), "archive contains regular files only"))
    manifest = _manifest_payload(members) if zip_ok else None
    checks.append(_check("manifest-present", ModuleWorkbenchArchiveCheckPlane.MANIFEST, manifest is not None, "present" if manifest is not None else "missing-or-invalid", "present", "archive has a readable JSON manifest"))
    if manifest is not None:
        archive_id = str(manifest.get("archive_id", "unavailable"))
        workbench_address = str(manifest.get("workbench_address", "unavailable"))
    manifest_raw = members.get(MODULE_WORKBENCH_ARCHIVE_MANIFEST, b"")
    canonical_manifest = manifest is not None and manifest_raw == (canonical_json(manifest) + "\n").encode(_UTF8)
    checks.append(_check("manifest-canonical", ModuleWorkbenchArchiveCheckPlane.MANIFEST, canonical_manifest, "canonical" if canonical_manifest else "non-canonical", "canonical", "manifest bytes are canonical UTF-8 JSON"))
    expected_names = {MODULE_WORKBENCH_ARCHIVE_MANIFEST, MODULE_WORKBENCH_ARCHIVE_REPORT}
    actual_names = set(names)
    missing_names = tuple(sorted(expected_names - actual_names))
    extra_names = tuple(sorted(actual_names - expected_names))
    checks.append(_check("declared-members", ModuleWorkbenchArchiveCheckPlane.MANIFEST, bool(manifest is not None and not missing_names and not extra_names), {"missing": missing_names, "extra": extra_names}, {"missing": (), "extra": ()}, "archive contains exactly manifest and report members"))
    report_raw = members.get(MODULE_WORKBENCH_ARCHIVE_REPORT, b"")
    report = None
    report_error = "unavailable"
    try:
        parsed_report = _strict_json_loads(report_raw.decode(_UTF8))
        if not isinstance(parsed_report, Mapping):
            raise ValidationError("report payload is not an object")
        report = _report_from_mapping(parsed_report)
        report_error = "verified"
    except (UnicodeDecodeError, ValueError, TypeError, ValidationError) as exc:
        report_error = str(exc)
    checks.append(_check("report-hydration", ModuleWorkbenchArchiveCheckPlane.REPORT, report is not None, report_error, "verified", "report restores into the typed workbench contract"))
    report_canonical = report is not None and report_raw == (canonical_json(report.to_dict()) + "\n").encode(_UTF8)
    checks.append(_check("report-canonical", ModuleWorkbenchArchiveCheckPlane.REPORT, report_canonical, "canonical" if report_canonical else "non-canonical", "canonical", "report bytes are canonical UTF-8 JSON"))
    report_address_ok = report is not None and manifest is not None and str(manifest.get("report_address")) == report.content_address == str(manifest.get("workbench_address"))
    checks.append(_check("report-address", ModuleWorkbenchArchiveCheckPlane.REPORT, report_address_ok, report.content_address if report is not None else "unavailable", workbench_address, "manifest and restored report addresses agree"))
    manifest_state_ok = report is not None and manifest is not None and str(manifest.get("state")) == (ModuleWorkbenchArchiveState.ACCEPTED.value if report.accepted else ModuleWorkbenchArchiveState.BLOCKED.value) and bool(manifest.get("accepted")) == report.accepted
    checks.append(_check("report-state", ModuleWorkbenchArchiveCheckPlane.REPORT, manifest_state_ok, report.accepted if report is not None else "unavailable", manifest.get("accepted") if manifest is not None else "unavailable", "report state is conserved"))
    byte_failures: list[str] = []
    if manifest is not None and manifest_raw != (canonical_json(manifest) + "\n").encode(_UTF8):
        byte_failures.append(MODULE_WORKBENCH_ARCHIVE_MANIFEST)
    if report is not None and report_raw != (canonical_json(report.to_dict()) + "\n").encode(_UTF8):
        byte_failures.append(MODULE_WORKBENCH_ARCHIVE_REPORT)
    if manifest is not None:
        if manifest.get("report_byte_count") != len(report_raw):
            byte_failures.append("report_byte_count")
        if manifest.get("report_line_count") != _line_count(report_raw):
            byte_failures.append("report_line_count")
    checks.append(_check("member-bytes", ModuleWorkbenchArchiveCheckPlane.BYTES, not byte_failures, tuple(sorted(byte_failures)), (), "member byte counts and reads are stable"))
    public_ok = manifest is not None and report is not None and not _has_forbidden_key(manifest) and not _has_forbidden_key(report.to_dict())
    checks.append(_check("public-boundary", ModuleWorkbenchArchiveCheckPlane.PUBLIC, public_ok, "clean" if public_ok else "forbidden-or-invalid", "clean", "archive contains only public aggregate report fields"))
    present_count = len(expected_names & actual_names)
    return _verification(archive_id, workbench_address, archive_address, MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES, present_count, len(missing_names), checks)


def verify_module_workbench_archive_value(value: ModuleWorkbenchArchive) -> ModuleWorkbenchArchive:
    if not isinstance(value, ModuleWorkbenchArchive):
        raise ValidationError("typed module workbench archive verification requires an archive")
    if hash_bytes(value.archive_bytes, prefix=MODULE_WORKBENCH_ARCHIVE_PREFIX) != value.archive_address:
        raise ValidationError("module workbench archive binary address mismatch")
    if address_module_workbench_archive(value) != value.content_address:
        raise ValidationError("module workbench archive descriptor address mismatch")
    return value


def load_module_workbench_archive(value: bytes | bytearray | str | Path) -> ModuleWorkbenchReport:
    """Load a verified report without source, tests, or documentation paths."""

    verification = verify_module_workbench_archive(value)
    if not verification.accepted:
        raise ValidationError("cannot load a blocked or malformed module workbench archive")
    members = _read_members(_read_archive(value))
    manifest = _manifest_payload(members)
    if manifest is None:
        raise ValidationError("module workbench archive manifest is unavailable")
    raw_report = _strict_json_loads(members[MODULE_WORKBENCH_ARCHIVE_REPORT].decode(_UTF8))
    if not isinstance(raw_report, Mapping):
        raise ValidationError("module workbench archive report is invalid")
    report = _report_from_mapping(raw_report)
    if report.content_address != str(manifest.get("workbench_address")):
        raise ValidationError("module workbench archive report address mismatch")
    return report


def _archive_rows(value: ModuleWorkbenchArchive, resource: str) -> list[dict[str, Any]]:
    if resource == "entries":
        return [item.to_dict() for item in value.entries]
    if resource == "summary":
        return [value.to_dict(include_entries=False)]
    raise ValidationError("archive resource must be entries or summary")


def query_module_workbench_archive(
    value: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
    *,
    resource: str = "entries",
    module_id: str | None = None,
    family: str | None = None,
    depth_band: str | None = None,
    risk: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_ARCHIVE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Query archive metadata or its reloaded report with bounded pagination."""

    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_ARCHIVE_MAX_LIMIT:
        raise ValidationError("module workbench archive paging is invalid")
    archive = value if isinstance(value, ModuleWorkbenchArchive) else build_module_workbench_archive(load_module_workbench_archive(value))
    verify_module_workbench_archive_value(archive)
    if resource in {"entries", "summary"}:
        rows = _archive_rows(archive, resource)
        if text:
            rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
        body = {"archive_address": archive.archive_address, "resource": resource, "text": text, "total": len(rows), "offset": offset, "limit": limit, "items": rows[offset : offset + limit], "accepted": True}
    else:
        report = load_module_workbench_archive(archive.archive_bytes)
        result = query_module_workbench(report, resource=resource, module_id=module_id, family=family, depth_band=depth_band, risk=risk, kind=kind, text=text, offset=offset, limit=limit)
        body = dict(result)
        body["archive_address"] = archive.archive_address
    return body | {"content_address": content_hash(body, prefix="module-workbench-archive-query")}


def module_workbench_archive_json(value: ModuleWorkbenchArchive) -> str:
    verify_module_workbench_archive_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_archive_csv(
    value: ModuleWorkbenchArchive,
    resource: str = "entries",
    *,
    module_id: str | None = None,
    family: str | None = None,
    depth_band: str | None = None,
    risk: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_ARCHIVE_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_archive(
        value,
        resource=resource,
        module_id=module_id,
        family=family,
        depth_band=depth_band,
        risk=risk,
        kind=kind,
        text=text,
        offset=offset,
        limit=limit,
    )
    rows = result["items"]
    if not rows:
        return ""
    columns = tuple(sorted({key for row in rows for key in row}))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: canonical_json(value) if isinstance(value, (dict, list)) else value for key, value in row.items()} for row in rows)
    return output.getvalue()


def render_module_workbench_archive_markdown(value: ModuleWorkbenchArchive) -> str:
    verify_module_workbench_archive_value(value)
    lines = [
        "# Module Workbench Archive",
        "",
        f"- Archive: `{value.archive_id}`",
        f"- Workbench address: `{value.workbench_address}`",
        f"- Archive address: `{value.archive_address}`",
        f"- Bytes: {value.archive_byte_count}",
        f"- State: `{value.state.value}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "## Members",
        "",
        "| Ordinal | Path | Kind | Bytes | Address |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    lines.extend(f"| {row.ordinal} | `{row.relative_path}` | `{row.kind.value}` | {row.byte_count} | `{row.content_address}` |" for row in value.entries)
    return "\n".join(lines) + "\n"


def module_workbench_archive_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_ARCHIVE_VERSION,
        "boundary": MODULE_WORKBENCH_ARCHIVE_BOUNDARY,
        "format": MODULE_WORKBENCH_ARCHIVE_FORMAT,
        "members": [MODULE_WORKBENCH_ARCHIVE_MANIFEST, MODULE_WORKBENCH_ARCHIVE_REPORT],
        "resources": ["entries", "summary", "modules", "tasks", "families", "risks"],
        "max_entries": MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES,
        "max_bytes": MODULE_WORKBENCH_ARCHIVE_MAX_BYTES,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_archive_capabilities() -> dict[str, Any]:
    operations = (
        "build_archive",
        "write_archive_atomically",
        "verify_zip_safety",
        "verify_canonical_manifest",
        "verify_report_addresses",
        "verify_public_boundary",
        "load_without_source_access",
        "query_archive_entries",
        "query_archived_modules",
        "query_archived_tasks",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_ARCHIVE_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "path_free": True,
        "timestamp_free": True,
        "source_free_reload": True,
    }


__all__ = [
    "build_module_workbench_archive",
    "load_module_workbench_archive",
    "module_workbench_archive_bytes",
    "module_workbench_archive_capabilities",
    "module_workbench_archive_csv",
    "module_workbench_archive_json",
    "module_workbench_archive_schema",
    "query_module_workbench_archive",
    "render_module_workbench_archive_markdown",
    "verify_module_workbench_archive",
    "verify_module_workbench_archive_value",
    "write_module_workbench_archive",
]
