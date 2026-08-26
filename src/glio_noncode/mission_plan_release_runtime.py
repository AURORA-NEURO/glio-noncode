"""Staged runtime orchestration for mission-plan release handoffs.

The runtime is intentionally timestamp-free and side-effect-limited.  It
validates a public receipt, assembles its release, optionally materializes an
exact-byte directory, independently verifies that directory, and records each
stage as an addressed receipt.  It never executes workflow handlers or
reconstructs hidden planner state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import (
    MissionPlanReleaseBundle,
    build_mission_plan_release,
    verify_mission_plan_release,
    write_mission_plan_release,
)
from .mission_runtime_public import MissionPlanPublicReceipt
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_RUNTIME_VERSION = "mission-plan-release-runtime-v1"
MISSION_PLAN_RELEASE_RUNTIME_SCHEMA_VERSION = "mission-plan-release-runtime-schema-v1"
MISSION_PLAN_RELEASE_RUNTIME_CAPABILITIES_VERSION = "mission-plan-release-runtime-capabilities-v1"


class MissionPlanReleaseRuntimeStageState(StrEnum):
    """Stable state for one release-runtime stage."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseRuntimeStage:
    """One deterministic runtime stage receipt."""

    ordinal: int
    stage_id: str
    state: MissionPlanReleaseRuntimeStageState
    input_address: str | None
    output_address: str | None
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if self.ordinal <= 0:
            raise ValidationError("runtime stage ordinal must be positive")
        if not self.stage_id.strip():
            raise ValidationError("runtime stage ID must not be empty")
        if not self.detail.strip():
            raise ValidationError("runtime stage detail must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseRuntime:
    """Addressed staged release runtime result."""

    runtime_version: str
    release_id: str
    plan_id: str
    plan_address: str
    materialized: bool
    verification_address: str | None
    stages: tuple[MissionPlanReleaseRuntimeStage, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.runtime_version != MISSION_PLAN_RELEASE_RUNTIME_VERSION:
            raise ValidationError("mission plan release runtime version is invalid")
        if self.release_id.strip() == "" or self.plan_id.strip() == "" or self.plan_address.strip() == "":
            raise ValidationError("runtime identity fields must not be empty")
        if tuple(stage.ordinal for stage in self.stages) != tuple(range(1, len(self.stages) + 1)):
            raise ValidationError("runtime stages must have contiguous ordinals")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "runtime_version": self.runtime_version,
            "release_id": self.release_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "materialized": self.materialized,
            "verification_address": self.verification_address,
            "stages": self.stages,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _stage(
    ordinal: int,
    stage_id: str,
    state: MissionPlanReleaseRuntimeStageState,
    input_address: str | None,
    output_address: str | None,
    detail: str,
) -> MissionPlanReleaseRuntimeStage:
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return MissionPlanReleaseRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-runtime-stage"),
    )


def run_mission_plan_release_runtime(
    value: MissionPlanPublicReceipt | MissionPlanReleaseBundle | Mapping[str, Any],
    *,
    destination: str | Path | None = None,
    allow_existing: bool = False,
) -> MissionPlanReleaseRuntime:
    """Run deterministic release stages and optionally verify a filesystem handoff."""

    if isinstance(value, MissionPlanReleaseBundle):
        bundle = value
    elif isinstance(value, MissionPlanPublicReceipt):
        bundle = build_mission_plan_release(value)
    else:
        body = dict(value)
        receipt_value = body.get("receipt", body)
        if not isinstance(receipt_value, Mapping):
            raise ValidationError("runtime input must contain a public mission receipt")
        bundle = build_mission_plan_release(receipt_value)
    stages: list[MissionPlanReleaseRuntimeStage] = []
    stages.append(
        _stage(
            1,
            "receipt-validation",
            MissionPlanReleaseRuntimeStageState.COMPLETED,
            bundle.plan_address,
            bundle.plan_address,
            "Public receipt validated and rehydrated.",
        )
    )
    stages.append(
        _stage(
            2,
            "release-assembly",
            MissionPlanReleaseRuntimeStageState.COMPLETED,
            bundle.plan_address,
            bundle.content_address,
            "Exact-byte release artifacts and integrity checks assembled.",
        )
    )
    verification_address: str | None = None
    materialized = destination is not None
    if destination is None:
        stages.append(
            _stage(
                3,
                "filesystem-materialization",
                MissionPlanReleaseRuntimeStageState.SKIPPED,
                bundle.content_address,
                None,
                "No destination supplied; filesystem write was not requested.",
            )
        )
        stages.append(
            _stage(
                4,
                "filesystem-verification",
                MissionPlanReleaseRuntimeStageState.SKIPPED,
                bundle.content_address,
                None,
                "No materialized directory exists to verify.",
            )
        )
        filesystem_accepted = True
    else:
        write_mission_plan_release(bundle, destination, allow_existing=allow_existing)
        manifest_address = str(bundle.manifest["manifest_address"])
        stages.append(
            _stage(
                3,
                "filesystem-materialization",
                MissionPlanReleaseRuntimeStageState.COMPLETED,
                bundle.content_address,
                manifest_address,
                "Release artifacts written as exact UTF-8 bytes.",
            )
        )
        verification = verify_mission_plan_release(destination)
        verification_address = verification.content_address
        filesystem_accepted = verification.accepted
        stages.append(
            _stage(
                4,
                "filesystem-verification",
                MissionPlanReleaseRuntimeStageState.COMPLETED
                if verification.accepted
                else MissionPlanReleaseRuntimeStageState.FAILED,
                manifest_address,
                verification.content_address,
                "Independent release-directory verification completed.",
            )
        )
    boundary_address = content_hash(
        {"checks": [item.to_dict() for item in bundle.checks]},
        prefix="mission-plan-release-runtime-boundary",
    )
    boundary_accepted = not any(
        key in bundle.manifest for key in ("agent", "language", "model", "author")
    )
    stages.append(
        _stage(
            5,
            "public-boundary",
            MissionPlanReleaseRuntimeStageState.COMPLETED
            if boundary_accepted
            else MissionPlanReleaseRuntimeStageState.FAILED,
            bundle.content_address,
            boundary_address,
            "Release projections passed the public boundary check.",
        )
    )
    accepted = bool(bundle.accepted and filesystem_accepted and boundary_accepted)
    stages.append(
        _stage(
            6,
            "finalize",
            MissionPlanReleaseRuntimeStageState.COMPLETED
            if accepted
            else MissionPlanReleaseRuntimeStageState.FAILED,
            stages[-1].content_address,
            None,
            "Release runtime finalized with its aggregate acceptance state.",
        )
    )
    body = {
        "runtime_version": MISSION_PLAN_RELEASE_RUNTIME_VERSION,
        "release_id": bundle.release_id,
        "plan_id": bundle.plan_id,
        "plan_address": bundle.plan_address,
        "materialized": materialized,
        "verification_address": verification_address,
        "stages": stages,
        "accepted": accepted,
    }
    return MissionPlanReleaseRuntime(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-runtime"),
    )


def mission_plan_release_runtime_json(runtime: MissionPlanReleaseRuntime) -> str:
    """Render the runtime receipt as canonical JSON."""

    return canonical_json(runtime.to_dict()) + "\n"


def mission_plan_release_runtime_schema() -> dict[str, Any]:
    """Return the staged-runtime contract."""

    return {
        "version": MISSION_PLAN_RELEASE_RUNTIME_SCHEMA_VERSION,
        "runtime_version": MISSION_PLAN_RELEASE_RUNTIME_VERSION,
        "stage_states": [item.value for item in MissionPlanReleaseRuntimeStageState],
        "stages": [
            "receipt-validation",
            "release-assembly",
            "filesystem-materialization",
            "filesystem-verification",
            "public-boundary",
            "finalize",
        ],
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_runtime_capabilities() -> dict[str, Any]:
    """Return staged-runtime capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_RUNTIME_CAPABILITIES_VERSION,
        "receipt_validation": True,
        "release_assembly": True,
        "optional_filesystem_materialization": True,
        "independent_filesystem_verification": True,
        "public_boundary_stage": True,
        "timestamp_free_replay": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "read_only_without_destination": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_RUNTIME_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_RUNTIME_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_RUNTIME_VERSION",
    "MissionPlanReleaseRuntime",
    "MissionPlanReleaseRuntimeStage",
    "MissionPlanReleaseRuntimeStageState",
    "mission_plan_release_runtime_capabilities",
    "mission_plan_release_runtime_json",
    "mission_plan_release_runtime_schema",
    "run_mission_plan_release_runtime",
]
