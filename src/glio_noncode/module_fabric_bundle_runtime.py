"""Staged runtime and deterministic replay for the fabric bundle boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_registry import CapabilityRegistry
from .module_fabric_bundle import build_module_fabric_bundle
from .module_fabric_bundle_contracts import FabricBundle, FabricBundleState
from .module_fabric_bundle_observability import build_module_fabric_bundle_observability
from .module_fabric_contracts import FabricFixture
from .serialization import content_hash, jsonable

MODULE_FABRIC_BUNDLE_RUNTIME_VERSION = "module-fabric-bundle-runtime-v1"


@dataclass(frozen=True, slots=True)
class FabricBundleRuntimeStage:
    stage_id: str
    ordinal: int
    state: FabricBundleState
    input_address: str
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricBundleRuntimeReport:
    run_id: str
    state: FabricBundleState
    stages: tuple[FabricBundleRuntimeStage, ...]
    bundle: FabricBundle
    observability: Any
    replay_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_FABRIC_BUNDLE_RUNTIME_VERSION,
            "run_id": self.run_id,
            "state": self.state.value,
            "stages": [item.to_dict() for item in self.stages],
            "bundle": self.bundle.to_dict(include_payloads=False),
            "observability": self.observability.to_dict(),
            "replay_address": self.replay_address,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str,
    ordinal: int,
    state: FabricBundleState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> FabricBundleRuntimeStage:
    return FabricBundleRuntimeStage(
        stage_id=stage_id,
        ordinal=ordinal,
        state=state,
        input_address=content_hash(input_value, prefix="module-fabric-bundle-runtime-input"),
        output_address=content_hash(output_value, prefix="module-fabric-bundle-runtime-output"),
        detail=detail,
    )


def replay_module_fabric_bundle(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
    *,
    bundle_id: str = "module-fabric-public-bundle",
    run_id: str = "module-fabric-bundle-runtime",
) -> FabricBundle:
    """Build the same bundle twice and return the second deterministic result."""

    first = build_module_fabric_bundle(fixture, registry, bundle_id=bundle_id, run_id=run_id)
    second = build_module_fabric_bundle(fixture, registry, bundle_id=bundle_id, run_id=run_id)
    if first.content_address != second.content_address:
        raise ValueError("module-fabric bundle replay produced a different address")
    return second


def run_module_fabric_bundle_runtime(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
    *,
    bundle_id: str = "module-fabric-public-bundle",
    run_id: str = "module-fabric-bundle-runtime",
) -> FabricBundleRuntimeReport:
    """Run the staged in-memory bundle pipeline and retain each transition."""

    bundle = build_module_fabric_bundle(fixture, registry, bundle_id=bundle_id, run_id=run_id)
    stages = [
        _stage("runtime-materialized", 1, FabricBundleState.READY if bundle.ready else FabricBundleState.BLOCKED, {}, {"runtime_address": bundle.runtime_address}, "module-fabric runtime receipt materialized"),
        _stage("artifact-inventory-assembled", 2, FabricBundleState.READY if bundle.artifact_count else FabricBundleState.BLOCKED, bundle.runtime_address, {"artifact_count": bundle.artifact_count}, "public artifact inventory assembled"),
        _stage("manifest-checks-closed", 3, FabricBundleState.READY if bundle.failed_check_count == 0 else FabricBundleState.BLOCKED, bundle.to_dict(include_payloads=False), {"failed_check_count": bundle.failed_check_count}, "bundle checks evaluated"),
    ]
    observability = build_module_fabric_bundle_observability(bundle)
    stages.append(
        _stage(
            "observability-closed",
            4,
            FabricBundleState.READY if observability.accepted else FabricBundleState.BLOCKED,
            bundle.content_address,
            observability.to_dict(),
            "events and metrics are addressed",
        )
    )
    replay = replay_module_fabric_bundle(fixture, registry, bundle_id=bundle_id, run_id=run_id)
    replay_ok = replay.content_address == bundle.content_address
    stages.append(
        _stage(
            "replay-verified",
            5,
            FabricBundleState.READY if replay_ok else FabricBundleState.BLOCKED,
            bundle.content_address,
            replay.content_address,
            "bundle address is stable across deterministic replay",
        )
    )
    accepted = bundle.ready and observability.accepted and replay_ok
    state = FabricBundleState.READY if accepted else FabricBundleState.BLOCKED
    stages.append(
        _stage(
            "runtime-finalized",
            6,
            state,
            {"stage_count": len(stages)},
            {"state": state.value, "accepted": accepted},
            "finalize the bundle runtime receipt",
        )
    )
    body = {
        "run_id": run_id,
        "state": state,
        "stages": stages,
        "bundle": bundle,
        "observability": observability,
        "replay_address": replay.content_address,
        "accepted": accepted,
    }
    return FabricBundleRuntimeReport(
        run_id=run_id,
        state=state,
        stages=tuple(stages),
        bundle=bundle,
        observability=observability,
        replay_address=replay.content_address,
        accepted=accepted,
        content_address=content_hash(body, prefix="module-fabric-bundle-runtime"),
    )


__all__ = [
    "MODULE_FABRIC_BUNDLE_RUNTIME_VERSION",
    "FabricBundleRuntimeReport",
    "FabricBundleRuntimeStage",
    "replay_module_fabric_bundle",
    "run_module_fabric_bundle_runtime",
]
