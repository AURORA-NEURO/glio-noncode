"""Typed contracts for dependency-aware module execution planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_PLAN_VERSION = "module-workbench-execution-plan-v1"
MODULE_WORKBENCH_EXECUTION_PLAN_BOUNDARY = "public_aggregate_module_workbench_execution_plan"
MODULE_WORKBENCH_EXECUTION_PLAN_MAX_NODES = 200_000


class ModuleWorkbenchExecutionPlanDependencyStatus(StrEnum):
    """Dependency state for one selected task."""

    ROOT = "root"
    SELECTED_PREREQUISITE = "selected_prerequisite"
    DEFERRED_PREREQUISITE = "deferred_prerequisite"
    UNKNOWN_PREREQUISITE = "unknown_prerequisite"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


def _ordered_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if len(values) != len(set(values)):
        raise ValidationError(f"{field} must be unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPlanNode:
    """One selected task with full-plan dependency and execution context."""

    task_id: str
    module_id: str
    family: str
    kind: str
    priority: int
    sequence: int
    depth: int
    prerequisite_task_ids: tuple[str, ...]
    selected_prerequisite_task_ids: tuple[str, ...]
    deferred_prerequisite_task_ids: tuple[str, ...]
    execution_state: str
    dependency_status: ModuleWorkbenchExecutionPlanDependencyStatus
    downstream_count: int
    content_address: str

    def __post_init__(self) -> None:
        for field in ("task_id", "module_id", "family", "kind", "execution_state", "content_address"):
            _text(getattr(self, field), field)
        for field in ("priority", "sequence", "depth", "downstream_count"):
            _count(getattr(self, field), field)
        if self.priority > 100:
            raise ValidationError("priority exceeds one hundred")
        for field in (
            "prerequisite_task_ids",
            "selected_prerequisite_task_ids",
            "deferred_prerequisite_task_ids",
        ):
            _sorted_unique(getattr(self, field), field)
        prerequisites = set(self.prerequisite_task_ids)
        selected = set(self.selected_prerequisite_task_ids)
        deferred = set(self.deferred_prerequisite_task_ids)
        if not selected <= prerequisites or not deferred <= prerequisites:
            raise ValidationError("plan prerequisite projections must be subsets")
        if selected & deferred or selected | deferred != prerequisites:
            raise ValidationError("plan prerequisite projections must partition prerequisites")
        if not isinstance(self.dependency_status, ModuleWorkbenchExecutionPlanDependencyStatus):
            raise ValidationError("dependency_status must be a supported plan status")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_plan_node(
    value: ModuleWorkbenchExecutionPlanNode,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-plan-node")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPlan:
    """Dependency-aware projection joining the full plan, wave, and ledger."""

    report_address: str
    portfolio_address: str
    ledger_address: str
    nodes: tuple[ModuleWorkbenchExecutionPlanNode, ...]
    dependency_edge_count: int
    root_count: int
    selected_prerequisite_count: int
    deferred_prerequisite_count: int
    unknown_prerequisite_count: int
    max_depth: int
    critical_path_task_ids: tuple[str, ...]
    dependency_safe: bool
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("report_address", "portfolio_address", "ledger_address", "content_address"):
            _text(getattr(self, field), field)
        if len(self.nodes) > MODULE_WORKBENCH_EXECUTION_PLAN_MAX_NODES:
            raise ValidationError("execution plan node limit exceeded")
        task_ids = tuple(item.task_id for item in self.nodes)
        if len(task_ids) != len(set(task_ids)):
            raise ValidationError("execution plan nodes must be unique")
        sequences = tuple(item.sequence for item in self.nodes)
        if tuple((item.sequence, item.task_id) for item in self.nodes) != tuple(
            sorted((item.sequence, item.task_id) for item in self.nodes)
        ) or sequences != tuple(range(1, len(sequences) + 1)):
            raise ValidationError("execution plan sequences must be contiguous")
        for field in (
            "dependency_edge_count",
            "root_count",
            "selected_prerequisite_count",
            "deferred_prerequisite_count",
            "unknown_prerequisite_count",
            "max_depth",
        ):
            _count(getattr(self, field), field)
        _ordered_unique(self.critical_path_task_ids, "critical_path_task_ids")
        node_ids = set(task_ids)
        if not set(self.critical_path_task_ids) <= node_ids:
            raise ValidationError("critical path contains an unknown selected task")
        if self.selected_prerequisite_count + self.deferred_prerequisite_count + self.unknown_prerequisite_count != self.dependency_edge_count:
            raise ValidationError("execution plan dependency counts do not conserve edges")
        if self.root_count > len(self.nodes):
            raise ValidationError("execution plan root count exceeds nodes")
        if not isinstance(self.dependency_safe, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("execution plan acceptance fields must be boolean")

    def to_dict(self, *, include_nodes: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PLAN_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PLAN_BOUNDARY,
            "report_address": self.report_address,
            "portfolio_address": self.portfolio_address,
            "ledger_address": self.ledger_address,
            "node_count": len(self.nodes),
            "dependency_edge_count": self.dependency_edge_count,
            "root_count": self.root_count,
            "selected_prerequisite_count": self.selected_prerequisite_count,
            "deferred_prerequisite_count": self.deferred_prerequisite_count,
            "unknown_prerequisite_count": self.unknown_prerequisite_count,
            "max_depth": self.max_depth,
            "critical_path_task_ids": list(self.critical_path_task_ids),
            "dependency_safe": self.dependency_safe,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_nodes:
            body["nodes"] = [item.to_dict() for item in self.nodes]
        return body


def address_module_workbench_execution_plan(value: ModuleWorkbenchExecutionPlan) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-plan")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PLAN_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PLAN_MAX_NODES",
    "MODULE_WORKBENCH_EXECUTION_PLAN_VERSION",
    "ModuleWorkbenchExecutionPlan",
    "ModuleWorkbenchExecutionPlanDependencyStatus",
    "ModuleWorkbenchExecutionPlanNode",
    "address_module_workbench_execution_plan",
    "address_module_workbench_execution_plan_node",
]
