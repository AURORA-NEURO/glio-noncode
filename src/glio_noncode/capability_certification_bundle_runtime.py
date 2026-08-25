"""Staged runtime and deterministic replay for certification bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_certification_bundle import build_capability_certification_bundle
from .capability_certification_bundle_contracts import (
    CapabilityCertificationBundle,
    CertificationBundleState,
)
from .capability_certification_bundle_observability import (
    build_capability_certification_bundle_observability,
)
from .capability_registry import CapabilityRegistry
from .serialization import content_hash, jsonable

CAPABILITY_CERTIFICATION_BUNDLE_RUNTIME_VERSION = "capability-certification-bundle-runtime-v1"


@dataclass(frozen=True, slots=True)
class CertificationBundleRuntimeStage:
    stage_id: str
    ordinal: int
    state: CertificationBundleState
    input_address: str
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CapabilityCertificationBundleRuntimeReport:
    run_id: str
    state: CertificationBundleState
    stages: tuple[CertificationBundleRuntimeStage, ...]
    bundle: CapabilityCertificationBundle
    observability: Any
    replay_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CAPABILITY_CERTIFICATION_BUNDLE_RUNTIME_VERSION,
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
    state: CertificationBundleState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> CertificationBundleRuntimeStage:
    return CertificationBundleRuntimeStage(
        stage_id=stage_id,
        ordinal=ordinal,
        state=state,
        input_address=input_value if isinstance(input_value, str) else content_hash(input_value, prefix="capability-certification-bundle-runtime-input"),
        output_address=output_value if isinstance(output_value, str) else content_hash(output_value, prefix="capability-certification-bundle-runtime-output"),
        detail=detail,
    )


def replay_capability_certification_bundle(
    registry: CapabilityRegistry | None = None,
    *,
    bundle_id: str = "capability-certification-public-bundle",
    run_id: str | None = None,
) -> CapabilityCertificationBundle:
    """Build the same public bundle twice and require address stability."""

    first = build_capability_certification_bundle(registry, bundle_id=bundle_id, run_id=run_id)
    second = build_capability_certification_bundle(registry, bundle_id=bundle_id, run_id=run_id)
    if first.content_address != second.content_address:
        raise ValueError("capability certification bundle replay produced a different address")
    return second


def run_capability_certification_bundle_runtime(
    registry: CapabilityRegistry | None = None,
    *,
    bundle_id: str = "capability-certification-public-bundle",
    run_id: str | None = None,
) -> CapabilityCertificationBundleRuntimeReport:
    """Run the bundle lifecycle and retain each addressed transition."""

    bundle = build_capability_certification_bundle(registry, bundle_id=bundle_id, run_id=run_id)
    ready = CertificationBundleState.READY if bundle.ready else CertificationBundleState.BLOCKED
    stages = [
        _stage(
            "runtime-materialized",
            1,
            ready,
            {},
            bundle.runtime_address,
            "live certification runtime receipt materialized",
        ),
        _stage(
            "artifact-inventory-assembled",
            2,
            CertificationBundleState.READY if bundle.artifact_count else CertificationBundleState.BLOCKED,
            bundle.runtime_address,
            {"artifact_count": bundle.artifact_count},
            "public certification artifact inventory assembled",
        ),
        _stage(
            "manifest-checks-closed",
            3,
            CertificationBundleState.READY if bundle.failed_check_count == 0 else CertificationBundleState.BLOCKED,
            bundle.to_dict(include_payloads=False),
            {"failed_check_count": bundle.failed_check_count},
            "bundle checks evaluated",
        ),
    ]
    observability = build_capability_certification_bundle_observability(
        bundle.bundle_id,
        # The report is intentionally reconstructed from the runtime artifact
        # by the builder; this stage only addresses the already-built receipt.
        _runtime_from_bundle(bundle, registry),
        artifact_count=bundle.artifact_count,
        artifact_bytes=sum(item.byte_count for item in bundle.artifacts),
    )
    stages.append(
        _stage(
            "observability-closed",
            4,
            CertificationBundleState.READY if observability.accepted else CertificationBundleState.BLOCKED,
            bundle.content_address,
            observability.to_dict(),
            "events and metrics are addressed",
        )
    )
    replay = replay_capability_certification_bundle(registry, bundle_id=bundle_id, run_id=run_id)
    replay_ok = replay.content_address == bundle.content_address
    stages.append(
        _stage(
            "replay-verified",
            5,
            CertificationBundleState.READY if replay_ok else CertificationBundleState.BLOCKED,
            bundle.content_address,
            replay.content_address,
            "bundle address is stable across deterministic replay",
        )
    )
    accepted = bundle.ready and observability.accepted and replay_ok
    state = CertificationBundleState.READY if accepted else CertificationBundleState.BLOCKED
    stages.append(
        _stage(
            "runtime-finalized",
            6,
            state,
            {"stage_count": len(stages)},
            {"state": state.value, "accepted": accepted},
            "finalize the addressed certification bundle runtime",
        )
    )
    body = {
        "run_id": run_id or bundle.run_id,
        "state": state,
        "stages": stages,
        "bundle": bundle,
        "observability": observability,
        "replay_address": replay.content_address,
        "accepted": accepted,
    }
    return CapabilityCertificationBundleRuntimeReport(
        run_id=run_id or bundle.run_id,
        state=state,
        stages=tuple(stages),
        bundle=bundle,
        observability=observability,
        replay_address=replay.content_address,
        accepted=accepted,
        content_address=content_hash(body, prefix="capability-certification-bundle-runtime"),
    )


def _runtime_from_bundle(bundle: CapabilityCertificationBundle, registry: CapabilityRegistry | None) -> Any:
    """Recover the runtime view required by observability without filesystem I/O."""

    from .capability_certification_runtime import run_capability_certification

    return run_capability_certification(run_id=bundle.run_id, registry=registry)


__all__ = [
    "CAPABILITY_CERTIFICATION_BUNDLE_RUNTIME_VERSION",
    "CapabilityCertificationBundleRuntimeReport",
    "CertificationBundleRuntimeStage",
    "replay_capability_certification_bundle",
    "run_capability_certification_bundle_runtime",
]
