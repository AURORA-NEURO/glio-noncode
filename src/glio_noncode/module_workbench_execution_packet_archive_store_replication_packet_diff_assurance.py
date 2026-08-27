"""Independent assurance report for packet diffs and release decisions.

The diff engine describes changes and the release engine applies a strict
promotion policy.  Assurance is a separate, human-oriented control plane: it
retains why a decision passed, was held, or was blocked, assigns bounded
severity to each finding, and can be queried without reopening either packet
directory.  It does not mutate packets or turn a warning into an approval.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_runtime import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_"
    "diff_assurance"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_FINDING_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-finding"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_QUERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_MAX_LIMIT = 512


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity:
    """Severity values are strings to keep public projections simple."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState:
    """Aggregate assurance outcome."""

    ACCEPTED = "accepted"
    HOLD = "hold"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field)
    if ":" not in normalized:
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _count(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _ratio(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or value < 0 or value > 1:
        raise ValidationError(f"{field} must be between zero and one")


def _public_boundary(value: Any) -> bool:
    forbidden = {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "author",
        "author_id",
        "codex",
        "email",
        "hostname",
        "model",
        "openai",
        "private",
        "token",
        "user",
        "username",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public_boundary(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return all(_public_boundary(item) for item in value)
    return True


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding:
    """One severity-bearing assurance finding."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        plane: str,
        severity: str,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.plane = plane
        self.severity = severity
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "assurance finding ordinal")
        _text(self.finding_id, "assurance finding ID", 256)
        _text(self.plane, "assurance finding plane", 128)
        _text(self.severity, "assurance finding severity", 64)
        _text(self.detail, "assurance finding detail", 4096)
        _text(self.remediation, "assurance finding remediation", 4096)
        _address(self.content_address, "assurance finding address")
        if self.severity not in {
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.INFO,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.WARNING,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER,
        }:
            raise ValidationError("assurance finding severity is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("assurance finding passed flag must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "plane": self.plane,
            "severity": self.severity,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_finding(  # noqa: E501
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding,
) -> str:
    """Recompute a finding address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_FINDING_PREFIX,
    )


def _finding(
    finding_id: str,
    plane: str,
    severity: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    remediation: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding:
    body = {
        "ordinal": 0,
        "finding_id": finding_id,
        "plane": plane,
        "severity": severity,
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
        "remediation": remediation,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_FINDING_PREFIX
        + ":pending-finding",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_finding(
            provisional
        ),
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport:
    """Bounded, addressed assurance aggregate."""

    def __init__(
        self,
        assurance_id: str,
        version: str,
        boundary: str,
        diff_address: str,
        release_address: str,
        runtime_address: str | None,
        findings: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding, ...
        ],
        finding_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        score: float,
        state: str,
        release_ready: bool,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.diff_address = diff_address
        self.release_address = release_address
        self.runtime_address = runtime_address
        self.findings = findings
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.score = score
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "assurance ID")
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_VERSION  # noqa: E501
        ):
            raise ValidationError("assurance version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_BOUNDARY  # noqa: E501
        ):
            raise ValidationError("assurance boundary is invalid")
        for value, field in (
            (self.diff_address, "assurance diff address"),
            (self.release_address, "assurance release address"),
            (self.content_address, "assurance address"),
        ):
            _address(value, field)
        if self.runtime_address is not None:
            _address(self.runtime_address, "assurance runtime address")
        for value, field in (
            (self.finding_count, "finding count"),
            (self.passed_count, "passed finding count"),
            (self.warning_count, "warning count"),
            (self.blocker_count, "blocker count"),
        ):
            _count(value, field)
        _ratio(self.score, "assurance score")
        _text(self.detail, "assurance detail", 8192)
        if self.finding_count != len(self.findings):
            raise ValidationError("finding count does not conserve")
        if self.passed_count != sum(item.passed for item in self.findings):
            raise ValidationError("passed finding count does not conserve")
        if self.warning_count != sum(
            item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.WARNING  # noqa: E501
            and not item.passed
            for item in self.findings
        ):
            raise ValidationError("warning count does not conserve")
        if self.blocker_count != sum(
            item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER  # noqa: E501
            and not item.passed
            for item in self.findings
        ):
            raise ValidationError("blocker count does not conserve")
        if not isinstance(self.release_ready, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("assurance flags must be boolean")
        if self.state not in {
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.ACCEPTED,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.HOLD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.BLOCKED,
        }:
            raise ValidationError("assurance state is invalid")
        if self.accepted != (
            self.state
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.BLOCKED
        ):
            raise ValidationError("assurance acceptance does not conserve")
        if self.release_ready and self.blocker_count:
            raise ValidationError("release readiness cannot coexist with blockers")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "assurance_address": self.content_address,
            "diff_address": self.diff_address,
            "release_address": self.release_address,
            "runtime_address": self.runtime_address,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "score": self.score,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "diff_address": self.diff_address,
            "release_address": self.release_address,
            "runtime_address": self.runtime_address,
            "findings": tuple(item.to_dict() for item in self.findings),
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "score": self.score,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
) -> str:
    """Recompute an assurance report address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_PREFIX,
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    release: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime | None = None,
    *,
    assurance_id: str = (  # noqa: E501
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-assurance"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport:
    """Build an independent severity-bearing assurance report."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff(diff)
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(release)
    if runtime is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
            runtime
        )
    findings = [
        _finding(
            "assurance-diff-integrity",
            "diff",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER,
            diff.accepted,
            diff.accepted,
            True,
            "packet diff structure must verify",
            "rebuild the comparison from two verified packet boundaries",
        ),
        _finding(
            "assurance-candidate-acceptance",
            "candidate",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER,
            diff.right_accepted,
            diff.right_accepted,
            True,
            "candidate packet must be internally accepted",
            "repair candidate packet checks before release review",
        ),
        _finding(
            "assurance-boundary-state",
            "release",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.WARNING,
            diff.state
            in {
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.MATCHED,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.EXTENDED,
            },
            diff.state,
            "matched or extended",
            "review changed or divergent packet boundaries",
            "inspect changed or divergent packet boundaries before release",
        ),
        _finding(
            "assurance-required-artifacts",
            "artifact",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER,
            diff.removed_required_count == 0,
            diff.removed_required_count,
            0,
            "required artifact removals are not releasable",
            "restore required artifacts or create an explicit migration decision",
        ),
        _finding(
            "assurance-content-changes",
            "artifact",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.WARNING,
            diff.changed_artifact_count == 0,
            diff.changed_artifact_count,
            0,
            "changed artifact bytes need review",
            "inspect changed artifact addresses and approve the new evidence",
        ),
        _finding(
            "assurance-release-decision",
            "release",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.WARNING,
            release.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE,  # noqa: E501
            release.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE,
            "release state must be promotable",
            "resolve every release check before promotion",
        ),
        _finding(
            "assurance-public-boundary",
            "public",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER,
            _public_boundary({"diff": diff.to_dict(), "release": release.to_dict()}),
            _public_boundary({"diff": diff.to_dict(), "release": release.to_dict()}),
            True,
            "public projections must remain identity-free",
            "remove private or attribution fields from the public boundary",
        ),
    ]
    if runtime is not None:
        findings.append(
            _finding(
                "assurance-runtime-closure",
                "runtime",
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER,
                runtime.accepted and runtime.blocked_count == 0,
                {"accepted": runtime.accepted, "blocked_count": runtime.blocked_count},
                {"accepted": True, "blocked_count": 0},
                "diff runtime must close without blocked stages",
                "rerun the ordered diff runtime after resolving its blocked stage",
            )
        )
    for ordinal, item in enumerate(findings):
        findings[ordinal] = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding(
                ordinal=ordinal,
                finding_id=item.finding_id,
                plane=item.plane,
                severity=item.severity,
                passed=item.passed,
                observed=item.observed,
                expected=item.expected,
                detail=item.detail,
                remediation=item.remediation,
                content_address="pending:assurance-finding",
            )
        )
        findings[ordinal] = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceFinding(
                ordinal=ordinal,
                finding_id=item.finding_id,
                plane=item.plane,
                severity=item.severity,
                passed=item.passed,
                observed=item.observed,
                expected=item.expected,
                detail=item.detail,
                remediation=item.remediation,
                content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_finding(
                    findings[ordinal]
                ),
            )
        )
    passed_count = sum(item.passed for item in findings)
    blocker_count = sum(
        item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.BLOCKER
        and not item.passed
        for item in findings
    )
    warning_count = sum(
        item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceSeverity.WARNING
        and not item.passed
        for item in findings
    )
    if blocker_count:
        state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.BLOCKED
        )
    elif warning_count:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.HOLD
    else:
        state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.ACCEPTED
        )
    body = {
        "assurance_id": assurance_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_VERSION,  # noqa: E501
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_BOUNDARY,  # noqa: E501
        "diff_address": diff.content_address,
        "release_address": release.content_address,
        "runtime_address": runtime.content_address if runtime is not None else None,
        "findings": tuple(findings),
        "finding_count": len(findings),
        "passed_count": passed_count,
        "warning_count": warning_count,
        "blocker_count": blocker_count,
        "score": passed_count / max(len(findings), 1),
        "state": state,
        "release_ready": release.accepted and blocker_count == 0 and warning_count == 0,
        "accepted": state
        != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.BLOCKED,
        "detail": "independent packet diff assurance completed",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_PREFIX
        + ":pending-assurance",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport:
    """Verify finding addresses and the aggregate assurance address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
    ):
        raise ValidationError("assurance verification requires a typed report")
    for item in value.findings:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_finding(
                item
            )
            != item.content_address
        ):
            raise ValidationError("assurance finding address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
            value
        )
        != value.content_address
    ):
        raise ValidationError("assurance report address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(value)
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
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.findings:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_markdown(  # noqa: E501
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
) -> str:
    """Render a severity-aware assurance report."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(value)
    lines = [
        "# Archive Store Replication Packet Diff Assurance",
        "",
        f"- Assurance: `{value.assurance_id}`",
        f"- Address: `{value.content_address}`",
        f"- State: `{value.state}`",
        f"- Score: `{value.score:.3f}`",
        f"- Findings passed: `{value.passed_count}/{value.finding_count}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        "",
        "| Ordinal | Finding | Plane | Severity | Passed | Detail |",
        "|---:|---|---|---|---:|---|",
    ]
    for item in value.findings:
        lines.append(
            f"| {item.ordinal} | `{item.finding_id}` | `{item.plane}` | "
            f"`{item.severity}` | {str(item.passed).lower()} | {item.detail} |"
        )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceReport,
    *,
    resource: str = "summary",
    severity: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_DEFAULT_LIMIT,  # noqa: E501
) -> dict[str, Any]:
    """Return a bounded assurance summary or finding page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(value)
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_MAX_LIMIT  # noqa: E501
    ):
        raise ValidationError("assurance query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "assurance_id"
    elif normalized == "findings":
        rows = [item.to_dict() for item in value.findings]
        if severity:
            rows = [item for item in rows if item.get("severity") == severity]
        if passed is not None:
            rows = [item for item in rows if item.get("passed") is passed]
        if text:
            needle = text.casefold()
            rows = [item for item in rows if needle in canonical_json(item).casefold()]
        index_used = "finding_id"
    else:
        raise ValidationError("unsupported assurance resource")
    total = len(rows)
    items = rows[offset : offset + limit]
    body = {
        "resource": normalized,
        "query": {"severity": severity, "passed": passed, "text": text},
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": items,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify one addressed assurance query response."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("assurance query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("assurance query address mismatch")
    if value.get("total") < len(value.get("items", ())):
        raise ValidationError("assurance query total is inconsistent")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query(
        value
    )
    output = io.StringIO(newline="")
    fields = ("resource", "ordinal", "finding_id", "plane", "severity", "passed", "detail")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for ordinal, item in enumerate(value.get("items", ())):
        writer.writerow(
            {
                "resource": value.get("resource"),
                "ordinal": ordinal,
                "finding_id": item.get("finding_id"),
                "plane": item.get("plane"),
                "severity": item.get("severity"),
                "passed": item.get("passed"),
                "detail": item.get("detail"),
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_markdown(  # noqa: E501
    value: Mapping[str, Any],
) -> str:
    """Render bounded assurance findings."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Assurance Query",
        "",
        f"- Resource: `{value.get('resource')}`",
        f"- Reference: `{value.get('reference_address')}`",
        f"- Rows: `{len(value.get('items', ()))}/{value.get('total')}`",
        "",
        "| Ordinal | Finding | Plane | Severity | Passed | Detail |",
        "|---:|---|---|---|---:|---|",
    ]
    for ordinal, item in enumerate(value.get("items", ())):
        lines.append(
            f"| {ordinal} | `{item.get('finding_id', '')}` | `{item.get('plane', '')}` | "
            f"`{item.get('severity', '')}` | {str(item.get('passed', '')).lower()} | "
            f"{item.get('detail', '')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_schema() -> (
    dict[str, Any]
):
    """Describe assurance findings and release-readiness states."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_VERSION,  # noqa: E501
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_BOUNDARY,  # noqa: E501
        "states": ["accepted", "hold", "blocked"],
        "severities": ["info", "warning", "blocker"],
        "resources": ["summary", "findings"],
        "limits": {
            "max_findings": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,  # noqa: E501
            "max_query_limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_MAX_LIMIT,  # noqa: E501
        },
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "release_gate": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    """Declare assurance and release-readiness operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_VERSION,  # noqa: E501
        "operations": [
            "audit_packet_diff",
            "classify_blockers",
            "classify_warnings",
            "calculate_bounded_score",
            "evaluate_release_readiness",
            "verify_assurance_report",
            "query_assurance_summary",
            "query_assurance_findings",
            "export_assurance_json",
            "export_assurance_csv",
            "render_assurance_markdown",
        ],
        "guarantees": [
            "independent_assurance_boundary",
            "severity_preservation",
            "blockers_fail_closed",
            "warnings_hold_release",
            "content_addressed_findings",
            "bounded_query_pages",
            "no_filesystem_paths",
            "no_private_or_attribution_fields",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_schema() -> (  # noqa: E501
    dict[str, Any]
):
    """Describe bounded assurance query resources and filters."""

    return {
        "version": (
            "module-workbench-execution-packet-archive-store-replication-packet-"
            "diff-assurance-query-v1"
        ),
        "resources": {"summary": ["summary"], "findings": ["findings"]},
        "filters": ["severity", "passed", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ASSURANCE_MAX_LIMIT
            ),
        },
        "addressed_response": True,
        "path_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    """Declare bounded assurance query and export operations."""

    return {
        "version": (
            "module-workbench-execution-packet-archive-store-replication-packet-"
            "diff-assurance-query-v1"
        ),
        "operations": [
            "query_assurance_summary",
            "query_assurance_findings",
            "filter_severity",
            "filter_passed",
            "filter_text",
            "page_offset_limit",
            "verify_content_address",
            "export_json",
            "export_csv",
            "render_markdown",
        ],
        "guarantees": [
            "bounded_results",
            "deterministic_filters",
            "content_addressed_response",
            "fail_closed_verification",
            "no_filesystem_paths",
        ],
    }
