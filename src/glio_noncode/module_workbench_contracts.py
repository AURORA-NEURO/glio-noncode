"""Typed contracts for module-by-module implementation depth planning.

The workbench turns static inventory, certification, and evidence into a
deterministic engineering queue.  It describes what is present, what is
missing, how a module connects to the rest of the package, and which bounded
next actions would increase durable coverage.  It stores only relative paths,
counts, digests, and stable identifiers so the report is safe to publish.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_VERSION = "module-workbench-v1"
MODULE_WORKBENCH_BOUNDARY = "public_aggregate_module_workbench"
MODULE_WORKBENCH_MAX_MODULES = 20_000
MODULE_WORKBENCH_MAX_TASKS = 200_000
MODULE_WORKBENCH_MAX_DIMENSIONS = 32
MODULE_WORKBENCH_MAX_LIMIT = 512
MODULE_WORKBENCH_DEFAULT_LIMIT = 50


class ModuleWorkbenchDepthBand(StrEnum):
    """Coarse implementation-depth band derived from multiple signals."""

    BLOCKED = "blocked"
    STARTER = "starter"
    ESTABLISHED = "established"
    DEEP = "deep"
    COMPREHENSIVE = "comprehensive"


class ModuleWorkbenchRisk(StrEnum):
    """Delivery risk inferred from static blockers and weak coverage."""

    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ModuleWorkbenchTaskKind(StrEnum):
    """Action classes emitted by the module depth planner."""

    REPAIR_PARSE = "repair_parse"
    RESOLVE_DEPENDENCY = "resolve_dependency"
    ADD_TEST = "add_test"
    ADD_DOCUMENTATION = "add_documentation"
    EXPAND_PUBLIC_CONTRACT = "expand_public_contract"
    DECOMPOSE_OVERSIZED = "decompose_oversized"
    REVIEW_INTEGRATION = "review_integration"
    CLOSE_CERTIFICATION = "close_certification"


def _text(value: Any, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


def _score(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")
    return float(value)


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


def _mapping_scores(values: Mapping[str, float], field: str) -> None:
    if not values or len(values) > MODULE_WORKBENCH_MAX_DIMENSIONS:
        raise ValidationError(f"{field} must contain a bounded dimension set")
    if tuple(sorted(values)) != tuple(values):
        raise ValidationError(f"{field} keys must be sorted")
    for key, value in values.items():
        _text(key, f"{field}.{key}", 128)
        _score(value, f"{field}.{key}")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchDimension:
    """One explainable module-depth dimension with observed and target values."""

    name: str
    score: float
    observed: int
    target: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.name, "name", 128)
        _score(self.score, "score")
        _count(self.observed, "observed")
        _count(self.target, "target")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchAssessment:
    """Conserved static assessment for one source module."""

    module_id: str
    family: str
    role: str
    state: str
    physical_lines: int
    nonblank_lines: int
    public_symbol_count: int
    function_count: int
    class_count: int
    import_count: int
    local_dependency_count: int
    fan_in: int
    fan_out: int
    test_reference_count: int
    evidence_count: int
    evidence_kinds: tuple[str, ...]
    dimensions: tuple[ModuleWorkbenchDimension, ...]
    score: float
    depth_band: ModuleWorkbenchDepthBand
    risk: ModuleWorkbenchRisk
    blockers: tuple[str, ...]
    strengths: tuple[str, ...]
    source_address: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("module_id", "family", "role", "state", "source_address", "content_address"):
            _text(getattr(self, field), field)
        for field in (
            "physical_lines",
            "nonblank_lines",
            "public_symbol_count",
            "function_count",
            "class_count",
            "import_count",
            "local_dependency_count",
            "fan_in",
            "fan_out",
            "test_reference_count",
            "evidence_count",
        ):
            _count(getattr(self, field), field)
        _sorted_unique(self.evidence_kinds, "evidence_kinds")
        _sorted_unique(self.blockers, "blockers")
        _sorted_unique(self.strengths, "strengths")
        if tuple(item.name for item in self.dimensions) != tuple(
            sorted(item.name for item in self.dimensions)
        ):
            raise ValidationError("module workbench dimensions must be sorted")
        _score(self.score, "score")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchTask:
    """One deterministic, bounded action for increasing module depth."""

    task_id: str
    module_id: str
    kind: ModuleWorkbenchTaskKind
    priority: int
    title: str
    rationale: str
    acceptance: str
    estimated_impact: float
    evidence: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "task_id",
            "module_id",
            "title",
            "rationale",
            "acceptance",
            "content_address",
        ):
            _text(getattr(self, field), field, 4096)
        if (
            not isinstance(self.priority, int)
            or isinstance(self.priority, bool)
            or not 0 <= self.priority <= 100
        ):
            raise ValidationError("task priority must be between zero and one hundred")
        _score(self.estimated_impact, "estimated_impact")
        _sorted_unique(self.evidence, "evidence")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchFamilyRollup:
    """Family-level conservation and concentration metrics."""

    family: str
    module_count: int
    deep_count: int
    comprehensive_count: int
    blocked_count: int
    high_risk_count: int
    average_score: float
    average_test_references: float
    average_evidence: float
    average_fan_out: float
    top_task_kinds: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        _text(self.family, "family")
        for field in (
            "module_count",
            "deep_count",
            "comprehensive_count",
            "blocked_count",
            "high_risk_count",
        ):
            _count(getattr(self, field), field)
        if self.module_count < self.deep_count + self.comprehensive_count + self.blocked_count:
            raise ValidationError("family depth counts exceed module count")
        for field in (
            "average_score",
            "average_test_references",
            "average_evidence",
            "average_fan_out",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValidationError(f"{field} must be non-negative")
        _sorted_unique(self.top_task_kinds, "top_task_kinds")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReport:
    """Whole-project module workbench with depth, risk, and action queue."""

    inventory_address: str
    matrix_address: str
    lineage_address: str
    quality_address: str
    assessments: tuple[ModuleWorkbenchAssessment, ...]
    tasks: tuple[ModuleWorkbenchTask, ...]
    families: tuple[ModuleWorkbenchFamilyRollup, ...]
    overall_score: float
    overall_percent: float
    depth_percent: float
    deep_count: int
    comprehensive_count: int
    starter_count: int
    blocked_count: int
    high_risk_count: int
    risk_counts: Mapping[str, int]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "inventory_address",
            "matrix_address",
            "lineage_address",
            "quality_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if len(self.assessments) > MODULE_WORKBENCH_MAX_MODULES:
            raise ValidationError("module workbench module limit exceeded")
        if len(self.tasks) > MODULE_WORKBENCH_MAX_TASKS:
            raise ValidationError("module workbench task limit exceeded")
        if tuple(item.module_id for item in self.assessments) != tuple(
            sorted(item.module_id for item in self.assessments)
        ):
            raise ValidationError("module workbench assessments must be sorted")
        if tuple(item.task_id for item in self.tasks) != tuple(
            sorted(item.task_id for item in self.tasks)
        ):
            raise ValidationError("module workbench tasks must be sorted")
        if tuple(item.family for item in self.families) != tuple(
            sorted(item.family for item in self.families)
        ):
            raise ValidationError("module workbench families must be sorted")
        for field in ("overall_score",):
            _score(getattr(self, field), field)
        if isinstance(self.overall_percent, bool) or not 0.0 <= self.overall_percent <= 100.0:
            raise ValidationError("overall_percent must be between zero and one hundred")
        if isinstance(self.depth_percent, bool) or not 0.0 <= self.depth_percent <= 100.0:
            raise ValidationError("depth_percent must be between zero and one hundred")
        for field in (
            "deep_count",
            "comprehensive_count",
            "starter_count",
            "blocked_count",
            "high_risk_count",
        ):
            _count(getattr(self, field), field)
        if (
            self.deep_count + self.comprehensive_count + self.starter_count + self.blocked_count
            > len(self.assessments)
        ):
            raise ValidationError("workbench depth counts exceed module count")
        if tuple(sorted(self.risk_counts)) != tuple(self.risk_counts):
            raise ValidationError("risk counts must be sorted")
        if any(
            _count(value, f"risk_counts.{key}") is None for key, value in self.risk_counts.items()
        ):
            raise AssertionError("unreachable")

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_VERSION,
            "boundary": MODULE_WORKBENCH_BOUNDARY,
            "inventory_address": self.inventory_address,
            "matrix_address": self.matrix_address,
            "lineage_address": self.lineage_address,
            "quality_address": self.quality_address,
            "module_count": len(self.assessments),
            "task_count": len(self.tasks),
            "family_count": len(self.families),
            "overall_score": self.overall_score,
            "overall_percent": self.overall_percent,
            "depth_percent": self.depth_percent,
            "deep_count": self.deep_count,
            "comprehensive_count": self.comprehensive_count,
            "starter_count": self.starter_count,
            "blocked_count": self.blocked_count,
            "high_risk_count": self.high_risk_count,
            "risk_counts": dict(sorted(self.risk_counts.items())),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            body["assessments"] = [item.to_dict() for item in self.assessments]
            body["tasks"] = [item.to_dict() for item in self.tasks]
            body["families"] = [item.to_dict() for item in self.families]
        return body


def address_module_workbench_dimension(value: ModuleWorkbenchDimension) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-dimension")


def address_module_workbench_assessment(value: ModuleWorkbenchAssessment) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-assessment")


def address_module_workbench_task(value: ModuleWorkbenchTask) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-task")


def address_module_workbench_family(value: ModuleWorkbenchFamilyRollup) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-family")


__all__ = [
    "MODULE_WORKBENCH_BOUNDARY",
    "MODULE_WORKBENCH_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_MAX_LIMIT",
    "MODULE_WORKBENCH_MAX_MODULES",
    "MODULE_WORKBENCH_MAX_TASKS",
    "MODULE_WORKBENCH_VERSION",
    "ModuleWorkbenchAssessment",
    "ModuleWorkbenchDepthBand",
    "ModuleWorkbenchDimension",
    "ModuleWorkbenchFamilyRollup",
    "ModuleWorkbenchReport",
    "ModuleWorkbenchRisk",
    "ModuleWorkbenchTask",
    "ModuleWorkbenchTaskKind",
    "address_module_workbench_assessment",
    "address_module_workbench_dimension",
    "address_module_workbench_family",
    "address_module_workbench_task",
]
