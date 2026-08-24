"""Contracts for executing and reconciling the sixteen domain runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


class ProgramRuntimeState(StrEnum):
    """Aggregate disposition of one program execution."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


class ProgramRuntimeCheckCategory(StrEnum):
    """Stable check planes for domain orchestration."""

    CATALOG = "catalog"
    RESOLUTION = "resolution"
    EXECUTION = "execution"
    INTEGRITY = "integrity"
    PUBLIC_BOUNDARY = "public_boundary"
    RECONCILIATION = "reconciliation"
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class ArchitectureProgramSpec:
    """Executable fixture/runtime pair for one domain."""

    domain_id: str
    domain: str
    fixture_reference: str
    runtime_reference: str
    dependency_order: int
    boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("domain_id", "domain", "fixture_reference", "runtime_reference", "boundary"):
            require_non_empty(str(getattr(self, field)), field)
        if self.dependency_order < 1 or ":" not in self.content_address:
            raise ValueError("program specs require positive order and content address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeCheck:
    """One addressed aggregate-program observation."""

    check_id: str
    domain_id: str
    category: ProgramRuntimeCheckCategory
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ArchitectureProgramReceipt:
    """Normalized public receipt for one heterogeneous domain runtime."""

    domain_id: str
    domain: str
    fixture_reference: str
    runtime_reference: str
    fixture_resolution: str
    runtime_resolution: str
    fixture_address: str
    runtime_address: str
    runtime_state: str
    accepted: bool
    stage_count: int
    evaluation_check_count: int
    artifact_count: int
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ArchitectureProgramReport:
    """Complete sixteen-domain execution and reconciliation report."""

    report_id: str
    specs: tuple[ArchitectureProgramSpec, ...]
    receipts: tuple[ArchitectureProgramReceipt, ...]
    checks: tuple[ProgramRuntimeCheck, ...]
    state: ProgramRuntimeState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is ProgramRuntimeState.ACCEPTED

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    @property
    def total_stage_count(self) -> int:
        return sum(item.stage_count for item in self.receipts)

    @property
    def total_evaluation_check_count(self) -> int:
        return sum(item.evaluation_check_count for item in self.receipts)

    @property
    def total_artifact_count(self) -> int:
        return sum(item.artifact_count for item in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "specs": [item.to_dict() for item in self.specs],
            "receipts": [item.to_dict() for item in self.receipts],
            "checks": [item.to_dict() for item in self.checks],
            "state": self.state.value,
            "accepted": self.accepted,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "total_stage_count": self.total_stage_count,
            "total_evaluation_check_count": self.total_evaluation_check_count,
            "total_artifact_count": self.total_artifact_count,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ProgramRuntimeStage:
    """Ordered program-level stage with predecessor and output addresses."""

    stage_id: str
    ordinal: int
    state: ProgramRuntimeState
    predecessor_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeQualityCheck:
    """Independent quality assertion for the aggregate runtime."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeQualityReport:
    """Quality gate over all domain receipts and aggregate checks."""

    report_address: str
    checks: tuple[ProgramRuntimeQualityCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_address": self.report_address,
            "checks": [item.to_dict() for item in self.checks],
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ProgramRuntime:
    """End-to-end runtime wrapping report, quality, and ordered stages."""

    run_id: str
    report: ArchitectureProgramReport
    quality: ProgramRuntimeQualityReport
    stages: tuple[ProgramRuntimeStage, ...]
    state: ProgramRuntimeState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is ProgramRuntimeState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "report": self.report.to_dict(),
            "quality": self.quality.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": len(self.stages),
            "state": self.state.value,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def addressed(value: Any, prefix: str) -> str:
    """Content-address a program projection with a semantic prefix."""

    return content_hash(jsonable(value), prefix=prefix)


__all__ = [
    "ArchitectureProgramReceipt",
    "ArchitectureProgramReport",
    "ArchitectureProgramSpec",
    "ProgramRuntime",
    "ProgramRuntimeCheck",
    "ProgramRuntimeCheckCategory",
    "ProgramRuntimeQualityCheck",
    "ProgramRuntimeQualityReport",
    "ProgramRuntimeStage",
    "ProgramRuntimeState",
    "addressed",
]
