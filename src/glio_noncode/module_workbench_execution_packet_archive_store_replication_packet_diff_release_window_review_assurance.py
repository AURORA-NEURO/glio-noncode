"""Independent assurance for release-window review ledgers."""

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
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_FINDING_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceFinding,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_finding,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _finding(
    ordinal: int,
    kind: str,
    severity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    remediation: str,
) -> Any:
    body = {
        "ordinal": ordinal,
        "finding_id": f"release-window-review-assurance-{ordinal}-{kind}",
        "kind": _text(kind, "review assurance finding kind", 128),
        "severity": severity.value,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "detail": _text(detail, "review assurance detail"),
        "remediation": _text(remediation, "review assurance remediation"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceFinding(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_FINDING_PREFIX
        + ":pending-finding",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_finding(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
    ledger: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    packet_assurance: Any,
    runtime: Any | None = None,
    *,
    assurance_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-assurance",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance:
    """Recheck ledger linkage, decisions, and optional runtime closure."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        window
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        packet_assurance
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        ledger, window=window, assurance=packet_assurance
    )
    findings = [
        _finding(
            0,
            "window-link",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            ledger.window_address == window.content_address,
            ledger.window_address,
            window.content_address,
            "review ledger references the supplied release window",
            "rebuild the review ledger against the verified window",
        ),
        _finding(
            1,
            "assurance-link",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            ledger.assurance_address == packet_assurance.content_address,
            ledger.assurance_address,
            packet_assurance.content_address,
            "review ledger references independent packet assurance",
            "rebuild the review ledger against the matching assurance receipt",
        ),
        _finding(
            2,
            "chain-continuity",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            ledger.append_only
            and tuple(item.ordinal for item in ledger.entries) == tuple(range(ledger.entry_count)),
            {"append_only": ledger.append_only, "entry_count": ledger.entry_count},
            {"contiguous": True},
            "review entries form a contiguous append-only chain",
            "restore the missing or reordered entry before review closure",
        ),
        _finding(
            3,
            "head-conservation",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            ledger.head_address == (ledger.entries[-1].content_address if ledger.entries else None),
            ledger.head_address,
            ledger.entries[-1].content_address if ledger.entries else None,
            "the ledger head resolves to the latest entry",
            "recompute the ledger head from the last verified entry",
        ),
        _finding(
            4,
            "decision-semantics",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            all((item.decision == "promote") == item.release_ready for item in ledger.entries),
            [item.decision for item in ledger.entries],
            "promote iff release-ready",
            "decision state and readiness are conserved per entry",
            "repair the entry decision or readiness projection",
        ),
        _finding(
            5,
            "action-accounting",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.WARNING,
            all(
                item.decision == "promote" or bool(item.required_actions) for item in ledger.entries
            ),
            [len(item.required_actions) for item in ledger.entries],
            "non-promote entries retain actions",
            "held, blocked, and superseded entries explain their next action",
            "add explicit bounded remediation actions before closing review",
        ),
        _finding(
            6,
            "promote-eligibility",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            all(
                not item.release_ready or (window.release_ready and packet_assurance.release_ready)
                for item in ledger.entries
            ),
            {
                "window_release_ready": window.release_ready,
                "assurance_release_ready": packet_assurance.release_ready,
            },
            {"promote_requires_both": True},
            "every promote entry is backed by ready window and assurance evidence",
            "do not record promotion until both upstream receipts are ready",
        ),
        _finding(
            7,
            "head-decision",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.WARNING,
            bool(ledger.entries),
            {"entry_count": ledger.entry_count, "state": ledger.state},
            {"entry_count": ">0"},
            "the review ledger has an explicit current decision",
            "append a bounded hold, block, supersede, or promote decision",
        ),
        _finding(
            8,
            "public-boundary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
            True,
            {"path_free": True, "identity_free": True},
            {"path_free": True, "identity_free": True},
            "review assurance contains only public deterministic fields",
            "remove identity, language, secret, path, or transport metadata",
        ),
    ]
    if runtime is not None:
        runtime_ok = (
            runtime.ledger_address == ledger.content_address
            and runtime.window_address == window.content_address
            and runtime.assurance_address == packet_assurance.content_address
        )
        findings.append(
            _finding(
                9,
                "runtime-link",
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER,
                runtime_ok,
                {
                    "ledger": runtime.ledger_address,
                    "window": runtime.window_address,
                    "assurance": runtime.assurance_address,
                },
                {"linked": True},
                "optional review runtime references the same evidence chain",
                "rerun the runtime against the current review ledger and evidence",
            )
        )
    blocker_count = sum(
        not item.passed
        and item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER.value
        for item in findings
    )
    warning_count = sum(
        not item.passed
        and item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.WARNING.value
        for item in findings
    )
    passed_count = sum(item.passed for item in findings)
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState.BLOCKED.value
        if blocker_count
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState.HOLD.value
        if warning_count
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState.ACCEPTED.value
    )
    body = {
        "assurance_id": _text(assurance_id, "review assurance ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY,
        "ledger_address": ledger.content_address,
        "window_address": window.content_address,
        "head_address": ledger.head_address,
        "findings": tuple(findings),
        "finding_count": len(findings),
        "passed_count": passed_count,
        "warning_count": warning_count,
        "blocker_count": blocker_count,
        "state": state,
        "release_ready": bool(
            blocker_count == 0
            and warning_count == 0
            and ledger.release_ready
            and window.release_ready
            and packet_assurance.release_ready
        ),
        "accepted": blocker_count == 0,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_PREFIX
        + ":pending-assurance",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance:
    """Verify finding addresses and the independent aggregate address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
    ):
        raise ValidationError("review assurance verification requires a typed assurance")
    for finding in value.findings:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_finding(
                finding
            )
            != finding.content_address
        ):
            raise ValidationError("review assurance finding address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review assurance address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "finding_id",
        "kind",
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
    for item in value.findings:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Assurance",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- Findings: `{value.finding_count}`; passed: `{value.passed_count}`; warnings: `{value.warning_count}`; blockers: `{value.blocker_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|---|",
    ]
    for item in value.findings:
        lines.append(
            f"| {item.ordinal} | {item.kind} | {item.severity} | {str(item.passed).lower()} | {item.detail} |"
        )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
    *,
    resource: str = "summary",
    kind: str | None = None,
    severity: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded assurance summary or finding page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
        value
    )
    if resource not in {"summary", "findings"}:
        raise ValidationError("review assurance query resource is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review assurance query offset is invalid")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT
    ):
        raise ValidationError("review assurance query limit is invalid")
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("review assurance passed filter is invalid")
    if text is not None:
        text = _text(text, "review assurance query text")
    if resource == "summary":
        rows = [value.summary()]
        index_used = "assurance_id"
    else:
        rows = [item.to_dict() for item in value.findings]
        if kind is not None:
            rows = [row for row in rows if row["kind"] == kind]
        if severity is not None:
            rows = [row for row in rows if row["severity"] == severity]
        if passed is not None:
            rows = [row for row in rows if row["passed"] is passed]
        if text is not None:
            rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
        index_used = "ordinal"
    body = {
        "resource": resource,
        "query": {"kind": kind, "severity": severity, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
        "release_ready": value.release_ready,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a review-assurance query envelope."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review assurance query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY
        + "-query",
    )
    if value["content_address"] != expected:
        raise ValidationError("review assurance query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query(
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
        "release_ready",
        "reference_address",
        "content_address",
        "ordinal",
        "finding_id",
        "kind",
        "severity",
        "passed",
        "detail",
        "remediation",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Assurance Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('kind')} | {row.get('severity')} | {str(row.get('passed')).lower()} | {row.get('detail')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_schema() -> (
    dict[str, Any]
):
    """Describe independent review-ledger assurance."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY,
        "findings": [
            "window-link",
            "assurance-link",
            "chain-continuity",
            "head-conservation",
            "decision-semantics",
            "action-accounting",
            "promote-eligibility",
            "head-decision",
            "public-boundary",
            "runtime-link",
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState
        ],
        "release_requires": [
            "no_blockers",
            "no_warnings",
            "promoted_head",
            "ready_window",
            "ready_packet_assurance",
        ],
        "independent": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_capabilities() -> (
    dict[str, Any]
):
    """Declare review assurance operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION,
        "operations": ["build", "verify", "json", "csv", "markdown", "query"],
        "independent": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded assurance finding queries."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION
        + "-query-v1",
        "resources": {"summary": ["summary"], "findings": ["findings"]},
        "filters": ["kind", "severity", "passed", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_query_capabilities() -> (
    dict[str, Any]
):
    """Declare assurance query and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION
        + "-query-v1",
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
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
    )
]
