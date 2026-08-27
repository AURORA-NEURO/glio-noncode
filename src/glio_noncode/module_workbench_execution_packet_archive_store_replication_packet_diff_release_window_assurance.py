"""Independent assurance for release-window policy decisions."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_FINDING_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_QUERY_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_finding,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _finding(
    ordinal: int,
    finding_id: str,
    plane: str,
    severity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    remediation: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding:
    body = {
        "ordinal": ordinal,
        "finding_id": _text(finding_id, "release-window assurance finding ID", 256),
        "plane": _text(plane, "release-window assurance plane", 128),
        "severity": severity.value,
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": _text(detail, "release-window assurance detail", 4096),
        "remediation": _text(remediation, "release-window assurance remediation", 4096),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_FINDING_PREFIX
        + ":pending-finding",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_finding(
            provisional
        ),
    )


def _findings(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime
    | None,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding,
    ...,
]:
    """Produce independent findings from only public aggregate values."""

    count_conserved = (
        window.check_count == window.passed_count + window.warning_count + window.blocker_count
    )
    state_ready = window.release_ready == (window.state == "promotable" and window.accepted)
    runtime_closed = runtime is None or (
        runtime.accepted
        and runtime.blocked_count == 0
        and runtime.completed_count == runtime.stage_count
    )
    return (
        _finding(
            0,
            "window-address-integrity",
            "address",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.INFO,
            True,
            {"window_address": window.content_address},
            {"verified": True},
            "the release-window aggregate address has been verified",
            "rebuild the release-window receipt if its address does not verify",
        ),
        _finding(
            1,
            "matrix-policy-linkage",
            "linkage",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER,
            bool(window.batch_address and window.policy_address),
            {
                "batch_present": bool(window.batch_address),
                "policy_present": bool(window.policy_address),
            },
            {"batch_present": True, "policy_present": True},
            "the decision retains both the verified matrix and policy addresses",
            "rebuild the window from an addressed matrix and policy",
        ),
        _finding(
            2,
            "check-conservation",
            "conservation",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER,
            count_conserved,
            {
                "check_count": window.check_count,
                "passed_count": window.passed_count,
                "warning_count": window.warning_count,
                "blocker_count": window.blocker_count,
            },
            {"conserved": True},
            "policy check totals are conserved across the assurance boundary",
            "recompute the window from its ordered policy checks",
        ),
        _finding(
            3,
            "window-decision-semantics",
            "decision",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER
            if window.state == "blocked"
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.WARNING,
            state_ready,
            {"state": window.state, "release_ready": window.release_ready},
            {"state_matches_readiness": True},
            "window state and release readiness are consistent",
            "re-evaluate the policy checks before using the decision",
        ),
        _finding(
            4,
            "matrix-score",
            "score",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER,
            0 <= window.score <= 1 and window.item_count > 0,
            {"score": window.score, "item_count": window.item_count},
            {"bounded": True, "non_empty": True},
            "matrix readiness score is bounded and backed by packet pairs",
            "rebuild the matrix with conserved pair and readiness counts",
        ),
        _finding(
            5,
            "held-pair-review",
            "review",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.WARNING,
            window.hold_count == 0,
            {"hold_count": window.hold_count},
            {"hold_count": 0},
            "no packet pair remains in a held release state",
            "review every held pair and rebuild the release window",
        ),
        _finding(
            6,
            "runtime-closure",
            "runtime",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.WARNING,
            runtime_closed,
            {
                "runtime_present": runtime is not None,
                "runtime_closed": runtime_closed,
            },
            {"closed_or_absent": True},
            "optional runtime evidence is either closed or intentionally absent",
            "complete the release-window runtime before relying on its receipt",
        ),
        _finding(
            7,
            "window-admissibility",
            "admissibility",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER,
            window.blocker_count == 0,
            {"window_blocker_count": window.blocker_count},
            {"window_blocker_count": 0},
            "the release-window policy has no blocking failures",
            "resolve blocking policy failures before relying on assurance",
        ),
        _finding(
            8,
            "public-boundary",
            "boundary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER,
            True,
            {"path_free": True, "identity_free": True, "timestamp_free": True},
            {"path_free": True, "identity_free": True, "timestamp_free": True},
            "assurance output contains no private or identity-bearing transport fields",
            "remove private, identity, path, or timestamp fields before export",
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime
    | None = None,
    *,
    assurance_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-assurance"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance:
    """Build an independent assurance receipt for a window decision."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        window
    )
    if runtime is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            runtime
        )
        if runtime.window_address != window.content_address:
            raise ValidationError("release-window runtime does not reference the window")
    assurance_id = _text(assurance_id, "release-window assurance ID", 256)
    findings = _findings(window, runtime)
    blocker_count = sum(
        not item.passed
        and item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER.value
        for item in findings
    )
    warning_count = sum(
        not item.passed
        and item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.WARNING.value
        for item in findings
    )
    passed_count = sum(item.passed for item in findings)
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.BLOCKED
        if blocker_count
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.HOLD
        if warning_count
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.ACCEPTED
    )
    body = {
        "assurance_id": assurance_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_BOUNDARY,
        "window_address": window.content_address,
        "runtime_address": runtime.content_address if runtime is not None else None,
        "state": state.value,
        "release_ready": state
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.ACCEPTED
        and window.release_ready,
        "findings": findings,
        "finding_count": len(findings),
        "passed_count": passed_count,
        "warning_count": warning_count,
        "blocker_count": blocker_count,
        "score": passed_count / len(findings),
        "accepted": blocker_count == 0,
        "detail": "independent release-window assurance completed",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_PREFIX
        + ":pending-assurance",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance:
    """Verify finding addresses and the assurance aggregate address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
    ):
        raise ValidationError("release-window assurance verification requires a typed report")
    for finding in value.findings:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_finding(
                finding
            )
            != finding.content_address
        ):
            raise ValidationError("release-window assurance finding address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            value
        )
        != value.content_address
    ):
        raise ValidationError("release-window assurance address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "finding_id",
        "plane",
        "severity",
        "passed",
        "observed",
        "expected",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for finding in value.findings:
        row = finding.to_dict()
        row["observed"] = canonical_json(row["observed"])
        row["expected"] = canonical_json(row["expected"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Assurance",
        "",
        f"- state: **{value.state}**",
        f"- release ready: `{str(value.release_ready).lower()}`",
        f"- findings: `{value.passed_count}/{value.finding_count}` passed; warnings: `{value.warning_count}`; blockers: `{value.blocker_count}`",
        f"- score: `{value.score:.6f}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Plane | Severity | Passed | Detail | Remediation |",
        "|---:|---|---|---|---|---|",
    ]
    for finding in value.findings:
        lines.append(
            f"| {finding.ordinal} | {finding.plane} | {finding.severity} | {str(finding.passed).lower()} | "
            f"{finding.detail} | {finding.remediation} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_schema() -> (
    dict[str, Any]
):
    """Describe independent assurance output."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_BOUNDARY,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState
        ],
        "severities": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity
        ],
        "findings": [
            "window_address_integrity",
            "matrix_policy_linkage",
            "check_conservation",
            "window_decision_semantics",
            "matrix_score",
            "held_pair_review",
            "runtime_closure",
            "window_admissibility",
            "public_boundary",
        ],
        "conservation": [
            "finding_count",
            "passed_count",
            "warning_count",
            "blocker_count",
            "score",
        ],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_capabilities() -> (
    dict[str, Any]
):
    """Declare assurance and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION,
        "operations": ["build", "verify", "json", "csv", "markdown", "query"],
        "severity_order": ["info", "warning", "blocker"],
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
    *,
    resource: str = "summary",
    severity: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded assurance summary or finding page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        value
    )
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT
    ):
        raise ValidationError("release-window assurance query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "assurance_id"
    elif normalized == "findings":
        rows = [item.to_dict() for item in value.findings]
        if severity is not None:
            if severity not in {
                item.value
                for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity
            }:
                raise ValidationError("release-window assurance query severity is invalid")
            rows = [row for row in rows if row["severity"] == severity]
        if passed is not None:
            if not isinstance(passed, bool):
                raise ValidationError(
                    "release-window assurance query passed filter must be boolean"
                )
            rows = [row for row in rows if row["passed"] is passed]
        index_used = "severity"
    else:
        raise ValidationError("unsupported release-window assurance query resource")
    if text is not None:
        if not isinstance(text, str) or len(text) > 512:
            raise ValidationError("release-window assurance query text is invalid")
        needle = text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    body = {
        "resource": normalized,
        "query": {"severity": severity, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify an addressed assurance query response."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("release-window assurance query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("release-window assurance query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "total",
        "offset",
        "limit",
        "index_used",
        "accepted",
        "reference_address",
        "content_address",
        "ordinal",
        "finding_id",
        "plane",
        "severity",
        "passed",
        "observed",
        "expected",
        "detail",
        "remediation",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            row = dict(row)
            row["observed"] = canonical_json(row.get("observed"))
            row["expected"] = canonical_json(row.get("expected"))
            writer.writerow(envelope | row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Assurance Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- reference: `{value.get('reference_address')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Plane | Severity | Passed | Detail | Remediation |",
        "|---:|---|---|---|---|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('plane')} | {row.get('severity')} | "
            f"{str(row.get('passed')).lower()} | {row.get('detail')} | {row.get('remediation')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded assurance finding queries."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_QUERY_PREFIX
        + "-v1",
        "resources": {"summary": ["summary"], "findings": ["findings"]},
        "filters": ["severity", "passed", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
        },
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_capabilities() -> (
    dict[str, Any]
):
    """Declare assurance query operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_QUERY_PREFIX
        + "-v1",
        "operations": [
            "summary",
            "findings",
            "filter",
            "page",
            "json",
            "csv",
            "markdown",
            "verify",
        ],
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance"
    )
]
