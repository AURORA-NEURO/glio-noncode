"""Staged runtime, observability, and replay for D14 offline bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .evidence_lifecycle_frontier_offline_audit import audit_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_bundle import build_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle, EvidenceLifecycleOfflineBundleState

EVIDENCE_LIFECYCLE_OFFLINE_RUNTIME_VERSION = "evidence-lifecycle-offline-runtime-v1"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineRuntimeStage:
    stage_id: str
    ordinal: int
    state: EvidenceLifecycleOfflineBundleState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineObservability:
    bundle_id: str
    run_id: str
    artifact_count: int
    stage_count: int
    completed: bool
    addressed: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineRuntimeReport:
    run_id: str
    state: EvidenceLifecycleOfflineBundleState
    stages: tuple[EvidenceLifecycleOfflineRuntimeStage, ...]
    bundle: EvidenceLifecycleOfflineBundle
    observability: EvidenceLifecycleOfflineObservability
    replay: EvidenceLifecycleOfflineReplay
    audit: Any
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": EVIDENCE_LIFECYCLE_OFFLINE_RUNTIME_VERSION,
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


def _stage(stage_id: str, ordinal: int, state: EvidenceLifecycleOfflineBundleState, input_value: Any, output_value: Any, detail: str) -> EvidenceLifecycleOfflineRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(input_value, prefix="evidence-lifecycle-offline-runtime-input"),
        "output_address": content_hash(output_value, prefix="evidence-lifecycle-offline-runtime-output"),
        "detail": detail,
    }
    return EvidenceLifecycleOfflineRuntimeStage(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-runtime-stage"))


def build_evidence_lifecycle_offline_observability(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineObservability:
    """Summarize the normalized runtime artifact without embedding its bytes."""

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
        "artifact_count": bundle.artifact_count,
        "stage_count": stage_count,
        "completed": completed,
        "addressed": addressed,
        "accepted": bundle.accepted and bundle.artifact_count == 21 and stage_count == 10 and completed and addressed,
    }
    return EvidenceLifecycleOfflineObservability(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-observability"))


def replay_evidence_lifecycle_offline_bundle(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineReplay:
    """Rebuild two normalized handoffs and compare exact root addresses."""

    first = build_evidence_lifecycle_offline_bundle(bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    second = build_evidence_lifecycle_offline_bundle(bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    deterministic = first.content_address == second.content_address == bundle.content_address
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "expected_address": bundle.content_address,
        "deterministic": deterministic,
        "accepted": deterministic,
    }
    return EvidenceLifecycleOfflineReplay(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-replay"))


def run_evidence_lifecycle_offline_bundle_runtime(
    *,
    bundle_id: str = "evidence-lifecycle-public-bundle",
    run_id: str = "evidence-lifecycle-offline-runtime",
) -> EvidenceLifecycleOfflineRuntimeReport:
    """Run materialization, closure audit, observability, and deterministic replay."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    bundle = build_evidence_lifecycle_offline_bundle(bundle_id=bundle_id, run_id=run_id)
    ready = EvidenceLifecycleOfflineBundleState.READY if bundle.ready else EvidenceLifecycleOfflineBundleState.BLOCKED
    stages: list[EvidenceLifecycleOfflineRuntimeStage] = [
        _stage("bundle-materialized", 1, ready, {}, bundle.content_address, "public D14 bundle materialized"),
        _stage("artifact-inventory-closed", 2, ready if bundle.artifact_count == 21 else EvidenceLifecycleOfflineBundleState.BLOCKED, bundle.content_address, {"artifact_count": bundle.artifact_count}, "twenty-one artifact identities are retained"),
    ]
    audit = audit_evidence_lifecycle_offline_bundle(bundle)
    audit_state = EvidenceLifecycleOfflineBundleState.READY if audit.accepted else EvidenceLifecycleOfflineBundleState.BLOCKED
    stages.append(_stage("cross-artifact-audit", 3, audit_state, bundle.content_address, audit.to_dict(), "independent fixture, evaluation, and release reconciliation completed"))
    observability = build_evidence_lifecycle_offline_observability(bundle)
    obs_state = EvidenceLifecycleOfflineBundleState.READY if observability.accepted else EvidenceLifecycleOfflineBundleState.BLOCKED
    stages.append(_stage("observability-closed", 4, obs_state, bundle.content_address, observability.to_dict(), "normalized runtime observability is addressed"))
    replay = replay_evidence_lifecycle_offline_bundle(bundle)
    replay_state = EvidenceLifecycleOfflineBundleState.READY if replay.accepted else EvidenceLifecycleOfflineBundleState.BLOCKED
    stages.append(_stage("replay-verified", 5, replay_state, bundle.content_address, replay.to_dict(), "normalized bundle address is stable across replay"))
    accepted = bundle.ready and audit.accepted and observability.accepted and replay.accepted
    state = EvidenceLifecycleOfflineBundleState.READY if accepted else EvidenceLifecycleOfflineBundleState.BLOCKED
    stages.append(_stage("runtime-finalized", 6, state, {"stage_count": len(stages)}, {"state": state.value, "accepted": accepted}, "finalize the offline bundle runtime receipt"))
    body = {"run_id": run_id, "state": state, "stages": tuple(stages), "bundle": bundle, "observability": observability, "replay": replay, "audit": audit, "accepted": accepted}
    return EvidenceLifecycleOfflineRuntimeReport(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-runtime"))


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_RUNTIME_VERSION",
    "EvidenceLifecycleOfflineObservability",
    "EvidenceLifecycleOfflineReplay",
    "EvidenceLifecycleOfflineRuntimeReport",
    "EvidenceLifecycleOfflineRuntimeStage",
    "build_evidence_lifecycle_offline_observability",
    "replay_evidence_lifecycle_offline_bundle",
    "run_evidence_lifecycle_offline_bundle_runtime",
]
