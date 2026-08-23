"""Explicit contracts for the D14 C13-C16 evidence-release frontier.

The release surface is intentionally separate from the broad lifecycle modules.  It
is a small, deterministic boundary for four high-risk transitions: reclassifying
evidence, retiring or superseding records, assembling an audit bundle, and signing
and verifying a research dossier.  Every object carries a content address so a
reviewer can compare a run without relying on mutable timestamps or database state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty

EVIDENCE_RELEASE_FRONTIER_VERSION = "2026.08.d14-c13-c16.v1"
EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
EVIDENCE_RELEASE_FRONTIER_BOUNDARY = "public_aggregate_evidence_lifecycle_release"


class EvidenceReleaseOperation(StrEnum):
    RECLASSIFICATION = "reclassification"
    SUPERSESSION = "supersession"
    REPRODUCIBILITY_BUNDLE = "reproducibility_bundle"
    SIGNED_DOSSIER = "signed_dossier"


class EvidenceReleaseRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class EvidenceReleaseState(StrEnum):
    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"
    RECLASSIFIED = "reclassified"
    SUPERSEDED = "superseded"
    BUNDLED = "bundled"
    SIGNED = "signed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class EvidenceReleaseSourceReceipt:
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
            raise ValueError("evidence-release receipts require HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("evidence-release receipts require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseRecord:
    record_id: str
    capability: str
    operation: EvidenceReleaseOperation
    role: EvidenceReleaseRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: EvidenceReleaseState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.capability, "capability")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.notes, "notes")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("evidence-release records require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[EvidenceReleaseSourceReceipt, ...]
    records: tuple[EvidenceReleaseRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[EvidenceReleaseRecord, ...]:
        return tuple(row for row in self.records if row.role == EvidenceReleaseRole.POSITIVE)

    @property
    def control_records(self) -> tuple[EvidenceReleaseRecord, ...]:
        return tuple(row for row in self.records if row.role == EvidenceReleaseRole.CONTROL)

    @property
    def operation_names(self) -> tuple[str, ...]:
        return tuple(sorted({row.operation.value for row in self.records}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseOperationResult:
    operation: EvidenceReleaseOperation
    state: EvidenceReleaseState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state not in {EvidenceReleaseState.REJECTED, EvidenceReleaseState.BLOCKED}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseExecution:
    record_id: str
    capability: str
    operation: EvidenceReleaseOperation
    role: EvidenceReleaseRole
    expected_state: EvidenceReleaseState
    observed_state: EvidenceReleaseState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseCheck:
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
class EvidenceReleaseEvaluation:
    fixture_id: str
    executions: tuple[EvidenceReleaseExecution, ...]
    checks: tuple[EvidenceReleaseCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def make_evidence_release_check(check_id: str, record_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceReleaseCheck:
    body = {"check_id": check_id, "record_id": record_id, "plane": plane, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return EvidenceReleaseCheck(**body, content_address=content_hash(body))


__all__ = [
    "EVIDENCE_RELEASE_FRONTIER_BOUNDARY",
    "EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY",
    "EVIDENCE_RELEASE_FRONTIER_FOREIGN_CONTEXT",
    "EVIDENCE_RELEASE_FRONTIER_VERSION",
    "EvidenceReleaseCheck",
    "EvidenceReleaseExecution",
    "EvidenceReleaseFixture",
    "EvidenceReleaseOperation",
    "EvidenceReleaseOperationResult",
    "EvidenceReleaseRecord",
    "EvidenceReleaseRole",
    "EvidenceReleaseSourceReceipt",
    "EvidenceReleaseState",
    "EvidenceReleaseEvaluation",
    "make_evidence_release_check",
]
