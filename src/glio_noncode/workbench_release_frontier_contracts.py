"""Contracts for the D15 C13-C16 workbench-release frontier.

This boundary makes review forms, report exports, search, and accessibility
evidence independently testable. It stores public aggregate records and stable
receipts; it does not attach user-session values or hidden metadata to a release.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty

WORKBENCH_RELEASE_FRONTIER_VERSION = "2026.08.d15-c13-c16.v1"
WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
WORKBENCH_RELEASE_FRONTIER_BOUNDARY = "public_aggregate_workbench_release"


class WorkbenchReleaseOperation(StrEnum):
    REVIEW_FORM = "review_form"
    REPORT_EXPORT = "report_export"
    SEARCH_PALETTE = "search_palette"
    ACCESSIBILITY = "accessibility"


class WorkbenchReleaseRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class WorkbenchReleaseState(StrEnum):
    READY = "ready"
    REVIEWED = "reviewed"
    EXPORTED = "exported"
    SEARCHED = "searched"
    PASSED = "passed"
    REVIEW = "review"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseSourceReceipt:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("source_id", "title", "uri", "scope", "version", "content_address"):
            require_non_empty(str(getattr(self, field)), field)
        if not self.uri.startswith("https://"):
            raise ValueError("workbench receipts require HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("workbench receipts require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseRecord:
    record_id: str
    capability: str
    operation: WorkbenchReleaseOperation
    role: WorkbenchReleaseRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: WorkbenchReleaseState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.capability, "capability")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.notes, "notes")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("workbench records require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[WorkbenchReleaseSourceReceipt, ...]
    records: tuple[WorkbenchReleaseRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[WorkbenchReleaseRecord, ...]:
        return tuple(row for row in self.records if row.role == WorkbenchReleaseRole.POSITIVE)

    @property
    def control_records(self) -> tuple[WorkbenchReleaseRecord, ...]:
        return tuple(row for row in self.records if row.role == WorkbenchReleaseRole.CONTROL)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOperationResult:
    operation: WorkbenchReleaseOperation
    state: WorkbenchReleaseState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseExecution:
    record_id: str
    capability: str
    operation: WorkbenchReleaseOperation
    role: WorkbenchReleaseRole
    expected_state: WorkbenchReleaseState
    observed_state: WorkbenchReleaseState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseCheck:
    check_id: str
    record_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseEvaluation:
    fixture_id: str
    executions: tuple[WorkbenchReleaseExecution, ...]
    checks: tuple[WorkbenchReleaseCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def make_workbench_release_check(check_id: str, record_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> WorkbenchReleaseCheck:
    body = {"check_id": check_id, "record_id": record_id, "plane": plane, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return WorkbenchReleaseCheck(**body, content_address=content_hash(body))


__all__ = [
    "WORKBENCH_RELEASE_FRONTIER_BOUNDARY", "WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY", "WORKBENCH_RELEASE_FRONTIER_FOREIGN_CONTEXT", "WORKBENCH_RELEASE_FRONTIER_VERSION",
    "WorkbenchReleaseCheck", "WorkbenchReleaseExecution", "WorkbenchReleaseFixture", "WorkbenchReleaseOperation", "WorkbenchReleaseOperationResult", "WorkbenchReleaseRecord", "WorkbenchReleaseRole", "WorkbenchReleaseSourceReceipt", "WorkbenchReleaseState", "WorkbenchReleaseEvaluation", "make_workbench_release_check",
]
