"""Typed runtime contracts for one complete module workbench evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RUNTIME_VERSION = "module-workbench-runtime-v1"
MODULE_WORKBENCH_RUNTIME_BOUNDARY = "public_aggregate_module_workbench_runtime"
MODULE_WORKBENCH_RUNTIME_MAX_STAGES = 16
MODULE_WORKBENCH_RUNTIME_MAX_LIMIT = 512
MODULE_WORKBENCH_RUNTIME_DEFAULT_LIMIT = 50


class ModuleWorkbenchStageState(StrEnum):
    """State vocabulary for timestamp-free runtime stages."""

    COMPLETED = "completed"
    BLOCKED = "blocked"


class ModuleWorkbenchStageKind(StrEnum):
    """Ordered static evaluation stages."""

    INVENTORY = "inventory"
    CERTIFICATION = "certification"
    LINEAGE = "lineage"
    QUALITY = "quality"
    WORKBENCH = "workbench"
    POLICY = "policy"
    AUDIT = "audit"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchStage:
    """One ordered stage outcome with an address to its typed artifact."""

    kind: ModuleWorkbenchStageKind
    state: ModuleWorkbenchStageState
    accepted: bool
    artifact_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise ValidationError("runtime stage accepted must be boolean")
        for field in ("artifact_address", "detail", "content_address"):
            _text(getattr(self, field), field)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchRuntime:
    """Complete, timestamp-free static workbench run result."""

    inventory_address: str
    certification_address: str
    lineage_address: str
    quality_address: str
    workbench_address: str
    policy_address: str
    gate_address: str
    audit_address: str
    stages: tuple[ModuleWorkbenchStage, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "inventory_address",
            "certification_address",
            "lineage_address",
            "quality_address",
            "workbench_address",
            "policy_address",
            "gate_address",
            "audit_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if not self.stages or len(self.stages) > MODULE_WORKBENCH_RUNTIME_MAX_STAGES:
            raise ValidationError("runtime requires a bounded nonempty stage set")
        kinds = tuple(item.kind for item in self.stages)
        if kinds != tuple(ModuleWorkbenchStageKind):
            raise ValidationError("runtime stages must follow the evaluation order")
        if len(set(kinds)) != len(kinds):
            raise ValidationError("runtime stages must be unique")
        if self.accepted != all(item.accepted for item in self.stages):
            raise ValidationError("runtime acceptance does not conserve stages")

    @property
    def completed_count(self) -> int:
        return sum(item.state is ModuleWorkbenchStageState.COMPLETED for item in self.stages)

    @property
    def blocked_count(self) -> int:
        return sum(item.state is ModuleWorkbenchStageState.BLOCKED for item in self.stages)

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_RUNTIME_VERSION,
            "boundary": MODULE_WORKBENCH_RUNTIME_BOUNDARY,
            "inventory_address": self.inventory_address,
            "certification_address": self.certification_address,
            "lineage_address": self.lineage_address,
            "quality_address": self.quality_address,
            "workbench_address": self.workbench_address,
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


def address_module_workbench_stage(value: ModuleWorkbenchStage) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-stage")


__all__ = [
    "MODULE_WORKBENCH_RUNTIME_BOUNDARY",
    "MODULE_WORKBENCH_RUNTIME_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RUNTIME_MAX_LIMIT",
    "MODULE_WORKBENCH_RUNTIME_MAX_STAGES",
    "MODULE_WORKBENCH_RUNTIME_VERSION",
    "ModuleWorkbenchRuntime",
    "ModuleWorkbenchStage",
    "ModuleWorkbenchStageKind",
    "ModuleWorkbenchStageState",
    "address_module_workbench_stage",
]
