"""Staged runtime, replay, and observability for D13 offline bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_design_frontier_bundle_audit import audit_validation_design_offline_bundle
from .validation_design_frontier_bundle_contracts import (
    ValidationDesignBundle,
    ValidationDesignBundleState,
)
from .validation_design_frontier_offline_bundle import build_validation_design_offline_bundle

VALIDATION_DESIGN_BUNDLE_RUNTIME_VERSION = "validation-design-bundle-runtime-v1"


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleRuntimeStage:
    stage_id: str
    ordinal: int
    state: ValidationDesignBundleState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleReplay:
    first_address: str
    second_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleObservability:
    bundle_id: str
    run_id: str
    stage_count: int
    completed: bool
    addressed: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleRuntimeReport:
    run_id: str
    state: ValidationDesignBundleState
    stages: tuple[ValidationDesignBundleRuntimeStage, ...]
    bundle: ValidationDesignBundle
    observability: ValidationDesignBundleObservability
    replay: ValidationDesignBundleReplay
    audit: Any
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VALIDATION_DESIGN_BUNDLE_RUNTIME_VERSION,
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


def _stage(stage_id: str, ordinal: int, state: ValidationDesignBundleState, input_value: Any, output_value: Any, detail: str) -> ValidationDesignBundleRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(input_value, prefix="validation-design-bundle-runtime-input"),
        "output_address": content_hash(output_value, prefix="validation-design-bundle-runtime-output"),
        "detail": detail,
    }
    return ValidationDesignBundleRuntimeStage(**body, content_address=content_hash(body, prefix="validation-design-bundle-runtime-stage"))


def build_validation_design_bundle_observability(bundle: ValidationDesignBundle) -> ValidationDesignBundleObservability:
    """Summarize the normalized runtime trace without embedding artifact bytes."""

    runtime_artifact = next((item for item in bundle.artifacts if item.artifact_id == "runtime"), None)
    payload: dict[str, Any] = {}
    if runtime_artifact is not None and runtime_artifact.payload is not None:
        try:
            parsed = json.loads(runtime_artifact.payload)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    stages = payload.get("stages", ())
    stage_count = len(stages) if isinstance(stages, list) else 0
    completed = bool(stages) and all(isinstance(item, dict) and item.get("state") == "completed" for item in stages)
    addressed = bool(stages) and all(isinstance(item, dict) and str(item.get("output_address", "")).startswith("sha256:") for item in stages)
    body = {
        "bundle_id": bundle.bundle_id,
        "run_id": bundle.run_id,
        "stage_count": stage_count,
        "completed": completed,
        "addressed": addressed,
        "accepted": bundle.accepted and stage_count == 79 and completed and addressed,
    }
    return ValidationDesignBundleObservability(**body, content_address=content_hash(body, prefix="validation-design-bundle-observability"))


def replay_validation_design_offline_bundle(bundle: ValidationDesignBundle) -> ValidationDesignBundleReplay:
    """Replay the normalized bundle assembly using the same source runtime."""

    first = build_validation_design_offline_bundle(runtime=_source_runtime(bundle.run_id), bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    second = build_validation_design_offline_bundle(runtime=_source_runtime(bundle.run_id), bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    deterministic = first.content_address == second.content_address == bundle.content_address
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "deterministic": deterministic,
        "accepted": deterministic,
    }
    return ValidationDesignBundleReplay(**body, content_address=content_hash(body, prefix="validation-design-bundle-replay"))


def _source_runtime(run_id: str) -> Any:
    """Build a fresh source runtime for replay while preserving run identity."""

    from .validation_design_frontier_public_data import default_validation_design_frontier_fixture
    from .validation_design_frontier_runtime import run_validation_design_runtime

    return run_validation_design_runtime(default_validation_design_frontier_fixture(), run_id=run_id)


def run_validation_design_bundle_runtime(
    *,
    bundle_id: str = "validation-design-public-bundle",
    run_id: str = "validation-design-bundle-runtime",
) -> ValidationDesignBundleRuntimeReport:
    """Run bundle assembly, observability, independent audit, and replay."""

    source_runtime = _source_runtime(run_id)
    bundle = build_validation_design_offline_bundle(runtime=source_runtime, bundle_id=bundle_id, run_id=run_id)
    stages: list[ValidationDesignBundleRuntimeStage] = [
        _stage("bundle-materialized", 1, ValidationDesignBundleState.READY if bundle.ready else ValidationDesignBundleState.BLOCKED, {}, bundle.content_address, "public D13 bundle materialized"),
        _stage("artifact-inventory-closed", 2, ValidationDesignBundleState.READY if bundle.artifact_count == 27 else ValidationDesignBundleState.BLOCKED, bundle.content_address, {"artifact_count": bundle.artifact_count}, "27 artifact identities are retained"),
    ]
    audit = audit_validation_design_offline_bundle(bundle)
    stages.append(_stage("cross-artifact-audit", 3, ValidationDesignBundleState.READY if audit.accepted else ValidationDesignBundleState.BLOCKED, bundle.content_address, audit.to_dict(), "independent fixture, evaluation, and release reconciliation completed"))
    observability = build_validation_design_bundle_observability(bundle)
    stages.append(_stage("observability-closed", 4, ValidationDesignBundleState.READY if observability.accepted else ValidationDesignBundleState.BLOCKED, bundle.content_address, observability.to_dict(), "normalized runtime observability is addressed"))
    first = build_validation_design_offline_bundle(runtime=source_runtime, bundle_id=bundle_id, run_id=run_id)
    second = build_validation_design_offline_bundle(runtime=source_runtime, bundle_id=bundle_id, run_id=run_id)
    replay_body = {"first_address": first.content_address, "second_address": second.content_address, "deterministic": first.content_address == second.content_address == bundle.content_address, "accepted": first.content_address == second.content_address == bundle.content_address}
    replay = ValidationDesignBundleReplay(**replay_body, content_address=content_hash(replay_body, prefix="validation-design-bundle-replay"))
    stages.append(_stage("replay-verified", 5, ValidationDesignBundleState.READY if replay.accepted else ValidationDesignBundleState.BLOCKED, bundle.content_address, replay.to_dict(), "normalized bundle address is stable across replay"))
    accepted = bundle.ready and audit.accepted and observability.accepted and replay.accepted
    state = ValidationDesignBundleState.READY if accepted else ValidationDesignBundleState.BLOCKED
    stages.append(_stage("runtime-finalized", 6, state, {"stage_count": len(stages)}, {"state": state.value, "accepted": accepted}, "finalize the offline bundle runtime receipt"))
    body = {"run_id": run_id, "state": state, "stages": tuple(stages), "bundle": bundle, "observability": observability, "replay": replay, "audit": audit, "accepted": accepted}
    return ValidationDesignBundleRuntimeReport(**body, content_address=content_hash(body, prefix="validation-design-bundle-runtime"))


__all__ = [
    "VALIDATION_DESIGN_BUNDLE_RUNTIME_VERSION",
    "ValidationDesignBundleObservability",
    "ValidationDesignBundleReplay",
    "ValidationDesignBundleRuntimeReport",
    "ValidationDesignBundleRuntimeStage",
    "build_validation_design_bundle_observability",
    "replay_validation_design_offline_bundle",
    "run_validation_design_bundle_runtime",
]
