"""Typed runtime contracts for the module execution handoff."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_RUNTIME_VERSION = "module-workbench-execution-runtime-v1"
MODULE_WORKBENCH_EXECUTION_RUNTIME_BOUNDARY = "public_aggregate_module_workbench_execution_runtime"
MODULE_WORKBENCH_EXECUTION_RUNTIME_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_RUNTIME_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_RUNTIME_MAX_STAGES = 8


class ModuleWorkbenchExecutionRuntimeStageKind(StrEnum):
    """Ordered execution handoff stages."""

    PORTFOLIO = "portfolio"
    PLAN = "plan"
    REPLAY = "replay"
    POLICY = "policy"
    AUDIT = "audit"
    HANDOFF = "handoff"


class ModuleWorkbenchExecutionRuntimeStageState(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionRuntimeStage:
    """One addressed runtime stage."""

    kind: ModuleWorkbenchExecutionRuntimeStageKind
    state: ModuleWorkbenchExecutionRuntimeStageState
    accepted: bool
    artifact_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ModuleWorkbenchExecutionRuntimeStageKind):
            raise ValidationError("kind must be a supported runtime stage")
        if not isinstance(self.state, ModuleWorkbenchExecutionRuntimeStageState):
            raise ValidationError("state must be a supported runtime stage state")
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")
        _text(self.artifact_address, "artifact_address")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_runtime_stage(
    value: ModuleWorkbenchExecutionRuntimeStage,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-runtime-stage")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionRuntime:
    """Complete deterministic execution handoff with retained artifact addresses."""

    report_address: str
    portfolio_address: str
    initial_ledger_address: str
    ledger_address: str
    policy_address: str
    gate_address: str
    audit_address: str
    stages: tuple[ModuleWorkbenchExecutionRuntimeStage, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "report_address",
            "portfolio_address",
            "initial_ledger_address",
            "ledger_address",
            "policy_address",
            "gate_address",
            "audit_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if len(self.stages) != len(ModuleWorkbenchExecutionRuntimeStageKind):
            raise ValidationError("runtime stage count is incomplete")
        kinds = tuple(item.kind for item in self.stages)
        if kinds != tuple(ModuleWorkbenchExecutionRuntimeStageKind):
            raise ValidationError("runtime stages must follow the declared order")
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")

    @property
    def completed_count(self) -> int:
        return sum(
            item.state is ModuleWorkbenchExecutionRuntimeStageState.COMPLETED
            for item in self.stages
        )

    @property
    def blocked_count(self) -> int:
        return sum(
            item.state is ModuleWorkbenchExecutionRuntimeStageState.BLOCKED for item in self.stages
        )

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_RUNTIME_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_RUNTIME_BOUNDARY,
            "report_address": self.report_address,
            "portfolio_address": self.portfolio_address,
            "initial_ledger_address": self.initial_ledger_address,
            "ledger_address": self.ledger_address,
            "policy_address": self.policy_address,
            "gate_address": self.gate_address,
            "audit_address": self.audit_address,
            "stage_count": len(self.stages),
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_runtime(
    value: ModuleWorkbenchExecutionRuntime,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-runtime")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_RUNTIME_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_RUNTIME_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_RUNTIME_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_RUNTIME_MAX_STAGES",
    "MODULE_WORKBENCH_EXECUTION_RUNTIME_VERSION",
    "ModuleWorkbenchExecutionRuntime",
    "ModuleWorkbenchExecutionRuntimeStage",
    "ModuleWorkbenchExecutionRuntimeStageKind",
    "ModuleWorkbenchExecutionRuntimeStageState",
    "address_module_workbench_execution_runtime",
    "address_module_workbench_execution_runtime_stage",
]
