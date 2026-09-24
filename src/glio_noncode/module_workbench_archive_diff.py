"""Compare portable module workbench archives without source access."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import read_bytes
from .errors import ValidationError
from .module_workbench_archive import (
    _manifest_payload,
    _read_archive,
    _read_members,
    load_module_workbench_archive,
    verify_module_workbench_archive,
    verify_module_workbench_archive_value,
)
from .module_workbench_archive_contracts import ModuleWorkbenchArchive
from .module_workbench_diff import (
    build_module_workbench_diff,
    query_module_workbench_diff,
    verify_module_workbench_diff,
)
from .module_workbench_diff_contracts import (
    ModuleWorkbenchChange,
    ModuleWorkbenchChangeKind,
    ModuleWorkbenchDiff,
)
from .module_workbench_archive_diff_contracts import (
    MODULE_WORKBENCH_ARCHIVE_DIFF_BOUNDARY,
    MODULE_WORKBENCH_ARCHIVE_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_LIMIT,
    MODULE_WORKBENCH_ARCHIVE_DIFF_VERSION,
    ModuleWorkbenchArchiveDiff,
    ModuleWorkbenchArchiveDiffCheck,
    ModuleWorkbenchArchiveDiffCheckPlane,
    ModuleWorkbenchArchiveDiffVerification,
    address_module_workbench_archive_diff,
    address_module_workbench_archive_diff_check,
    address_module_workbench_archive_diff_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 128 * 1024 * 1024


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value


def _archive_context(
    value: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
) -> tuple[str, str, Any]:
    """Return the exact archive address, workbench address, and restored report."""

    if isinstance(value, ModuleWorkbenchArchive):
        verify_module_workbench_archive_value(value)
        raw = value.archive_bytes
        report = load_module_workbench_archive(raw)
        return value.archive_address, value.workbench_address, report
    raw = _read_archive(value)
    verification = verify_module_workbench_archive(raw)
    if not verification.accepted:
        raise ValidationError("archive diff input is malformed or unverifiable")
    report = load_module_workbench_archive(raw)
    members = _read_members(raw)
    manifest = _manifest_payload(members)
    if manifest is None:
        raise ValidationError("archive diff input has no readable manifest")
    archive_address = hash_bytes(raw, prefix="module-workbench-archive")
    workbench_address = _text(manifest.get("workbench_address"), "workbench_address")
    if report.content_address != workbench_address:
        raise ValidationError("archive diff input workbench address is not conserved")
    return archive_address, workbench_address, report


def _check(
    check_id: str,
    plane: ModuleWorkbenchArchiveDiffCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchArchiveDiffCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchArchiveDiffCheck(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiffCheck(
        **body,
        content_address=address_module_workbench_archive_diff_check(provisional),
    )


def build_module_workbench_archive_diff(
    previous: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
    current: ModuleWorkbenchArchive | bytes | bytearray | str | Path,
    *,
    diff_id: str = "glio-noncode-module-workbench-archive-diff",
) -> ModuleWorkbenchArchiveDiff:
    """Build a deterministic comparison from two verified portable reports."""

    _text(diff_id, "diff_id")
    previous_archive, previous_workbench, previous_report = _archive_context(previous)
    current_archive, current_workbench, current_report = _archive_context(current)
    diff = build_module_workbench_diff(previous_report, current_report)
    body = {
        "diff_id": diff_id,
        "previous_archive_address": previous_archive,
        "current_archive_address": current_archive,
        "previous_workbench_address": previous_workbench,
        "current_workbench_address": current_workbench,
        "diff": diff,
        "accepted": diff.accepted,
    }
    provisional = ModuleWorkbenchArchiveDiff(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiff(
        **body,
        content_address=address_module_workbench_archive_diff(provisional),
    )


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _diff_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchDiff:
    raw = _mapping(value.get("diff"), "diff")
    raw_changes = raw.get("changes")
    if not isinstance(raw_changes, list):
        raise ValidationError("archive diff changes are invalid")
    changes = tuple(
        ModuleWorkbenchChange(
            module_id=str(row.get("module_id", "")),
            kind=ModuleWorkbenchChangeKind(str(row.get("kind"))),
            previous_score=row.get("previous_score"),
            current_score=row.get("current_score"),
            previous_depth_band=row.get("previous_depth_band"),
            current_depth_band=row.get("current_depth_band"),
            previous_risk=row.get("previous_risk"),
            current_risk=row.get("current_risk"),
            task_delta=row.get("task_delta"),
            detail=str(row.get("detail", "")),
            content_address=str(row.get("content_address", "")),
        )
        for row in (_mapping(item, "change") for item in raw_changes)
    )
    return ModuleWorkbenchDiff(
        previous_address=str(raw.get("previous_address", "")),
        current_address=str(raw.get("current_address", "")),
        changes=changes,
        added_count=raw.get("added_count"),
        changed_count=raw.get("changed_count"),
        removed_count=raw.get("removed_count"),
        unchanged_count=raw.get("unchanged_count"),
        score_delta=raw.get("score_delta"),
        task_delta=raw.get("task_delta"),
        accepted=raw.get("accepted"),
        content_address=str(raw.get("content_address", "")),
    )


def module_workbench_archive_diff_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchArchiveDiff:
    """Hydrate and verify a JSON comparison produced by this module."""

    diff = _diff_from_mapping(value)
    result = ModuleWorkbenchArchiveDiff(
        diff_id=str(value.get("diff_id", "")),
        previous_archive_address=str(value.get("previous_archive_address", "")),
        current_archive_address=str(value.get("current_archive_address", "")),
        previous_workbench_address=str(value.get("previous_workbench_address", "")),
        current_workbench_address=str(value.get("current_workbench_address", "")),
        diff=diff,
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    verify_module_workbench_archive_diff_value(result)
    return result


def load_module_workbench_archive_diff(
    value: Mapping[str, Any] | bytes | bytearray | str | Path,
) -> ModuleWorkbenchArchiveDiff:
    """Load a canonical source-free comparison document."""

    if isinstance(value, Mapping):
        return module_workbench_archive_diff_from_mapping(value)
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = read_bytes(value, field="module workbench archive diff", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse module workbench archive diff: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("module workbench archive diff must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("module workbench archive diff is not canonical JSON")
    return module_workbench_archive_diff_from_mapping(parsed)


def verify_module_workbench_archive_diff(
    value: ModuleWorkbenchArchiveDiff | Mapping[str, Any] | bytes | bytearray | str | Path,
) -> ModuleWorkbenchArchiveDiffVerification:
    """Run bounded independent checks over a portable comparison."""

    if not isinstance(value, ModuleWorkbenchArchiveDiff):
        try:
            value = load_module_workbench_archive_diff(value)
        except ValidationError as exc:
            return _verification_from_failure(str(exc))
    checks: list[ModuleWorkbenchArchiveDiffCheck] = []
    checks.append(
        _check(
            "input-addresses",
            ModuleWorkbenchArchiveDiffCheckPlane.INPUT,
            bool(value.previous_archive_address and value.current_archive_address),
            (value.previous_archive_address, value.current_archive_address),
            "two archive addresses",
            "both compared inputs retain their exact archive addresses",
        )
    )
    checks.append(
        _check(
            "nested-diff",
            ModuleWorkbenchArchiveDiffCheckPlane.DIFF,
            _nested_diff_ok(value.diff),
            value.diff.content_address,
            "verified",
            "the nested module workbench diff verifies independently",
        )
    )
    checks.append(
        _check(
            "workbench-addresses",
            ModuleWorkbenchArchiveDiffCheckPlane.ADDRESS,
            value.diff.previous_address == value.previous_workbench_address
            and value.diff.current_address == value.current_workbench_address,
            (value.diff.previous_address, value.diff.current_address),
            (value.previous_workbench_address, value.current_workbench_address),
            "nested diff and archive manifests agree on workbench addresses",
        )
    )
    checks.append(
        _check(
            "change-count",
            ModuleWorkbenchArchiveDiffCheckPlane.DIFF,
            value.diff.to_dict(include_changes=False).get("change_count")
            == len(value.diff.changes),
            value.diff.to_dict(include_changes=False).get("change_count"),
            len(value.diff.changes),
            "all change rows are retained",
        )
    )
    checks.append(
        _check(
            "kind-counts",
            ModuleWorkbenchArchiveDiffCheckPlane.DIFF,
            sum(
                (
                    value.diff.added_count,
                    value.diff.changed_count,
                    value.diff.removed_count,
                    value.diff.unchanged_count,
                )
            )
            == len(value.diff.changes),
            {
                "added": value.diff.added_count,
                "changed": value.diff.changed_count,
                "removed": value.diff.removed_count,
                "unchanged": value.diff.unchanged_count,
            },
            len(value.diff.changes),
            "change-kind counts conserve every row",
        )
    )
    checks.append(
        _check(
            "acceptance",
            ModuleWorkbenchArchiveDiffCheckPlane.DIFF,
            value.accepted == value.diff.accepted,
            value.accepted,
            value.diff.accepted,
            "comparison acceptance is conserved from the nested diff",
        )
    )
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchArchiveDiffCheckPlane.PUBLIC,
            not _has_forbidden_key(value.to_dict()),
            "clean" if not _has_forbidden_key(value.to_dict()) else "forbidden-key",
            "clean",
            "comparison contains only public aggregate fields",
        )
    )
    checks.append(
        _check(
            "content-address",
            ModuleWorkbenchArchiveDiffCheckPlane.ADDRESS,
            _content_address_ok(value),
            value.content_address,
            address_module_workbench_archive_diff(value),
            "comparison content address is conserved",
        )
    )
    return _verification(value, checks)


def _nested_diff_ok(value: ModuleWorkbenchDiff) -> bool:
    try:
        verify_module_workbench_diff(value)
    except ValidationError:
        return False
    return True


def _content_address_ok(value: ModuleWorkbenchArchiveDiff) -> bool:
    try:
        return address_module_workbench_archive_diff(value) == value.content_address
    except ValidationError:
        return False


def _verification(
    value: ModuleWorkbenchArchiveDiff,
    checks: list[ModuleWorkbenchArchiveDiffCheck],
) -> ModuleWorkbenchArchiveDiffVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {
        "diff_id": value.diff_id,
        "previous_archive_address": value.previous_archive_address,
        "current_archive_address": value.current_archive_address,
        "change_count": len(value.diff.changes),
        "checks": ordered,
        "accepted": bool(ordered) and all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchArchiveDiffVerification(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiffVerification(
        **body,
        content_address=address_module_workbench_archive_diff_verification(provisional),
    )


def _verification_from_failure(detail: str) -> ModuleWorkbenchArchiveDiffVerification:
    check = _check(
        "load",
        ModuleWorkbenchArchiveDiffCheckPlane.INPUT,
        False,
        detail,
        "verified comparison",
        "comparison could not be loaded",
    )
    body = {
        "diff_id": "unavailable",
        "previous_archive_address": "unavailable",
        "current_archive_address": "unavailable",
        "change_count": 0,
        "checks": (check,),
        "accepted": False,
    }
    provisional = ModuleWorkbenchArchiveDiffVerification(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiffVerification(
        **body,
        content_address=address_module_workbench_archive_diff_verification(provisional),
    )


def verify_module_workbench_archive_diff_value(
    value: ModuleWorkbenchArchiveDiff,
) -> ModuleWorkbenchArchiveDiff:
    if not isinstance(value, ModuleWorkbenchArchiveDiff):
        raise ValidationError("typed archive diff verification requires an archive diff")
    verification = verify_module_workbench_archive_diff(value)
    if not verification.accepted:
        raise ValidationError("module workbench archive diff verification failed")
    return value


def query_module_workbench_archive_diff(
    value: ModuleWorkbenchArchiveDiff | Mapping[str, Any] | bytes | bytearray | str | Path,
    *,
    kind: str | None = None,
    module_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_ARCHIVE_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded source-free page of archive comparison rows."""

    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_LIMIT:
        raise ValidationError("module workbench archive diff paging is invalid")
    if not isinstance(value, ModuleWorkbenchArchiveDiff):
        value = load_module_workbench_archive_diff(value)
    verify_module_workbench_archive_diff_value(value)
    result = query_module_workbench_diff(
        value.diff,
        kind=kind,
        module_id=module_id,
        text=text,
        offset=offset,
        limit=limit,
    )
    result = dict(result)
    result.update(
        {
            "archive_diff_address": value.content_address,
            "previous_archive_address": value.previous_archive_address,
            "current_archive_address": value.current_archive_address,
        }
    )
    return result | {"content_address": content_hash(result, prefix="module-workbench-archive-diff-query")}


def module_workbench_archive_diff_json(value: ModuleWorkbenchArchiveDiff) -> str:
    verify_module_workbench_archive_diff_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_archive_diff_csv(
    value: ModuleWorkbenchArchiveDiff,
    *,
    kind: str | None = None,
    module_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_ARCHIVE_DIFF_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_archive_diff(
        value,
        kind=kind,
        module_id=module_id,
        text=text,
        offset=offset,
        limit=limit,
    )
    rows = result["items"]
    if not rows:
        return ""
    output = io.StringIO()
    fields = tuple(sorted({key for row in rows for key in row}))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_module_workbench_archive_diff_markdown(value: ModuleWorkbenchArchiveDiff) -> str:
    verify_module_workbench_archive_diff_value(value)
    lines = [
        "# Module Workbench Archive Diff",
        "",
        f"- Diff: `{value.diff_id}`",
        f"- Previous archive: `{value.previous_archive_address}`",
        f"- Current archive: `{value.current_archive_address}`",
        f"- Added: {value.diff.added_count}",
        f"- Changed: {value.diff.changed_count}",
        f"- Removed: {value.diff.removed_count}",
        f"- Unchanged: {value.diff.unchanged_count}",
        f"- Score delta: {value.diff.score_delta}",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Module | Kind | Previous score | Current score | Previous risk | Current risk |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    lines.extend(
        f"| `{item.module_id}` | `{item.kind.value}` | {item.previous_score if item.previous_score is not None else '—'} | {item.current_score if item.current_score is not None else '—'} | {item.previous_risk or '—'} | {item.current_risk or '—'} |"
        for item in value.diff.changes
    )
    return "\n".join(lines) + "\n"


def module_workbench_archive_diff_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_ARCHIVE_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_ARCHIVE_DIFF_BOUNDARY,
        "resources": ["changes"],
        "change_kinds": [item.value for item in ModuleWorkbenchChangeKind],
        "max_changes": 20_000,
        "max_query_limit": MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_LIMIT,
        "path_free": True,
        "timestamp_free": True,
        "source_free": True,
    }


def module_workbench_archive_diff_capabilities() -> dict[str, Any]:
    operations = (
        "compare_verified_archives",
        "conserve_archive_addresses",
        "classify_added_modules",
        "classify_removed_modules",
        "classify_changed_modules",
        "classify_unchanged_modules",
        "query_changes",
        "verify_nested_diff",
        "verify_content_address",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_ARCHIVE_DIFF_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "path_free": True,
        "timestamp_free": True,
        "source_free": True,
    }


__all__ = [
    "build_module_workbench_archive_diff",
    "load_module_workbench_archive_diff",
    "module_workbench_archive_diff_capabilities",
    "module_workbench_archive_diff_csv",
    "module_workbench_archive_diff_from_mapping",
    "module_workbench_archive_diff_json",
    "module_workbench_archive_diff_schema",
    "query_module_workbench_archive_diff",
    "render_module_workbench_archive_diff_markdown",
    "verify_module_workbench_archive_diff",
    "verify_module_workbench_archive_diff_value",
]
