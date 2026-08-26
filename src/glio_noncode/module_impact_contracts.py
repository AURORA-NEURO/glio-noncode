"""Typed contracts for deterministic module-change impact analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

MODULE_IMPACT_VERSION = "module-impact-v1"
MODULE_IMPACT_BOUNDARY = "public_aggregate_module_impact"
MODULE_IMPACT_MAX_MODULES = 20000
MODULE_IMPACT_MAX_CHANGES = 40000
MODULE_IMPACT_MAX_IMPACTS = 60000
MODULE_IMPACT_MAX_TASKS = 60000
MODULE_IMPACT_MAX_CHECKS = 64
MODULE_IMPACT_MAX_EVENTS = 256
MODULE_IMPACT_DEFAULT_LIMIT = 50
MODULE_IMPACT_MAX_LIMIT = 512


class ImpactChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class ImpactSeverity(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactPropagation(StrEnum):
    DIRECT = "direct"
    DEPENDENT = "dependent"
    TRANSITIVE = "transitive"


class ImpactResource(StrEnum):
    CHANGES = "changes"
    DEPENDENCIES = "dependencies"
    IMPACTS = "impacts"
    TASKS = "tasks"
    CHECKS = "checks"
    EVENTS = "events"
    METRICS = "metrics"


class ImpactStageState(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ImpactCheckPlane(StrEnum):
    INPUT = "input"
    DIFF = "diff"
    GRAPH = "graph"
    POLICY = "policy"
    VERIFICATION = "verification"
    PUBLIC = "public"


class ImpactTaskKind(StrEnum):
    REVIEW_DIRECT_CHANGE = "review_direct_change"
    REPLAY_DEPENDENT = "replay_dependent"
    REVIEW_PUBLIC_SURFACE = "review_public_surface"
    REVIEW_REMOVED_MODULE = "review_removed_module"
    REVIEW_UNRESOLVED_EDGE = "review_unresolved_edge"
    REPLAY_PACKET = "replay_packet"


class ImpactGateState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


def _required_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleImpactChange:
    """A per-module structural change between two immutable inventories."""

    module_id: str
    kind: ImpactChangeKind
    left_address: str | None
    right_address: str | None
    physical_delta: int
    nonblank_delta: int
    public_symbol_delta: int
    import_delta: int
    test_reference_delta: int
    added_symbols: tuple[str, ...]
    removed_symbols: tuple[str, ...]
    changed_symbols: tuple[str, ...]
    added_dependencies: tuple[str, ...]
    removed_dependencies: tuple[str, ...]
    severity: ImpactSeverity
    content_address: str

    def __post_init__(self) -> None:
        _required_text(self.module_id, "module_id")
        _required_text(self.content_address, "content_address")
        if self.left_address is not None:
            _required_text(self.left_address, "left_address")
        if self.right_address is not None:
            _required_text(self.right_address, "right_address")
        for field in (
            "added_symbols",
            "removed_symbols",
            "changed_symbols",
            "added_dependencies",
            "removed_dependencies",
        ):
            _sorted_unique(getattr(self, field), field)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleDependencyChange:
    """An import edge addition, removal, or resolution-state transition."""

    source_module: str
    target_module: str
    import_name: str
    kind: ImpactChangeKind
    relative: bool
    left_resolved: bool | None
    right_resolved: bool | None
    content_address: str

    def __post_init__(self) -> None:
        for field in ("source_module", "target_module", "import_name", "content_address"):
            _required_text(getattr(self, field), field)

    @property
    def key(self) -> str:
        return f"{self.source_module}|{self.target_module}|{self.import_name}"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactDiff:
    """Complete structural diff over module rows and dependency edges."""

    left_inventory_address: str
    right_inventory_address: str
    changes: tuple[ModuleImpactChange, ...]
    dependencies: tuple[ModuleDependencyChange, ...]
    changed_summary_fields: tuple[str, ...]
    summary_delta: Mapping[str, int]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "left_inventory_address",
            "right_inventory_address",
            "content_address",
        ):
            _required_text(getattr(self, field), field)
        if tuple(item.module_id for item in self.changes) != tuple(
            sorted(item.module_id for item in self.changes)
        ):
            raise ValidationError("module impact changes must be module ordered")
        if tuple(item.key for item in self.dependencies) != tuple(
            sorted(item.key for item in self.dependencies)
        ):
            raise ValidationError("module dependency changes must be key ordered")
        _sorted_unique(self.changed_summary_fields, "changed_summary_fields")
        if len(self.changes) > MODULE_IMPACT_MAX_CHANGES:
            raise ValidationError("module impact change limit exceeded")
        if len(self.dependencies) > MODULE_IMPACT_MAX_CHANGES:
            raise ValidationError("module impact dependency limit exceeded")

    @property
    def added_count(self) -> int:
        return sum(item.kind is ImpactChangeKind.ADDED for item in self.changes)

    @property
    def change_count(self) -> int:
        return len(self.changes)

    @property
    def removed_count(self) -> int:
        return sum(item.kind is ImpactChangeKind.REMOVED for item in self.changes)

    @property
    def changed_count(self) -> int:
        return sum(item.kind is ImpactChangeKind.CHANGED for item in self.changes)

    @property
    def dependency_change_count(self) -> int:
        return len(self.dependencies)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_IMPACT_VERSION,
            "left_inventory_address": self.left_inventory_address,
            "right_inventory_address": self.right_inventory_address,
            "change_count": len(self.changes),
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "dependency_change_count": self.dependency_change_count,
            "changed_summary_fields": list(self.changed_summary_fields),
            "summary_delta": dict(self.summary_delta),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["changes"] = [item.to_dict() for item in self.changes]
            result["dependencies"] = [item.to_dict() for item in self.dependencies]
        return result


@dataclass(frozen=True, slots=True)
class ModuleImpactAssessment:
    """One direct or reverse-dependency impact with explainable evidence."""

    module_id: str
    propagation: ImpactPropagation
    distance: int
    severity: ImpactSeverity
    risk_score: float
    direct_change_kind: ImpactChangeKind | None
    changed_sources: tuple[str, ...]
    paths: tuple[str, ...]
    reasons: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        _required_text(self.module_id, "module_id")
        _required_text(self.content_address, "content_address")
        if self.distance < 0:
            raise ValidationError("impact distance cannot be negative")
        if not 0.0 <= self.risk_score <= 100.0:
            raise ValidationError("impact risk score must be between zero and one hundred")
        _sorted_unique(self.changed_sources, "changed_sources")
        _sorted_unique(self.paths, "paths")
        _sorted_unique(self.reasons, "reasons")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactReport:
    """Reverse-dependency closure for a module inventory diff."""

    diff_address: str
    assessments: tuple[ModuleImpactAssessment, ...]
    direct_count: int
    dependent_count: int
    transitive_count: int
    critical_count: int
    high_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("diff_address", "content_address"):
            _required_text(getattr(self, field), field)
        if tuple(item.module_id for item in self.assessments) != tuple(
            sorted(item.module_id for item in self.assessments)
        ):
            raise ValidationError("module impact assessments must be module ordered")
        if len(self.assessments) > MODULE_IMPACT_MAX_IMPACTS:
            raise ValidationError("module impact assessment limit exceeded")

    @property
    def impact_count(self) -> int:
        return len(self.assessments)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_IMPACT_VERSION,
            "diff_address": self.diff_address,
            "impact_count": self.impact_count,
            "direct_count": self.direct_count,
            "dependent_count": self.dependent_count,
            "transitive_count": self.transitive_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["assessments"] = [item.to_dict() for item in self.assessments]
        return result


@dataclass(frozen=True, slots=True)
class ModuleVerificationTask:
    """A deterministic review or replay task derived from impact evidence."""

    task_id: str
    module_id: str
    kind: ImpactTaskKind
    priority: int
    reason: str
    source_modules: tuple[str, ...]
    evidence: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in ("task_id", "module_id", "reason", "content_address"):
            _required_text(getattr(self, field), field)
        if self.priority < 0 or self.priority > 100:
            raise ValidationError("verification task priority must be between zero and one hundred")
        _sorted_unique(self.source_modules, "source_modules")
        _sorted_unique(self.evidence, "evidence")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactVerificationPlan:
    """Stable task plan that turns impact findings into review work."""

    diff_address: str
    impact_address: str
    tasks: tuple[ModuleVerificationTask, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("diff_address", "impact_address", "content_address"):
            _required_text(getattr(self, field), field)
        order = tuple(
            (item.priority, item.kind.value, item.module_id, item.task_id) for item in self.tasks
        )
        if order != tuple(sorted(order)):
            raise ValidationError("verification tasks must be priority ordered")
        if len(self.tasks) > MODULE_IMPACT_MAX_TASKS:
            raise ValidationError("verification task limit exceeded")

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_IMPACT_VERSION,
            "diff_address": self.diff_address,
            "impact_address": self.impact_address,
            "task_count": self.task_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["tasks"] = [item.to_dict() for item in self.tasks]
        return result


@dataclass(frozen=True, slots=True)
class ModuleImpactPolicy:
    """Configurable static gate thresholds with no execution side effects."""

    policy_id: str
    max_critical: int
    max_high: int
    allow_removed_modules: bool
    require_tests_for_direct_changes: bool
    require_clean_inputs: bool
    max_unresolved_direct: int
    min_verification_task_count: int
    content_address: str

    def __post_init__(self) -> None:
        _required_text(self.policy_id, "policy_id")
        _required_text(self.content_address, "content_address")
        for field in (
            "max_critical",
            "max_high",
            "max_unresolved_direct",
            "min_verification_task_count",
        ):
            if getattr(self, field) < 0:
                raise ValidationError(f"{field} cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactGateCheck:
    """One policy-gate finding retained for review when it fails."""

    check_id: str
    plane: ImpactCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            _required_text(getattr(self, field), field)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactGate:
    """Static release decision over diff, impact, and verification evidence."""

    diff_address: str
    impact_address: str
    plan_address: str
    policy: ModuleImpactPolicy
    checks: tuple[ModuleImpactGateCheck, ...]
    state: ImpactGateState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("diff_address", "impact_address", "plan_address", "content_address"):
            _required_text(getattr(self, field), field)
        if not self.checks or len(self.checks) > MODULE_IMPACT_MAX_CHECKS:
            raise ValidationError("impact gate checks are required and bounded")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("impact gate acceptance must conserve check states")
        if (self.state is ImpactGateState.ACCEPTED) != self.accepted:
            raise ValidationError("impact gate state must match acceptance")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_IMPACT_VERSION,
            "diff_address": self.diff_address,
            "impact_address": self.impact_address,
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
class ModuleImpactStage:
    """One timestamp-free runtime stage."""

    stage_id: str
    order: int
    state: ImpactStageState
    input_count: int
    output_count: int
    issue_count: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("stage_id", "detail", "content_address"):
            _required_text(getattr(self, field), field)
        if self.order < 1 or min(self.input_count, self.output_count, self.issue_count) < 0:
            raise ValidationError("impact stage counters are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactRuntime:
    """Reproducible staged execution receipt for impact analysis."""

    runtime_id: str
    version: str
    stages: tuple[ModuleImpactStage, ...]
    left_inventory_address: str
    right_inventory_address: str
    diff_address: str
    impact_address: str
    plan_address: str
    gate_address: str
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "runtime_id",
            "version",
            "left_inventory_address",
            "right_inventory_address",
            "diff_address",
            "impact_address",
            "plan_address",
            "gate_address",
            "content_address",
        ):
            _required_text(getattr(self, field), field)
        if tuple(item.order for item in self.stages) != tuple(range(1, len(self.stages) + 1)):
            raise ValidationError("impact runtime stage order must be contiguous")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactEvent:
    """Stable event row for a timestamp-free impact trace."""

    sequence: int
    event_type: str
    module_id: str
    state: str
    value: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("event_type", "module_id", "state", "detail", "content_address"):
            _required_text(getattr(self, field), field)
        if self.sequence < 1 or self.value < 0:
            raise ValidationError("impact event counters are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactMetric:
    """Aggregate metric that does not contain source payloads."""

    metric_id: str
    category: str
    value: float
    unit: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("metric_id", "category", "unit", "content_address"):
            _required_text(getattr(self, field), field)
        if self.value < 0:
            raise ValidationError("impact metric values cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactObservability:
    """Bounded impact events and aggregate metrics."""

    diff_address: str
    events: tuple[ModuleImpactEvent, ...]
    metrics: tuple[ModuleImpactMetric, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _required_text(self.diff_address, "diff_address")
        _required_text(self.content_address, "content_address")
        if len(self.events) > MODULE_IMPACT_MAX_EVENTS:
            raise ValidationError("impact event limit exceeded")
        if tuple(item.sequence for item in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("impact events must have contiguous sequence numbers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_IMPACT_VERSION,
            "diff_address": self.diff_address,
            "event_count": len(self.events),
            "events": [item.to_dict() for item in self.events],
            "metric_count": len(self.metrics),
            "metrics": [item.to_dict() for item in self.metrics],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleImpactAuditCheck:
    """Independent audit finding for cross-artifact impact closure."""

    check_id: str
    plane: ImpactCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            _required_text(getattr(self, field), field)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactAudit:
    """Cross-artifact audit that never mutates the compared inventories."""

    diff_address: str
    checks: tuple[ModuleImpactAuditCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("diff_address", "content_address"):
            _required_text(getattr(self, field), field)
        if not self.checks or len(self.checks) > MODULE_IMPACT_MAX_CHECKS:
            raise ValidationError("module impact audit checks are required and bounded")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("module impact audit acceptance must conserve checks")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_IMPACT_VERSION,
            "diff_address": self.diff_address,
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


__all__ = [
    "ImpactChangeKind",
    "ImpactCheckPlane",
    "ImpactGateState",
    "ImpactPropagation",
    "ImpactResource",
    "ImpactSeverity",
    "ImpactStageState",
    "ImpactTaskKind",
    "MODULE_IMPACT_BOUNDARY",
    "MODULE_IMPACT_DEFAULT_LIMIT",
    "MODULE_IMPACT_MAX_CHECKS",
    "MODULE_IMPACT_MAX_EVENTS",
    "MODULE_IMPACT_MAX_IMPACTS",
    "MODULE_IMPACT_MAX_LIMIT",
    "MODULE_IMPACT_MAX_MODULES",
    "MODULE_IMPACT_MAX_TASKS",
    "MODULE_IMPACT_VERSION",
    "ModuleDependencyChange",
    "ModuleImpactAssessment",
    "ModuleImpactAudit",
    "ModuleImpactAuditCheck",
    "ModuleImpactChange",
    "ModuleImpactDiff",
    "ModuleImpactEvent",
    "ModuleImpactGate",
    "ModuleImpactGateCheck",
    "ModuleImpactMetric",
    "ModuleImpactObservability",
    "ModuleImpactPolicy",
    "ModuleImpactReport",
    "ModuleImpactRuntime",
    "ModuleImpactStage",
    "ModuleImpactVerificationPlan",
    "ModuleVerificationTask",
]
