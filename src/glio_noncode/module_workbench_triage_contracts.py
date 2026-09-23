"""Typed contracts for deterministic module implementation triage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_TRIAGE_VERSION = "module-workbench-triage-v1"
MODULE_WORKBENCH_TRIAGE_BOUNDARY = "public_aggregate_module_workbench_triage"
MODULE_WORKBENCH_TRIAGE_MAX_ITEMS = 20_000
MODULE_WORKBENCH_TRIAGE_MAX_REASONS = 16
MODULE_WORKBENCH_TRIAGE_MAX_TASK_IDS = 8


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


def _ordered_unique(
    values: tuple[str, ...], field: str, maximum: int, value_maximum: int = 256
) -> None:
    if len(values) > maximum or len(values) != len(set(values)):
        raise ValidationError(f"{field} must be bounded and unique")
    for value in values:
        _text(value, f"{field}[]", value_maximum)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchTriageItem:
    """One explainable module priority row."""

    rank: int
    module_id: str
    family: str
    role: str
    risk: str
    depth_band: str
    score: float
    priority_score: float
    fan_in: int
    fan_out: int
    gap_count: int
    evidence_count: int
    unresolved_edge_count: int
    task_count: int
    reasons: tuple[str, ...]
    recommended_task_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        _count(self.rank, "rank")
        if self.rank < 1:
            raise ValidationError("rank must be positive")
        for field in ("module_id", "family", "role", "risk", "depth_band", "content_address"):
            _text(getattr(self, field), field)
        _score(self.score, "score")
        _score(self.priority_score, "priority_score")
        for field in (
            "fan_in",
            "fan_out",
            "gap_count",
            "evidence_count",
            "unresolved_edge_count",
            "task_count",
        ):
            _count(getattr(self, field), field)
        _ordered_unique(self.reasons, "reasons", MODULE_WORKBENCH_TRIAGE_MAX_REASONS)
        _ordered_unique(
            self.recommended_task_ids,
            "recommended_task_ids",
            MODULE_WORKBENCH_TRIAGE_MAX_TASK_IDS,
            4096,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchTriageReport:
    """Complete, deterministically ranked module review queue."""

    workbench_address: str
    matrix_address: str
    lineage_address: str
    quality_address: str
    items: tuple[ModuleWorkbenchTriageItem, ...]
    reason_counts: Mapping[str, int]
    risk_counts: Mapping[str, int]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "workbench_address",
            "matrix_address",
            "lineage_address",
            "quality_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if len(self.items) > MODULE_WORKBENCH_TRIAGE_MAX_ITEMS:
            raise ValidationError("triage item limit exceeded")
        ranks = tuple(item.rank for item in self.items)
        if ranks != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("triage items must have contiguous ranks")
        for field, values in (("reason_counts", self.reason_counts), ("risk_counts", self.risk_counts)):
            if tuple(sorted(values)) != tuple(values):
                raise ValidationError(f"{field} keys must be sorted")
            for key, value in values.items():
                _text(key, f"{field}.key", 256)
                _count(value, f"{field}.{key}")
        if not isinstance(self.accepted, bool):
            raise ValidationError("triage accepted must be boolean")

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_TRIAGE_VERSION,
            "boundary": MODULE_WORKBENCH_TRIAGE_BOUNDARY,
            "workbench_address": self.workbench_address,
            "matrix_address": self.matrix_address,
            "lineage_address": self.lineage_address,
            "quality_address": self.quality_address,
            "item_count": len(self.items),
            "reason_counts": dict(sorted(self.reason_counts.items())),
            "risk_counts": dict(sorted(self.risk_counts.items())),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_module_workbench_triage_item(value: ModuleWorkbenchTriageItem) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-triage-item")


def address_module_workbench_triage(value: ModuleWorkbenchTriageReport) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-triage")


__all__ = [
    "MODULE_WORKBENCH_TRIAGE_BOUNDARY",
    "MODULE_WORKBENCH_TRIAGE_MAX_ITEMS",
    "MODULE_WORKBENCH_TRIAGE_MAX_REASONS",
    "MODULE_WORKBENCH_TRIAGE_MAX_TASK_IDS",
    "MODULE_WORKBENCH_TRIAGE_VERSION",
    "ModuleWorkbenchTriageItem",
    "ModuleWorkbenchTriageReport",
    "address_module_workbench_triage",
    "address_module_workbench_triage_item",
]
