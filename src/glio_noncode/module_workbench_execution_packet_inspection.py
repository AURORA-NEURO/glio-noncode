"""Build, query, and export a packet review projection."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet import (
    load_module_workbench_execution_packet,
    verify_module_workbench_execution_packet,
    verify_module_workbench_execution_packet_value,
)
from .module_workbench_execution_packet_contracts import ModuleWorkbenchExecutionPacket
from .module_workbench_execution_packet_inspection_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_VERSION,
    ModuleWorkbenchExecutionPacketInspection,
    ModuleWorkbenchExecutionPacketInspectionFinding,
    ModuleWorkbenchExecutionPacketInspectionPlane,
    ModuleWorkbenchExecutionPacketInspectionSeverity,
    ModuleWorkbenchExecutionPacketInspectionState,
    address_module_workbench_execution_packet_inspection,
    address_module_workbench_execution_packet_inspection_finding,
)
from .module_workbench_execution_packet_query import replay_module_workbench_execution_packet
from .module_workbench_execution_packet_release import (
    build_module_workbench_execution_packet_release,
)
from .module_workbench_execution_packet_release_contracts import (
    ModuleWorkbenchExecutionPacketRelease,
)
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash


def _verification(value: ModuleWorkbenchExecutionPacket | str | Path) -> Any:
    if isinstance(value, ModuleWorkbenchExecutionPacket):
        return verify_module_workbench_execution_packet_value(value)
    return verify_module_workbench_execution_packet(value)


def _packet_or_none(
    value: ModuleWorkbenchExecutionPacket | str | Path,
    verified: Any,
) -> ModuleWorkbenchExecutionPacket | None:
    if isinstance(value, ModuleWorkbenchExecutionPacket):
        return value
    return load_module_workbench_execution_packet(value) if verified.accepted else None


def _plane(value: str) -> ModuleWorkbenchExecutionPacketInspectionPlane:
    try:
        return ModuleWorkbenchExecutionPacketInspectionPlane(value)
    except ValueError:
        return ModuleWorkbenchExecutionPacketInspectionPlane.SEMANTIC


def _severity(
    passed: bool,
    plane: ModuleWorkbenchExecutionPacketInspectionPlane,
) -> ModuleWorkbenchExecutionPacketInspectionSeverity:
    if passed:
        return ModuleWorkbenchExecutionPacketInspectionSeverity.INFO
    if plane in {
        ModuleWorkbenchExecutionPacketInspectionPlane.BYTES,
        ModuleWorkbenchExecutionPacketInspectionPlane.PATH,
        ModuleWorkbenchExecutionPacketInspectionPlane.PUBLIC,
        ModuleWorkbenchExecutionPacketInspectionPlane.STORAGE,
    }:
        return ModuleWorkbenchExecutionPacketInspectionSeverity.CRITICAL
    return ModuleWorkbenchExecutionPacketInspectionSeverity.WARNING


def _finding(
    finding_id: str,
    *,
    plane: ModuleWorkbenchExecutionPacketInspectionPlane,
    code: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketInspectionFinding:
    body = {
        "finding_id": finding_id,
        "plane": plane,
        "severity": _severity(passed, plane),
        "code": code,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketInspectionFinding(
        **body, content_address="pending"
    )
    return ModuleWorkbenchExecutionPacketInspectionFinding(
        **body,
        content_address=address_module_workbench_execution_packet_inspection_finding(provisional),
    )


def _verification_findings(receipt: Any) -> list[ModuleWorkbenchExecutionPacketInspectionFinding]:
    rows: list[ModuleWorkbenchExecutionPacketInspectionFinding] = []
    for check in receipt.checks:
        plane = _plane(str(check.plane))
        rows.append(
            _finding(
                f"verification:{check.check_id}",
                plane=plane,
                code=f"verification:{check.check_id}",
                passed=check.passed,
                observed=check.observed,
                required=check.required,
                detail=check.detail,
            )
        )
    return rows


def _release_findings(
    release: ModuleWorkbenchExecutionPacketRelease,
) -> list[ModuleWorkbenchExecutionPacketInspectionFinding]:
    return [
        _finding(
            f"release:{check.check_id}",
            plane=ModuleWorkbenchExecutionPacketInspectionPlane.RELEASE,
            code=f"release:{check.check_id}",
            passed=check.passed,
            observed=check.observed,
            required=check.required,
            detail=check.detail,
        )
        for check in release.checks
    ]


def build_module_workbench_execution_packet_inspection(
    value: ModuleWorkbenchExecutionPacket | str | Path,
) -> ModuleWorkbenchExecutionPacketInspection:
    """Normalize verification, replay, and release results into review findings."""

    receipt = _verification(value)
    packet = _packet_or_none(value, receipt)
    replay = replay_module_workbench_execution_packet(value)
    release = build_module_workbench_execution_packet_release(value)
    verification_findings = _verification_findings(receipt)
    findings = verification_findings + _release_findings(release)
    packet_id = packet.packet_id if packet is not None else receipt.packet_id
    packet_address = packet.content_address if packet is not None else "unavailable"
    body = {
        "packet_id": packet_id,
        "packet_address": packet_address,
        "verification_address": receipt.content_address,
        "replay_address": str(replay["content_address"]),
        "release_address": release.content_address,
        "artifact_count": receipt.artifact_count,
        "check_count": len(findings),
        "passed_check_count": sum(item.passed for item in findings),
        "failed_check_count": sum(not item.passed for item in findings),
        "findings": tuple(sorted(findings, key=lambda item: item.finding_id)),
        "state": (
            ModuleWorkbenchExecutionPacketInspectionState.ACCEPTED
            if all(item.passed for item in findings)
            else ModuleWorkbenchExecutionPacketInspectionState.BLOCKED
        ),
        "accepted": all(item.passed for item in findings),
    }
    if _has_forbidden_key(body):
        raise ValidationError("inspection projection contains a forbidden public key")
    provisional = ModuleWorkbenchExecutionPacketInspection(**body, content_address="pending")
    return ModuleWorkbenchExecutionPacketInspection(
        **body,
        content_address=address_module_workbench_execution_packet_inspection(provisional),
    )


def verify_module_workbench_execution_packet_inspection(
    value: ModuleWorkbenchExecutionPacketInspection,
) -> ModuleWorkbenchExecutionPacketInspection:
    """Verify finding addresses, counts, public fields, and the aggregate address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketInspection):
        raise ValidationError("inspection verification requires a typed inspection")
    for finding in value.findings:
        if (
            address_module_workbench_execution_packet_inspection_finding(finding)
            != finding.content_address
        ):
            raise ValidationError(f"inspection finding address mismatch: {finding.finding_id}")
    if _has_forbidden_key(value.to_dict()):
        raise ValidationError("inspection contains a forbidden public key")
    if address_module_workbench_execution_packet_inspection(value) != value.content_address:
        raise ValidationError("inspection address mismatch")
    return value


def query_module_workbench_execution_packet_inspection(
    value: ModuleWorkbenchExecutionPacketInspection | ModuleWorkbenchExecutionPacket | str | Path,
    *,
    resource: str = "findings",
    severity: str | None = None,
    plane: str | None = None,
    code: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded summary or filtered finding rows."""

    inspection = (
        value
        if isinstance(value, ModuleWorkbenchExecutionPacketInspection)
        else build_module_workbench_execution_packet_inspection(value)
    )
    verify_module_workbench_execution_packet_inspection(inspection)
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_LIMIT:
        raise ValidationError("inspection query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [inspection.to_dict(include_findings=False)]
        index_used = "packet_id"
    elif normalized == "findings":
        rows = [item.to_dict() for item in inspection.findings]
        if severity:
            rows = [row for row in rows if row.get("severity") == severity]
        if plane:
            rows = [row for row in rows if row.get("plane") == plane]
        if code:
            rows = [row for row in rows if row.get("code") == code]
        if passed is not None:
            rows = [row for row in rows if row.get("passed") is passed]
        if text:
            needle = text.casefold()
            rows = [row for row in rows if needle in canonical_json(row).casefold()]
        index_used = "finding_id"
    else:
        raise ValidationError("inspection resource must be findings or summary")
    total = len(rows)
    body = {
        "packet_id": inspection.packet_id,
        "inspection_address": inspection.content_address,
        "resource": normalized,
        "query": {
            "severity": severity,
            "plane": plane,
            "code": code,
            "passed": passed,
            "text": text,
        },
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": rows[offset : offset + limit],
        "accepted": inspection.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-inspection-query",
        )
    }


def module_workbench_execution_packet_inspection_json(
    value: ModuleWorkbenchExecutionPacketInspection,
) -> str:
    """Return canonical inspection JSON."""

    verify_module_workbench_execution_packet_inspection(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_inspection_csv(
    value: ModuleWorkbenchExecutionPacketInspection,
) -> str:
    """Return one stable CSV row per finding."""

    verify_module_workbench_execution_packet_inspection(value)
    fields = (
        "finding_id",
        "plane",
        "severity",
        "code",
        "passed",
        "observed",
        "required",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for finding in value.findings:
        row = finding.to_dict()
        row["observed"] = canonical_json(row["observed"])
        row["required"] = canonical_json(row["required"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_inspection_markdown(
    value: ModuleWorkbenchExecutionPacketInspection,
) -> str:
    """Render a compact reviewer report with every finding retained."""

    verify_module_workbench_execution_packet_inspection(value)
    lines = [
        "# Module Workbench Execution Packet Inspection",
        "",
        f"- Packet: `{value.packet_id}`",
        f"- State: `{value.state.value}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Artifacts: `{value.artifact_count}`",
        f"- Findings: `{value.finding_count}` (`{value.failed_finding_count}` failed)",
        f"- Critical failures: `{value.critical_count}`",
        f"- Address: `{value.content_address}`",
        "",
        "| Finding | Plane | Severity | Passed | Detail |",
        "|---|---|---|---:|---|",
    ]
    for finding in value.findings:
        detail = finding.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{finding.finding_id}` | `{finding.plane.value}` | `{finding.severity.value}` | "
            f"`{str(finding.passed).lower()}` | {detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_inspection_schema() -> dict[str, Any]:
    """Describe the inspection resource, filters, and public guarantees."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY,
        "resources": ["findings", "summary"],
        "planes": [item.value for item in ModuleWorkbenchExecutionPacketInspectionPlane],
        "severities": [item.value for item in ModuleWorkbenchExecutionPacketInspectionSeverity],
        "states": [item.value for item in ModuleWorkbenchExecutionPacketInspectionState],
        "filters": ["severity", "plane", "code", "passed", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_LIMIT,
        },
        "inputs": ["typed_packet", "verified_packet_directory"],
        "outputs": ["summary", "findings", "json", "csv", "markdown"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_inspection_capabilities() -> dict[str, Any]:
    """Declare deterministic inspection operations for offline clients."""

    operations = (
        "normalize_verification_findings",
        "normalize_release_findings",
        "classify_severity",
        "query_findings",
        "query_summary",
        "filter_by_plane",
        "filter_by_severity",
        "filter_by_result",
        "export_json",
        "export_csv",
        "export_markdown",
        "verify_finding_addresses",
        "verify_inspection_address",
        "enforce_public_boundary",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "offline": True,
        "bounded": True,
        "identity_free": True,
    }


__all__ = [
    "build_module_workbench_execution_packet_inspection",
    "module_workbench_execution_packet_inspection_capabilities",
    "module_workbench_execution_packet_inspection_csv",
    "module_workbench_execution_packet_inspection_json",
    "module_workbench_execution_packet_inspection_schema",
    "query_module_workbench_execution_packet_inspection",
    "render_module_workbench_execution_packet_inspection_markdown",
    "verify_module_workbench_execution_packet_inspection",
]
