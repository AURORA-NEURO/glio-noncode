"""Contracts for the D13 C05-C08 editing-design frontier."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping
from .serialization import content_hash, jsonable, require_non_empty

EDITING_DESIGN_FRONTIER_VERSION = "2026.08.d13-c05-c08.v1"
EDITING_DESIGN_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
EDITING_DESIGN_FRONTIER_BOUNDARY = "public_aggregate_editing_design_planning"

class EditingDesignOperation(StrEnum):
    CRISPR_DESIGN = "crispr_design"
    BASE_EDITING = "base_editing"
    PRIME_EDITING = "prime_editing"
    ALLELE_REPORTER = "allele_specific_reporter"

class EditingDesignRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"

class EditingDesignState(StrEnum):
    DESIGNED = "designed"
    REVIEW = "review"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    ABSTAINED = "abstained"

@dataclass(frozen=True, slots=True)
class EditingDesignSourceReceipt:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    content_address: str
    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "scope", "version", "content_address"): require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"): raise ValueError("editing-design sources require HTTPS")
        if not self.content_address.startswith("sha256:"): raise ValueError("editing-design sources require SHA-256")
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignRecord:
    record_id: str
    capability: str
    operation: EditingDesignOperation
    role: EditingDesignRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: EditingDesignState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str
    def __post_init__(self) -> None:
        for name in ("record_id", "capability", "context_key", "notes", "content_address"): require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids: raise ValueError("editing-design records require source joins")
        if not self.content_address.startswith("sha256:"): raise ValueError("editing-design records require SHA-256")
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[EditingDesignSourceReceipt, ...]
    records: tuple[EditingDesignRecord, ...]
    content_address: str
    @property
    def positive_records(self) -> tuple[EditingDesignRecord, ...]: return tuple(item for item in self.records if item.role == EditingDesignRole.POSITIVE)
    @property
    def control_records(self) -> tuple[EditingDesignRecord, ...]: return tuple(item for item in self.records if item.role == EditingDesignRole.CONTROL)
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignOperationResult:
    operation: EditingDesignOperation
    state: EditingDesignState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignExecution:
    record_id: str
    capability: str
    operation: EditingDesignOperation
    role: EditingDesignRole
    expected_state: EditingDesignState
    observed_state: EditingDesignState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignCheck:
    check_id: str
    record_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignEvaluation:
    fixture_id: str
    executions: tuple[EditingDesignExecution, ...]
    checks: tuple[EditingDesignCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def make_editing_design_check(check_id: str, record_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> EditingDesignCheck:
    body = {"check_id": check_id, "record_id": record_id, "plane": plane, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return EditingDesignCheck(**body, content_address=content_hash(body))

__all__ = ["EDITING_DESIGN_FRONTIER_BOUNDARY", "EDITING_DESIGN_FRONTIER_CONTEXT_KEY", "EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT", "EDITING_DESIGN_FRONTIER_VERSION", "EditingDesignCheck", "EditingDesignExecution", "EditingDesignFixture", "EditingDesignOperation", "EditingDesignOperationResult", "EditingDesignRecord", "EditingDesignRole", "EditingDesignSourceReceipt", "EditingDesignState", "EditingDesignEvaluation", "make_editing_design_check"]
