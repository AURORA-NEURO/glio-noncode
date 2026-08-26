"""Typed contracts for per-module certification and contract coverage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

MODULE_CERTIFICATION_VERSION = "module-certification-v1"
MODULE_CERTIFICATION_BOUNDARY = "public_aggregate_module_certification"
MODULE_CERTIFICATION_MAX_MODULES = 20000
MODULE_CERTIFICATION_MAX_CHECKS = 200000
MODULE_CERTIFICATION_MAX_GAPS = 200000
MODULE_CERTIFICATION_MAX_TASKS = 200000
MODULE_CERTIFICATION_MAX_EVENTS = 256
MODULE_CERTIFICATION_MAX_LIMIT = 512
MODULE_CERTIFICATION_DEFAULT_LIMIT = 50


class CertificationState(StrEnum):
    CERTIFIED = "certified"
    REVIEW = "review"
    BLOCKED = "blocked"
    UNCOVERED = "uncovered"


class CertificationCheckKind(StrEnum):
    PARSE = "parse"
    SYMBOL = "symbol"
    DEPENDENCY = "dependency"
    TEST = "test"
    DOCUMENTATION = "documentation"
    EXPORT = "export"
    BOUNDARY = "boundary"
    SCALE = "scale"


class CertificationCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class CertificationResource(StrEnum):
    MODULES = "modules"
    CHECKS = "checks"
    GAPS = "gaps"
    TASKS = "tasks"
    EVENTS = "events"
    METRICS = "metrics"


class CertificationCheckPlane(StrEnum):
    INVENTORY = "inventory"
    COVERAGE = "coverage"
    POLICY = "policy"
    PUBLIC = "public"


class CertificationStageState(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class CertificationTaskKind(StrEnum):
    REPAIR_PARSE = "repair_parse"
    ADD_TEST_COVERAGE = "add_test_coverage"
    ADD_DOCUMENTATION = "add_documentation"
    REVIEW_EXPORT = "review_export"
    REPAIR_DEPENDENCY = "repair_dependency"
    REVIEW_BOUNDARY = "review_boundary"
    REVIEW_MODULE = "review_module"


class CertificationGateState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")


def _tuple_text(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleCertificationCheck:
    """One module-level contract check with static evidence."""

    kind: CertificationCheckKind
    state: CertificationCheckState
    observed: Any
    required: Any
    detail: str
    evidence: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")
        _tuple_text(self.evidence, "evidence")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationRow:
    """Conserved per-module certification result."""

    module_id: str
    family: str
    role: str
    physical_lines: int
    public_symbol_count: int
    checks: tuple[ModuleCertificationCheck, ...]
    passed_count: int
    failed_count: int
    not_applicable_count: int
    score: float
    state: CertificationState
    gap_count: int
    content_address: str

    def __post_init__(self) -> None:
        for field in ("module_id", "family", "role", "content_address"):
            _text(getattr(self, field), field)
        if self.physical_lines < 0 or self.public_symbol_count < 0:
            raise ValidationError("module certification row counters cannot be negative")
        if min(self.passed_count, self.failed_count, self.not_applicable_count, self.gap_count) < 0:
            raise ValidationError("module certification row counts cannot be negative")
        if self.passed_count + self.failed_count + self.not_applicable_count != len(self.checks):
            raise ValidationError("module certification check counts do not conserve rows")
        if not 0.0 <= self.score <= 1.0:
            raise ValidationError("module certification score must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationGap:
    """One actionable missing or failed contract surface."""

    gap_id: str
    module_id: str
    kind: CertificationCheckKind
    priority: int
    detail: str
    next_action: str
    evidence: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in ("gap_id", "module_id", "detail", "next_action", "content_address"):
            _text(getattr(self, field), field)
        if self.priority < 0 or self.priority > 100:
            raise ValidationError("module certification gap priority is invalid")
        _tuple_text(self.evidence, "evidence")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationMatrix:
    """Whole-project module certification matrix."""

    inventory_address: str
    rows: tuple[ModuleCertificationRow, ...]
    gaps: tuple[ModuleCertificationGap, ...]
    check_kind_count: int
    module_count: int
    certified_count: int
    review_count: int
    blocked_count: int
    uncovered_count: int
    overall_score: float
    overall_percent: float
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.inventory_address, "inventory_address")
        _text(self.content_address, "content_address")
        if tuple(item.module_id for item in self.rows) != tuple(
            sorted(item.module_id for item in self.rows)
        ):
            raise ValidationError("module certification rows must be sorted")
        if self.module_count != len(self.rows):
            raise ValidationError("module certification module count does not conserve rows")
        if self.check_kind_count < 1:
            raise ValidationError("module certification check kinds are required")
        if not 0.0 <= self.overall_score <= 1.0 or not 0.0 <= self.overall_percent <= 100.0:
            raise ValidationError("module certification aggregate score is invalid")
        if (
            sum((self.certified_count, self.review_count, self.blocked_count, self.uncovered_count))
            != self.module_count
        ):
            raise ValidationError("module certification state counts do not conserve modules")

    @property
    def gap_count(self) -> int:
        return len(self.gaps)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_CERTIFICATION_VERSION,
            "inventory_address": self.inventory_address,
            "module_count": self.module_count,
            "check_kind_count": self.check_kind_count,
            "gap_count": self.gap_count,
            "certified_count": self.certified_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "uncovered_count": self.uncovered_count,
            "overall_score": self.overall_score,
            "overall_percent": self.overall_percent,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["rows"] = [item.to_dict() for item in self.rows]
            result["gaps"] = [item.to_dict() for item in self.gaps]
        return result


@dataclass(frozen=True, slots=True)
class ModuleCertificationTask:
    """Stable task derived from a certification gap."""

    task_id: str
    module_id: str
    kind: CertificationTaskKind
    priority: int
    reason: str
    gap_ids: tuple[str, ...]
    evidence: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in ("task_id", "module_id", "reason", "content_address"):
            _text(getattr(self, field), field)
        if self.priority < 0 or self.priority > 100:
            raise ValidationError("module certification task priority is invalid")
        _tuple_text(self.gap_ids, "gap_ids")
        _tuple_text(self.evidence, "evidence")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationTaskPlan:
    """Ordered remediation plan over certification gaps."""

    matrix_address: str
    tasks: tuple[ModuleCertificationTask, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.matrix_address, "matrix_address")
        _text(self.content_address, "content_address")
        order = tuple(
            (item.priority, item.kind.value, item.module_id, item.task_id) for item in self.tasks
        )
        if order != tuple(sorted(order)):
            raise ValidationError("module certification tasks must be priority ordered")

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result = {
            "version": MODULE_CERTIFICATION_VERSION,
            "matrix_address": self.matrix_address,
            "task_count": self.task_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["tasks"] = [item.to_dict() for item in self.tasks]
        return result


@dataclass(frozen=True, slots=True)
class ModuleCertificationPolicy:
    """Explicit aggregate certification gate thresholds."""

    policy_id: str
    minimum_score: float
    minimum_certified_percent: float
    maximum_blocked_count: int
    maximum_review_count: int
    require_tests_for_domain: bool
    require_documentation_for_integration: bool
    require_export_for_public_symbols: bool
    allow_not_applicable: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_id, "policy_id")
        _text(self.content_address, "content_address")
        if (
            not 0.0 <= self.minimum_score <= 1.0
            or not 0.0 <= self.minimum_certified_percent <= 100.0
        ):
            raise ValidationError("module certification policy score thresholds are invalid")
        if self.maximum_blocked_count < 0 or self.maximum_review_count < 0:
            raise ValidationError("module certification policy counts cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationGateCheck:
    """One aggregate certification policy check."""

    check_id: str
    plane: CertificationCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            _text(getattr(self, field), field)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationGate:
    """Release decision over the complete certification matrix."""

    matrix_address: str
    plan_address: str
    policy: ModuleCertificationPolicy
    checks: tuple[ModuleCertificationGateCheck, ...]
    state: CertificationGateState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("matrix_address", "plan_address", "content_address"):
            _text(getattr(self, field), field)
        if not self.checks:
            raise ValidationError("module certification gate requires checks")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("module certification gate acceptance does not conserve checks")
        if (self.state is CertificationGateState.ACCEPTED) != self.accepted:
            raise ValidationError("module certification gate state does not match acceptance")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_CERTIFICATION_VERSION,
            "matrix_address": self.matrix_address,
            "plan_address": self.plan_address,
            "policy": self.policy.to_dict(),
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleCertificationStage:
    """One timestamp-free certification runtime stage."""

    stage_id: str
    order: int
    state: CertificationStageState
    input_count: int
    output_count: int
    issue_count: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("stage_id", "detail", "content_address"):
            _text(getattr(self, field), field)
        if self.order < 1 or min(self.input_count, self.output_count, self.issue_count) < 0:
            raise ValidationError("module certification stage counters are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationRuntime:
    """Reproducible certification runtime receipt."""

    runtime_id: str
    version: str
    stages: tuple[ModuleCertificationStage, ...]
    inventory_address: str
    matrix_address: str
    plan_address: str
    gate_address: str
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "runtime_id",
            "version",
            "inventory_address",
            "matrix_address",
            "plan_address",
            "gate_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if tuple(item.order for item in self.stages) != tuple(range(1, len(self.stages) + 1)):
            raise ValidationError("module certification runtime stages must be contiguous")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationEvent:
    """Stable event row for certification observability."""

    sequence: int
    event_type: str
    module_id: str
    state: str
    value: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("event_type", "module_id", "state", "detail", "content_address"):
            _text(getattr(self, field), field)
        if self.sequence < 1 or self.value < 0:
            raise ValidationError("module certification event counters are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationMetric:
    """Aggregate certification metric."""

    metric_id: str
    category: str
    value: float
    unit: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("metric_id", "category", "unit", "content_address"):
            _text(getattr(self, field), field)
        if self.value < 0:
            raise ValidationError("module certification metric value cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationObservability:
    """Bounded events and metrics for a certification matrix."""

    matrix_address: str
    events: tuple[ModuleCertificationEvent, ...]
    metrics: tuple[ModuleCertificationMetric, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.matrix_address, "matrix_address")
        _text(self.content_address, "content_address")
        if len(self.events) > MODULE_CERTIFICATION_MAX_EVENTS:
            raise ValidationError("module certification event limit exceeded")
        if tuple(item.sequence for item in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("module certification events must be contiguous")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_CERTIFICATION_VERSION,
            "matrix_address": self.matrix_address,
            "event_count": len(self.events),
            "events": [item.to_dict() for item in self.events],
            "metric_count": len(self.metrics),
            "metrics": [item.to_dict() for item in self.metrics],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleCertificationAuditCheck:
    """One independent integrity check over the certification closure."""

    check_id: str
    plane: CertificationCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            _text(getattr(self, field), field)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationAudit:
    """Independent audit receipt for matrix, task, gate, and runtime closure."""

    matrix_address: str
    checks: tuple[ModuleCertificationAuditCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.matrix_address, "matrix_address")
        _text(self.content_address, "content_address")
        if not self.checks:
            raise ValidationError("certification audit requires checks")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("certification audit acceptance does not conserve checks")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_CERTIFICATION_VERSION,
            "matrix_address": self.matrix_address,
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


__all__ = [
    "CertificationCheckKind",
    "CertificationCheckPlane",
    "CertificationCheckState",
    "CertificationGateState",
    "CertificationResource",
    "CertificationStageState",
    "CertificationState",
    "CertificationTaskKind",
    "MODULE_CERTIFICATION_BOUNDARY",
    "MODULE_CERTIFICATION_DEFAULT_LIMIT",
    "MODULE_CERTIFICATION_MAX_CHECKS",
    "MODULE_CERTIFICATION_MAX_EVENTS",
    "MODULE_CERTIFICATION_MAX_GAPS",
    "MODULE_CERTIFICATION_MAX_LIMIT",
    "MODULE_CERTIFICATION_MAX_MODULES",
    "MODULE_CERTIFICATION_MAX_TASKS",
    "MODULE_CERTIFICATION_VERSION",
    "ModuleCertificationAudit",
    "ModuleCertificationAuditCheck",
    "ModuleCertificationCheck",
    "ModuleCertificationEvent",
    "ModuleCertificationGate",
    "ModuleCertificationGateCheck",
    "ModuleCertificationGap",
    "ModuleCertificationMatrix",
    "ModuleCertificationMetric",
    "ModuleCertificationObservability",
    "ModuleCertificationPolicy",
    "ModuleCertificationRow",
    "ModuleCertificationRuntime",
    "ModuleCertificationStage",
    "ModuleCertificationTask",
    "ModuleCertificationTaskPlan",
]
