"""Staged runtime, observability, and deterministic replay for D15 bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workbench_release_frontier_offline_audit import audit_workbench_release_offline_bundle
from .workbench_release_frontier_offline_bundle import build_workbench_release_offline_bundle
from .workbench_release_frontier_offline_contracts import (
    WorkbenchReleaseOfflineBundle,
    WorkbenchReleaseOfflineBundleState,
)

WORKBENCH_RELEASE_OFFLINE_RUNTIME_VERSION = "workbench-release-offline-runtime-v1"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineRuntimeStage:
    stage_id: str
    ordinal: int
    state: WorkbenchReleaseOfflineBundleState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineObservability:
    bundle_id: str
    run_id: str
    artifact_count: int
    stage_count: int
    component_count: int
    completed: bool
    addressed: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineRuntimeReport:
    run_id: str
    state: WorkbenchReleaseOfflineBundleState
    stages: tuple[WorkbenchReleaseOfflineRuntimeStage, ...]
    bundle: WorkbenchReleaseOfflineBundle
    observability: WorkbenchReleaseOfflineObservability
    replay: WorkbenchReleaseOfflineReplay
    audit: Any
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKBENCH_RELEASE_OFFLINE_RUNTIME_VERSION,
            "run_id": self.run_id,
            "state": self.state,
            "stages": [item.to_dict() for item in self.stages],
            "bundle": self.bundle.to_dict(include_payloads=False),
            "observability": self.observability.to_dict(),
            "replay": self.replay.to_dict(),
            "audit": self.audit.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str,
    ordinal: int,
    state: WorkbenchReleaseOfflineBundleState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> WorkbenchReleaseOfflineRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(
            input_value, prefix="workbench-release-offline-runtime-input"
        ),
        "output_address": content_hash(
            output_value, prefix="workbench-release-offline-runtime-output"
        ),
        "detail": detail,
    }
    return WorkbenchReleaseOfflineRuntimeStage(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-runtime-stage")
    )


def _runtime_payload(bundle: WorkbenchReleaseOfflineBundle) -> dict[str, Any]:
    runtime = next(item for item in bundle.artifacts if item.artifact_id == "runtime")
    if runtime.payload is None:
        return {}
    try:
        value = json.loads(runtime.payload)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def build_workbench_release_offline_observability(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineObservability:
    """Summarize the normalized 49-stage trace without duplicating payload bytes."""

    runtime = _runtime_payload(bundle)
    stages = runtime.get("stages", ())
    stage_count = len(stages) if isinstance(stages, list) else 0
    completed = bool(stages) and all(
        isinstance(item, dict) and item.get("state") == "completed" for item in stages
    )
    addressed = bool(stages) and all(
        isinstance(item, dict) and str(item.get("output_address", "")).startswith("sha256:")
        for item in stages
    )
    component_count = sum(
        item.kind.value not in {"fixture", "runtime", "review_csv"} for item in bundle.artifacts
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "run_id": bundle.run_id,
        "artifact_count": bundle.artifact_count,
        "stage_count": stage_count,
        "component_count": component_count,
        "completed": completed,
        "addressed": addressed,
        "accepted": bundle.accepted
        and bundle.artifact_count == 56
        and stage_count == 49
        and completed
        and addressed,
    }
    return WorkbenchReleaseOfflineObservability(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-observability")
    )


def replay_workbench_release_offline_bundle(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineReplay:
    """Rebuild two normalized handoffs and compare exact root addresses."""

    first = build_workbench_release_offline_bundle(bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    second = build_workbench_release_offline_bundle(
        bundle_id=bundle.bundle_id, run_id=bundle.run_id
    )
    deterministic = first.content_address == second.content_address == bundle.content_address
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "expected_address": bundle.content_address,
        "deterministic": deterministic,
        "accepted": deterministic,
    }
    return WorkbenchReleaseOfflineReplay(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-replay")
    )


def run_workbench_release_offline_bundle_runtime(
    *,
    bundle_id: str = "workbench-release-public-bundle",
    run_id: str = "workbench-release-offline-runtime",
) -> WorkbenchReleaseOfflineRuntimeReport:
    """Run materialization, cross-artifact audit, observability, and replay."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    bundle = build_workbench_release_offline_bundle(bundle_id=bundle_id, run_id=run_id)
    ready = (
        WorkbenchReleaseOfflineBundleState.READY
        if bundle.ready
        else WorkbenchReleaseOfflineBundleState.BLOCKED
    )
    stages: list[WorkbenchReleaseOfflineRuntimeStage] = [
        _stage(
            "bundle-materialized",
            1,
            ready,
            {},
            bundle.content_address,
            "public D15 bundle materialized",
        ),
        _stage(
            "artifact-inventory-closed",
            2,
            ready if bundle.artifact_count == 56 else WorkbenchReleaseOfflineBundleState.BLOCKED,
            bundle.content_address,
            {"artifact_count": bundle.artifact_count},
            "fifty-six artifact identities are retained",
        ),
    ]
    audit = audit_workbench_release_offline_bundle(bundle)
    audit_state = (
        WorkbenchReleaseOfflineBundleState.READY
        if audit.accepted
        else WorkbenchReleaseOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "cross-artifact-audit",
            3,
            audit_state,
            bundle.content_address,
            audit.to_dict(),
            "fixture, evaluation, runtime, and index joins are reconciled",
        )
    )
    observability = build_workbench_release_offline_observability(bundle)
    obs_state = (
        WorkbenchReleaseOfflineBundleState.READY
        if observability.accepted
        else WorkbenchReleaseOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "observability-closed",
            4,
            obs_state,
            bundle.content_address,
            observability.to_dict(),
            "normalized 49-stage trace is addressed",
        )
    )
    replay = replay_workbench_release_offline_bundle(bundle)
    replay_state = (
        WorkbenchReleaseOfflineBundleState.READY
        if replay.accepted
        else WorkbenchReleaseOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "replay-verified",
            5,
            replay_state,
            bundle.content_address,
            replay.to_dict(),
            "normalized D15 root address is stable across replay",
        )
    )
    accepted = bundle.ready and audit.accepted and observability.accepted and replay.accepted
    state = (
        WorkbenchReleaseOfflineBundleState.READY
        if accepted
        else WorkbenchReleaseOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "runtime-finalized",
            6,
            state,
            {"stage_count": len(stages)},
            {"state": state.value, "accepted": accepted},
            "finalize the offline workbench receipt",
        )
    )
    body = {
        "run_id": run_id,
        "state": state,
        "stages": tuple(stages),
        "bundle": bundle,
        "observability": observability,
        "replay": replay,
        "audit": audit,
        "accepted": accepted,
    }
    return WorkbenchReleaseOfflineRuntimeReport(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-runtime")
    )


__all__ = [
    "WORKBENCH_RELEASE_OFFLINE_RUNTIME_VERSION",
    "WorkbenchReleaseOfflineObservability",
    "WorkbenchReleaseOfflineReplay",
    "WorkbenchReleaseOfflineRuntimeReport",
    "WorkbenchReleaseOfflineRuntimeStage",
    "build_workbench_release_offline_observability",
    "replay_workbench_release_offline_bundle",
    "run_workbench_release_offline_bundle_runtime",
]
