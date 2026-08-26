"""Typed contracts for selecting a bounded module-workbench task portfolio."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchTask
from .serialization import content_hash

MODULE_WORKBENCH_PORTFOLIO_VERSION = "module-workbench-portfolio-v1"
MODULE_WORKBENCH_PORTFOLIO_BOUNDARY = "public_aggregate_module_workbench_portfolio"
MODULE_WORKBENCH_PORTFOLIO_MAX_TASKS = 200_000


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _score(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchPortfolio:
    """Bounded selected task set for a module implementation wave."""

    report_address: str
    capacity: int
    max_tasks_per_module: int
    selected_tasks: tuple[ModuleWorkbenchTask, ...]
    deferred_task_count: int
    selected_module_count: int
    selected_family_counts: Mapping[str, int]
    total_estimated_impact: float
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.report_address, "report_address")
        _count(self.capacity, "capacity")
        _count(self.max_tasks_per_module, "max_tasks_per_module")
        if self.capacity < 1:
            raise ValidationError("portfolio capacity must be positive")
        if self.max_tasks_per_module < 1:
            raise ValidationError("portfolio per-module capacity must be positive")
        if len(self.selected_tasks) > self.capacity:
            raise ValidationError("portfolio exceeds capacity")
        if len(self.selected_tasks) > MODULE_WORKBENCH_PORTFOLIO_MAX_TASKS:
            raise ValidationError("portfolio task limit exceeded")
        task_ids = tuple(item.task_id for item in self.selected_tasks)
        if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValidationError("portfolio tasks must be sorted and unique")
        _count(self.deferred_task_count, "deferred_task_count")
        _count(self.selected_module_count, "selected_module_count")
        if self.selected_module_count > len(self.selected_tasks):
            raise ValidationError("portfolio selected module count exceeds task count")
        if tuple(sorted(self.selected_family_counts)) != tuple(self.selected_family_counts):
            raise ValidationError("portfolio family counts must be sorted")
        for key, value in self.selected_family_counts.items():
            _text(key, f"selected_family_counts.{key}", 256)
            _count(value, f"selected_family_counts.{key}")
        _score(self.total_estimated_impact, "total_estimated_impact")
        if not isinstance(self.accepted, bool):
            raise ValidationError("portfolio accepted must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self, *, include_tasks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_PORTFOLIO_VERSION,
            "boundary": MODULE_WORKBENCH_PORTFOLIO_BOUNDARY,
            "report_address": self.report_address,
            "capacity": self.capacity,
            "max_tasks_per_module": self.max_tasks_per_module,
            "task_count": len(self.selected_tasks),
            "deferred_task_count": self.deferred_task_count,
            "selected_module_count": self.selected_module_count,
            "selected_family_counts": dict(sorted(self.selected_family_counts.items())),
            "total_estimated_impact": self.total_estimated_impact,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_tasks:
            body["selected_tasks"] = [item.to_dict() for item in self.selected_tasks]
        return body


def address_module_workbench_portfolio(value: ModuleWorkbenchPortfolio) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-portfolio")


__all__ = [
    "MODULE_WORKBENCH_PORTFOLIO_BOUNDARY",
    "MODULE_WORKBENCH_PORTFOLIO_MAX_TASKS",
    "MODULE_WORKBENCH_PORTFOLIO_VERSION",
    "ModuleWorkbenchPortfolio",
    "address_module_workbench_portfolio",
]
