"""Independent assurance for durable release-window review stores.

Assurance intentionally recomputes evidence from the hydrated store and its
ledger instead of trusting the store's aggregate flags.  Findings are
addressed individually, ordered, and exported as a stable public receipt.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-assurance-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_FINDING_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-assurance-finding"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceSeverity(
    StrEnum
):
    PASS = "pass"
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceState(
    StrEnum
):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _public(value: Any) -> bool:
    forbidden = {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public(item) for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_finding(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceFinding,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_FINDING_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceFinding:
    """One independently computed assurance result."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        kind: str,
        severity: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review store assurance finding ordinal")
        _text(self.finding_id, "review store assurance finding ID", 256)
        _text(self.kind, "review store assurance finding kind", 256)
        if self.severity not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceSeverity
        }:
            raise ValidationError("review store assurance finding severity is invalid")
        _bool(self.passed, "review store assurance finding passed flag")
        _text(self.detail, "review store assurance finding detail")
        _text(self.remediation, "review store assurance finding remediation")
        _address(self.content_address, "review store assurance finding address")
        if (
            self.passed
            and self.severity
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceSeverity.PASS.value
        ):
            raise ValidationError("passed assurance findings must have pass severity")
        if (
            not self.passed
            and self.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceSeverity.PASS.value
        ):
            raise ValidationError("failed assurance findings cannot have pass severity")
        if not _public(self.to_dict()):
            raise ValidationError("review store assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "kind": self.kind,
            "severity": self.severity,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance:
    """Addressed assurance aggregate with conserved finding counts."""

    def __init__(
        self,
        assurance_id: str,
        version: str,
        boundary: str,
        store_address: str,
        ledger_address: str,
        head_address: str | None,
        findings: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceFinding,
            ...,
        ],
        finding_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.store_address = store_address
        self.ledger_address = ledger_address
        self.head_address = head_address
        self.findings = tuple(findings)
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "review store assurance ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_VERSION
        ):
            raise ValidationError("review store assurance version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_BOUNDARY
        ):
            raise ValidationError("review store assurance boundary is invalid")
        _address(self.store_address, "review store assurance store address")
        _address(self.ledger_address, "review store assurance ledger address")
        _address(self.head_address, "review store assurance head address", optional=True)
        _count(self.finding_count, "review store assurance finding count")
        if self.finding_count != len(self.findings) or self.finding_count == 0:
            raise ValidationError("review store assurance findings must be non-empty and conserved")
        for ordinal, finding in enumerate(self.findings):
            if finding.ordinal != ordinal:
                raise ValidationError("review store assurance finding ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_finding(
                    finding
                )
                != finding.content_address
            ):
                raise ValidationError("review store assurance finding address mismatch")
        passed = sum(item.passed for item in self.findings)
        warning = sum(not item.passed and item.severity == "warning" for item in self.findings)
        blocker = sum(not item.passed and item.severity == "blocker" for item in self.findings)
        if (self.passed_count, self.warning_count, self.blocker_count) != (
            passed,
            warning,
            blocker,
        ):
            raise ValidationError("review store assurance finding counts do not conserve")
        _count(self.passed_count, "review store assurance passed count")
        _count(self.warning_count, "review store assurance warning count")
        _count(self.blocker_count, "review store assurance blocker count")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceState
        }:
            raise ValidationError("review store assurance state is invalid")
        _bool(self.accepted, "review store assurance accepted flag")
        _bool(self.release_ready, "review store assurance release-ready flag")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("review store assurance acceptance does not conserve")
        expected_state = (
            "blocked" if self.blocker_count else "warning" if self.warning_count else "passed"
        )
        if self.state != expected_state:
            raise ValidationError("review store assurance state does not follow findings")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("review store assurance readiness does not conserve")
        _address(self.content_address, "review store assurance content address")
        if not _public(self.to_dict()):
            raise ValidationError("review store assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "store_address": self.store_address,
            "ledger_address": self.ledger_address,
            "head_address": self.head_address,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def _finding(
    ordinal: int,
    kind: str,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
    remediation: str,
    *,
    severity: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceFinding:
    if severity is None:
        severity = "pass" if passed else "blocker"
    body = {
        "ordinal": ordinal,
        "finding_id": f"review-store-assurance-{ordinal}-{kind}",
        "kind": kind,
        "severity": severity,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
        "remediation": remediation,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceFinding(
        **body, content_address="pending:finding"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_finding(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
    store: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    *,
    assurance_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store-assurance",
) -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance
):
    """Recompute durable-store assurance from the store and hydrated ledger."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        store
    )
    ledger = getattr(store, "ledger", None)
    replay = replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        store
    )
    ledger_address = ledger.content_address if ledger is not None else store.ledger_address
    head_address = ledger.head_address if ledger is not None else None
    public_ok = (
        _public(store.to_dict()) and _public(ledger.to_dict())
        if ledger is not None
        else _public(store.to_dict())
    )
    operations_ok = (
        bool(store.operations)
        and all(item.accepted for item in store.operations)
        and tuple(item.ordinal for item in store.operations) == tuple(range(len(store.operations)))
    )
    findings = (
        _finding(
            0,
            "store-address",
            store.content_address.startswith(
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
                + ":"
            ),
            "addressed durable store",
            store.content_address,
            "store aggregate has a published content address",
            "rebuild the store aggregate from canonical inputs",
        ),
        _finding(
            1,
            "ledger-link",
            ledger is not None and ledger.content_address == store.ledger_address,
            store.ledger_address,
            ledger_address,
            "hydrated ledger is linked to the store manifest",
            "load the exact ledger artifact before assurance",
        ),
        _finding(
            2,
            "head-conservation",
            ledger is not None
            and ledger.head_address == store.head_address
            and ledger.entry_count == store.entry_count,
            {"head": store.head_address, "count": store.entry_count},
            {"head": head_address, "count": ledger.entry_count if ledger is not None else None},
            "store head and entry count agree with the ledger",
            "replay the ledger and repair the persisted manifest",
        ),
        _finding(
            3,
            "operation-chain",
            operations_ok,
            "contiguous accepted operation chain",
            {"count": len(store.operations), "accepted": operations_ok},
            "durable operations form one append-only chain",
            "reject the store and rebuild its journal",
        ),
        _finding(
            4,
            "replay",
            replay.accepted,
            "matched",
            replay.state,
            "replay reaches the persisted head",
            "rehydrate the exact ledger referenced by the store",
        ),
        _finding(
            5,
            "public-boundary",
            public_ok,
            True,
            public_ok,
            "public projection contains deterministic fields only",
            "remove private, attribution, or machine-specific fields",
        ),
        _finding(
            6,
            "release-readiness",
            store.release_ready,
            True,
            store.release_ready,
            "store is release-ready",
            "append or review a decision that makes the ledger release-ready",
            severity="pass"
            if store.release_ready
            else "warning"
            if store.entry_count
            else "blocker",
        ),
        _finding(
            7,
            "accepted-conservation",
            store.accepted
            == (
                store.entry_count > 0
                and operations_ok
                and all(item.passed for item in store.checks)
            ),
            True,
            store.accepted,
            "store acceptance follows its checks and entry count",
            "rebuild the aggregate after changing any check",
        ),
    )
    body = {
        "assurance_id": _text(assurance_id, "review store assurance ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_BOUNDARY,
        "store_address": store.content_address,
        "ledger_address": store.ledger_address,
        "head_address": head_address,
        "findings": findings,
        "finding_count": len(findings),
        "passed_count": sum(item.passed for item in findings),
        "warning_count": sum(not item.passed and item.severity == "warning" for item in findings),
        "blocker_count": sum(not item.passed and item.severity == "blocker" for item in findings),
        "state": "blocked"
        if any(not item.passed and item.severity == "blocker" for item in findings)
        else "warning"
        if any(not item.passed for item in findings)
        else "passed",
        "release_ready": all(item.passed for item in findings),
        "accepted": not any(not item.passed and item.severity == "blocker" for item in findings),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance(
        **body, content_address="pending:assurance"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_from_directory(
    directory: str | Path,
    *,
    assurance_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store-assurance",
) -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance
):
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            directory
        ),
        assurance_id=assurance_id,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
) -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance
):
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
    ):
        raise ValidationError("review store assurance verification requires a typed assurance")
    for finding in value.findings:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_finding(
                finding
            )
            != finding.content_address
        ):
            raise ValidationError("review store assurance finding address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review store assurance address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "finding_id",
        "kind",
        "severity",
        "passed",
        "expected",
        "observed",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for finding in value.findings:
        row = finding.to_dict()
        row["expected"] = canonical_json(row["expected"])
        row["observed"] = canonical_json(row["observed"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
        value
    )
    lines = [
        "# Durable Release-Window Review Store Assurance",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- findings: `{value.finding_count}`; passed: `{value.passed_count}`; warnings: `{value.warning_count}`; blockers: `{value.blocker_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.kind} | {item.severity} | {str(item.passed).lower()} | {item.detail} |"
        for item in value.findings
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance,
    *,
    severity: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
        value
    )
    if severity is not None and severity not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceSeverity
    }:
        raise ValidationError("review store assurance query severity is invalid")
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("review store assurance query passed filter is invalid")
    if text is not None:
        text = _text(text, "review store assurance query text")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review store assurance query offset is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 512:
        raise ValidationError("review store assurance query limit is invalid")
    rows = [finding.to_dict() for finding in value.findings]
    if severity is not None:
        rows = [row for row in rows if row["severity"] == severity]
    if passed is not None:
        rows = [row for row in rows if row["passed"] is passed]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {"severity": severity, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "assurance": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review store assurance query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_PREFIX
            + "-query",
        )
        != value["content_address"]
    ):
        raise ValidationError("review store assurance query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "finding_id",
        "kind",
        "severity",
        "passed",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value.get("items", []):
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query(
        value
    )
    lines = [
        "# Durable Review Store Assurance Query",
        "",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | {row.get('kind', '')} | {row.get('severity', '')} | {str(row.get('passed', '')).lower()} | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_BOUNDARY,
        "severities": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceSeverity
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssuranceState
        ],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_VERSION,
        "operations": ["build", "verify", "query", "json", "csv", "markdown"],
        "independent": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_PREFIX
        + "-query-v1",
        "filters": ["severity", "passed", "text", "offset", "limit"],
        "bounded": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE_PREFIX
        + "-query-v1",
        "resources": ["findings"],
        "exports": ["json", "csv", "markdown"],
        "identity_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_ASSURANCE"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreAssurance"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance"
    )
]
