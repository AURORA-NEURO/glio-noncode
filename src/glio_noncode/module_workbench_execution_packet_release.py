"""Evaluate, query, and export release decisions for execution packets."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet import (
    load_module_workbench_execution_packet,
    verify_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
    ModuleWorkbenchExecutionPacket,
    address_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_query import (
    replay_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_release_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_VERSION,
    ModuleWorkbenchExecutionPacketRelease,
    ModuleWorkbenchExecutionPacketReleaseCheck,
    ModuleWorkbenchExecutionPacketReleasePlane,
    ModuleWorkbenchExecutionPacketReleaseState,
    address_module_workbench_execution_packet_release,
    address_module_workbench_execution_packet_release_check,
)
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes


def _check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketReleasePlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketReleaseCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleWorkbenchExecutionPacketReleaseCheck(
        **body,
        content_address=address_module_workbench_execution_packet_release_check(
            ModuleWorkbenchExecutionPacketReleaseCheck(**body, content_address="pending")
        ),
    )


def _typed_verification(
    packet: ModuleWorkbenchExecutionPacket,
) -> dict[str, Any]:
    """Check a typed packet without requiring it to be written to disk."""

    byte_failures = tuple(
        sorted(
            item.artifact_id
            for item in packet.artifacts
            if item.payload is None
            or hash_bytes(
                item.payload.encode("utf-8"),
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
            )
            != item.content_address
        )
    )
    address_ok = address_module_workbench_execution_packet(packet) == packet.content_address
    accepted = bool(packet.accepted and address_ok and not byte_failures)
    body = {
        "packet_id": packet.packet_id,
        "artifact_count": packet.artifact_count,
        "present_count": packet.artifact_count,
        "missing_count": 0,
        "byte_failures": byte_failures,
        "address_ok": address_ok,
        "accepted": accepted,
    }
    return body | {
        "content_address": content_hash(
            body, prefix="module-workbench-execution-packet-verification"
        )
    }


def _resolve_packet(
    value: ModuleWorkbenchExecutionPacket | str | Path,
) -> tuple[ModuleWorkbenchExecutionPacket | None, str, str, bool, int, int]:
    if isinstance(value, ModuleWorkbenchExecutionPacket):
        typed = _typed_verification(value)
        return (
            value,
            value.packet_id,
            value.content_address,
            bool(typed["accepted"]),
            value.artifact_count,
            value.passed_check_count,
        )
    verification = verify_module_workbench_execution_packet(value)
    packet = load_module_workbench_execution_packet(value) if verification.accepted else None
    if packet is None:
        return (
            None,
            verification.packet_id,
            "unavailable",
            False,
            verification.artifact_count,
            0,
        )
    return (
        packet,
        packet.packet_id,
        packet.content_address,
        verification.accepted,
        packet.artifact_count,
        packet.passed_check_count,
    )


def _replay_address(value: ModuleWorkbenchExecutionPacket | str | Path) -> tuple[str, bool]:
    replay = replay_module_workbench_execution_packet(value)
    return str(replay["content_address"]), bool(replay.get("accepted"))


def build_module_workbench_execution_packet_release(
    value: ModuleWorkbenchExecutionPacket | str | Path,
    *,
    release_id: str = "glio-noncode-module-workbench-execution-release",
    minimum_artifact_count: int = 13,
    minimum_passed_check_count: int = 1,
) -> ModuleWorkbenchExecutionPacketRelease:
    """Create an explicit accepted or blocked release decision."""

    if not isinstance(release_id, str) or not release_id.strip():
        raise ValidationError("execution packet release ID is required")
    if minimum_artifact_count < 0 or minimum_passed_check_count < 0:
        raise ValidationError("release thresholds cannot be negative")
    packet, packet_id, packet_address, packet_ok, artifact_count, passed_check_count = (
        _resolve_packet(value)
    )
    replay_address, replay_ok = _replay_address(value)
    packet_public = packet is not None and not _has_forbidden_key(packet.to_dict())
    checks = (
        _check(
            "artifact-threshold",
            ModuleWorkbenchExecutionPacketReleasePlane.THRESHOLD,
            artifact_count >= minimum_artifact_count,
            artifact_count,
            minimum_artifact_count,
            "packet contains the required number of artifacts",
        ),
        _check(
            "check-threshold",
            ModuleWorkbenchExecutionPacketReleasePlane.THRESHOLD,
            passed_check_count >= minimum_passed_check_count,
            passed_check_count,
            minimum_passed_check_count,
            "packet contains the required number of passed checks",
        ),
        _check(
            "packet-accepted",
            ModuleWorkbenchExecutionPacketReleasePlane.PACKET,
            packet_ok,
            packet_ok,
            True,
            "packet state is accepted and its bytes are internally consistent",
        ),
        _check(
            "public-boundary",
            ModuleWorkbenchExecutionPacketReleasePlane.PUBLIC,
            packet_public,
            "clean" if packet_public else "blocked",
            "clean",
            "packet projection contains only public aggregate fields",
        ),
        _check(
            "replay-accepted",
            ModuleWorkbenchExecutionPacketReleasePlane.REPLAY,
            replay_ok,
            replay_ok,
            True,
            "packet replay receipt is accepted",
        ),
        _check(
            "verification-address",
            ModuleWorkbenchExecutionPacketReleasePlane.VERIFICATION,
            bool(packet_address),
            packet_address,
            "addressed",
            "packet verification retains an addressed packet reference",
        ),
    )
    accepted = all(item.passed for item in checks)
    state = (
        ModuleWorkbenchExecutionPacketReleaseState.ACCEPTED
        if accepted
        else ModuleWorkbenchExecutionPacketReleaseState.BLOCKED
    )
    body = {
        "release_id": release_id,
        "packet_id": packet_id,
        "packet_address": packet_address,
        "verification_address": content_hash(
            {"packet_id": packet_id, "packet_address": packet_address},
            prefix="module-workbench-execution-packet-verification",
        ),
        "replay_address": replay_address,
        "minimum_artifact_count": minimum_artifact_count,
        "minimum_passed_check_count": minimum_passed_check_count,
        "state": state,
        "accepted": accepted,
        "checks": tuple(sorted(checks, key=lambda item: item.check_id)),
    }
    provisional = ModuleWorkbenchExecutionPacketRelease(**body, content_address="pending")
    return ModuleWorkbenchExecutionPacketRelease(
        **body,
        content_address=address_module_workbench_execution_packet_release(provisional),
    )


def verify_module_workbench_execution_packet_release(
    value: ModuleWorkbenchExecutionPacketRelease,
) -> ModuleWorkbenchExecutionPacketRelease:
    """Verify release checks and the aggregate release address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketRelease):
        raise ValidationError("execution packet release verification requires a typed release")
    for check in value.checks:
        if address_module_workbench_execution_packet_release_check(check) != check.content_address:
            raise ValidationError(f"release check address mismatch: {check.check_id}")
    if address_module_workbench_execution_packet_release(value) != value.content_address:
        raise ValidationError("execution packet release address mismatch")
    if value.accepted != all(item.passed for item in value.checks):
        raise ValidationError("execution packet release acceptance is inconsistent")
    return value


def query_module_workbench_execution_packet_release(
    value: ModuleWorkbenchExecutionPacketRelease,
    *,
    resource: str = "checks",
    plane: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded release summary or check view."""

    verify_module_workbench_execution_packet_release(value)
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_LIMIT:
        raise ValidationError("execution packet release paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "checks":
        rows = [item.to_dict() for item in value.checks]
        if plane:
            rows = [row for row in rows if row.get("plane") == plane]
        if passed is not None:
            rows = [row for row in rows if row.get("passed") is passed]
        index_used = "check_id"
    elif normalized == "summary":
        rows = [value.to_dict(include_checks=False)]
        index_used = "release_id"
    else:
        raise ValidationError("execution packet release resource must be checks or summary")
    if text:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    body = {
        "release_id": value.release_id,
        "release_address": value.content_address,
        "resource": normalized,
        "query": {"plane": plane, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body, prefix="module-workbench-execution-packet-release-query"
        )
    }


def module_workbench_execution_packet_release_json(
    value: ModuleWorkbenchExecutionPacketRelease,
) -> str:
    """Return canonical release JSON."""

    verify_module_workbench_execution_packet_release(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_release_csv(
    value: ModuleWorkbenchExecutionPacketRelease,
) -> str:
    """Return one stable CSV row per release check."""

    verify_module_workbench_execution_packet_release(value)
    fields = ("check_id", "plane", "passed", "observed", "required", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        for field in ("observed", "required"):
            if isinstance(row.get(field), (dict, list, tuple)):
                row[field] = canonical_json(row[field])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_release_markdown(
    value: ModuleWorkbenchExecutionPacketRelease,
) -> str:
    """Render a readable release decision for offline review."""

    verify_module_workbench_execution_packet_release(value)
    lines = [
        "# Module Workbench Execution Packet Release",
        "",
        f"- Release: `{value.release_id}`",
        f"- Address: `{value.content_address}`",
        f"- Packet: `{value.packet_id}`",
        f"- State: **{value.state.value}**",
        f"- Accepted: **{str(value.accepted).lower()}**",
        f"- Checks: **{value.passed_check_count}/{value.check_count} passed**",
        "",
        "## Thresholds",
        "",
        f"- Minimum artifacts: **{value.minimum_artifact_count}**",
        f"- Minimum passed checks: **{value.minimum_passed_check_count}**",
        "",
        "## Checks",
        "",
        "| Check | Plane | Result | Observed | Required | Detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in value.checks:
        lines.append(
            f"| `{check.check_id}` | {check.plane.value} | "
            f"{'pass' if check.passed else 'fail'} | `{check.observed}` | "
            f"`{check.required}` | {check.detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_release_schema() -> dict[str, Any]:
    """Describe packet release decisions."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_BOUNDARY,
        "states": [item.value for item in ModuleWorkbenchExecutionPacketReleaseState],
        "planes": [item.value for item in ModuleWorkbenchExecutionPacketReleasePlane],
        "resources": ["checks", "summary"],
        "filters": ["plane", "passed", "text"],
        "thresholds": ["minimum_artifact_count", "minimum_passed_check_count"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_release_capabilities() -> dict[str, Any]:
    """Declare release operations and explicit fail-closed behavior."""

    operations = (
        "resolve_typed_packet",
        "resolve_verified_directory",
        "check_artifact_threshold",
        "check_passed_check_threshold",
        "check_packet_acceptance",
        "check_public_boundary",
        "check_replay_acceptance",
        "check_verification_address",
        "build_release_decision",
        "verify_release_address",
        "query_checks",
        "query_summary",
        "filter_planes",
        "filter_results",
        "export_json",
        "export_csv",
        "render_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "offline": True,
        "fail_closed": True,
        "identity_free": True,
    }


__all__ = [
    "build_module_workbench_execution_packet_release",
    "module_workbench_execution_packet_release_capabilities",
    "module_workbench_execution_packet_release_csv",
    "module_workbench_execution_packet_release_json",
    "module_workbench_execution_packet_release_schema",
    "query_module_workbench_execution_packet_release",
    "render_module_workbench_execution_packet_release_markdown",
    "verify_module_workbench_execution_packet_release",
]
