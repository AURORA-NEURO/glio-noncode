"""Staged materialization, observability, and deterministic replay for D16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_audit import audit_deployment_frontier_offline_bundle
from .deployment_frontier_offline_boundary import audit_deployment_frontier_offline_boundary
from .deployment_frontier_offline_bundle import build_deployment_frontier_offline_bundle
from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_RUNTIME_VERSION,
    DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
    DeploymentFrontierOfflineBundle,
    DeploymentFrontierOfflineBundleState,
)
from .deployment_frontier_offline_indexes import (
    audit_deployment_frontier_offline_indexes,
    build_deployment_frontier_offline_indexes,
)
from .deployment_frontier_offline_reconciliation import reconcile_deployment_frontier_offline_bundle
from .deployment_frontier_offline_summary import (
    audit_deployment_frontier_offline_summary,
    build_deployment_frontier_offline_summary,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineRuntimeStage:
    stage_id: str
    ordinal: int
    state: DeploymentFrontierOfflineBundleState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineObservability:
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
class DeploymentFrontierOfflineRuntimeReport:
    run_id: str
    state: DeploymentFrontierOfflineBundleState
    stages: tuple[DeploymentFrontierOfflineRuntimeStage, ...]
    bundle: DeploymentFrontierOfflineBundle
    observability: DeploymentFrontierOfflineObservability
    replay: DeploymentFrontierOfflineReplay
    audit: Any
    boundary: Any
    indexes: Any
    index_audit: Any
    reconciliation: Any
    summary: Any
    summary_audit: Any
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DEPLOYMENT_FRONTIER_OFFLINE_RUNTIME_VERSION,
            "run_id": self.run_id,
            "state": self.state,
            "stages": [item.to_dict() for item in self.stages],
            "bundle": self.bundle.to_dict(include_payloads=False),
            "observability": self.observability.to_dict(),
            "replay": self.replay.to_dict(),
            "audit": self.audit.to_dict(),
            "boundary": self.boundary.to_dict(),
            "indexes": self.indexes.to_dict(),
            "index_audit": self.index_audit.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "summary": self.summary.to_dict(),
            "summary_audit": self.summary_audit.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str,
    ordinal: int,
    state: DeploymentFrontierOfflineBundleState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> DeploymentFrontierOfflineRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(
            input_value, prefix="deployment-frontier-offline-runtime-input"
        ),
        "output_address": content_hash(
            output_value, prefix="deployment-frontier-offline-runtime-output"
        ),
        "detail": detail,
    }
    return DeploymentFrontierOfflineRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-runtime-stage"),
    )


def _runtime_payload(bundle: DeploymentFrontierOfflineBundle) -> dict[str, Any]:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == "runtime"), None)
    if artifact is None or artifact.payload is None:
        return {}
    try:
        value = json.loads(artifact.payload)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def build_deployment_frontier_offline_observability(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineObservability:
    """Summarize the normalized D16 trace without duplicating payload bytes."""

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
        item.artifact_id
        not in {"fixture", "runtime", "review-csv", "sources-csv", "executions-csv"}
        for item in bundle.artifacts
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
        and bundle.artifact_count == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT
        and stage_count == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT
        and completed
        and addressed,
    }
    return DeploymentFrontierOfflineObservability(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-observability"),
    )


def replay_deployment_frontier_offline_bundle(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineReplay:
    """Build two normalized handoffs and compare exact root addresses."""

    first = build_deployment_frontier_offline_bundle(
        bundle_id=bundle.bundle_id, run_id=bundle.run_id
    )
    second = build_deployment_frontier_offline_bundle(
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
    return DeploymentFrontierOfflineReplay(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-replay")
    )


def run_deployment_frontier_offline_runtime(
    *,
    bundle_id: str = "deployment-frontier-public-bundle",
    run_id: str = "deployment-frontier-offline-runtime",
) -> DeploymentFrontierOfflineRuntimeReport:
    """Run materialization, audits, indexes, reconciliation, summary, and replay."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    bundle = build_deployment_frontier_offline_bundle(bundle_id=bundle_id, run_id=run_id)
    ready = (
        DeploymentFrontierOfflineBundleState.READY
        if bundle.ready
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages: list[DeploymentFrontierOfflineRuntimeStage] = []
    stages.append(
        _stage(
            "bundle-materialized",
            1,
            ready,
            {},
            bundle.content_address,
            "D16 public offline bundle materialized",
        )
    )
    stages.append(
        _stage(
            "artifact-inventory-closed",
            2,
            ready if bundle.artifact_count == 51 else DeploymentFrontierOfflineBundleState.BLOCKED,
            bundle.content_address,
            {"artifact_count": bundle.artifact_count},
            "fifty-one exact-byte artifact identities are retained",
        )
    )
    audit = audit_deployment_frontier_offline_bundle(bundle)
    audit_state = (
        DeploymentFrontierOfflineBundleState.READY
        if audit.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "cross-artifact-audit",
            3,
            audit_state,
            bundle.content_address,
            audit.to_dict(),
            "fixture, evaluation, runtime, and release joins are reconciled",
        )
    )
    boundary = audit_deployment_frontier_offline_boundary(bundle)
    boundary_state = (
        DeploymentFrontierOfflineBundleState.READY
        if boundary.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "public-boundary-closed",
            4,
            boundary_state,
            bundle.content_address,
            boundary.to_dict(),
            "recursive public key and path boundaries are closed",
        )
    )
    indexes = build_deployment_frontier_offline_indexes(bundle)
    index_audit = audit_deployment_frontier_offline_indexes(bundle, indexes)
    index_state = (
        DeploymentFrontierOfflineBundleState.READY
        if index_audit.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "address-indexes-closed",
            5,
            index_state,
            bundle.content_address,
            index_audit.to_dict(),
            "address-only artifact, record, stage, issue, and state indexes are closed",
        )
    )
    reconciliation = reconcile_deployment_frontier_offline_bundle(bundle)
    reconciliation_state = (
        DeploymentFrontierOfflineBundleState.READY
        if reconciliation.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "denominator-reconciled",
            6,
            reconciliation_state,
            bundle.content_address,
            reconciliation.to_dict(),
            "D16 denominators and identity joins reconcile",
        )
    )
    summary = build_deployment_frontier_offline_summary(bundle)
    summary_audit = audit_deployment_frontier_offline_summary(summary)
    summary_state = (
        DeploymentFrontierOfflineBundleState.READY
        if summary_audit.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "review-summary-closed",
            7,
            summary_state,
            bundle.content_address,
            summary_audit.to_dict(),
            "operation summaries and reviewer counters close",
        )
    )
    observability = build_deployment_frontier_offline_observability(bundle)
    observability_state = (
        DeploymentFrontierOfflineBundleState.READY
        if observability.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "observability-closed",
            8,
            observability_state,
            bundle.content_address,
            observability.to_dict(),
            "normalized 38-stage trace is addressable",
        )
    )
    replay = replay_deployment_frontier_offline_bundle(bundle)
    replay_state = (
        DeploymentFrontierOfflineBundleState.READY
        if replay.accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "replay-verified",
            9,
            replay_state,
            bundle.content_address,
            replay.to_dict(),
            "normalized D16 root address is stable across replay",
        )
    )
    accepted = (
        bundle.ready
        and audit.accepted
        and boundary.accepted
        and index_audit.accepted
        and reconciliation.accepted
        and summary_audit.accepted
        and observability.accepted
        and replay.accepted
    )
    state = (
        DeploymentFrontierOfflineBundleState.READY
        if accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    stages.append(
        _stage(
            "runtime-finalized",
            10,
            state,
            {"stage_count": len(stages)},
            {"state": state.value, "accepted": accepted},
            "finalize the D16 offline receipt",
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
        "boundary": boundary,
        "indexes": indexes,
        "index_audit": index_audit,
        "reconciliation": reconciliation,
        "summary": summary,
        "summary_audit": summary_audit,
        "accepted": accepted,
    }
    return DeploymentFrontierOfflineRuntimeReport(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-runtime")
    )


__all__ = [
    "DEPLOYMENT_FRONTIER_OFFLINE_RUNTIME_VERSION",
    "DeploymentFrontierOfflineObservability",
    "DeploymentFrontierOfflineReplay",
    "DeploymentFrontierOfflineRuntimeReport",
    "DeploymentFrontierOfflineRuntimeStage",
    "build_deployment_frontier_offline_observability",
    "replay_deployment_frontier_offline_bundle",
    "run_deployment_frontier_offline_runtime",
]
