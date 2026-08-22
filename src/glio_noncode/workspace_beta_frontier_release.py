"""Release manifest for the C05-C08 projection frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_bundle import BetaFrontierReleaseBundle
from .workspace_beta_frontier_quality_gate import BetaFrontierQualityGate
from .workspace_beta_frontier_replay import BetaFrontierReplayReceipt
from .workspace_beta_frontier_runtime import BetaFrontierRuntimeReport


class BetaFrontierReleaseState(StrEnum):
    READY = "ready"
    HELD = "held"


@dataclass(frozen=True, slots=True)
class BetaFrontierReleaseCheck:
    """One manifest check and its release impact."""

    check_id: str
    passed: bool
    blocking: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierReleaseManifest:
    """Versioned release manifest with explicit hold reasons."""

    release_id: str
    version: str
    state: BetaFrontierReleaseState
    fixture_id: str
    bundle_address: str
    runtime_address: str
    replay_address: str
    checks: tuple[BetaFrontierReleaseCheck, ...]
    hold_reasons: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.release_id, "release_id")
        require_non_empty(self.version, "version")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(check_id: str, passed: bool, blocking: bool, observed: Any, required: Any, detail: str) -> BetaFrontierReleaseCheck:
    body = {"check_id": check_id, "passed": passed, "blocking": blocking, "observed": observed, "required": required, "detail": detail}
    return BetaFrontierReleaseCheck(**body, content_address=content_hash(body))


def build_beta_frontier_release_manifest(
    bundle: BetaFrontierReleaseBundle,
    quality: BetaFrontierQualityGate,
    replay: BetaFrontierReplayReceipt,
    runtime: BetaFrontierRuntimeReport,
    *,
    release_id: str = "workspace-beta-frontier-release",
) -> BetaFrontierReleaseManifest:
    checks = (
        _check("release:bundle", bundle.accepted, True, bundle.accepted, True, "bundle is accepted"),
        _check("release:quality", quality.accepted, True, quality.accepted, True, "quality gate has no blocking failures"),
        _check("release:replay", replay.deterministic, True, replay.deterministic, True, "replay is deterministic"),
        _check("release:runtime", runtime.accepted, True, runtime.accepted, True, "runtime rehearsal is accepted"),
        _check("release:boundary", bundle.public_boundary == "public_aggregate_non_patient", True, bundle.public_boundary, "public_aggregate_non_patient", "release boundary is public aggregate"),
        _check("release:stage-count", len(runtime.stages) == 8, False, len(runtime.stages), 8, "eight runtime stages are present"),
        _check("release:address", all(item.content_address.startswith("sha256:") for item in quality.checks), False, True, True, "quality checks are addressed"),
    )
    hold_reasons = tuple(item.check_id for item in checks if item.blocking and not item.passed)
    state = BetaFrontierReleaseState.READY if not hold_reasons else BetaFrontierReleaseState.HELD
    body = {"release_id": release_id, "version": "2026.08.d15.c05-c08.v1", "state": state, "fixture_id": bundle.fixture_id, "bundle_address": bundle.content_address, "runtime_address": runtime.content_address, "replay_address": replay.content_address, "checks": checks, "hold_reasons": hold_reasons}
    return BetaFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierReleaseCheck", "BetaFrontierReleaseManifest", "BetaFrontierReleaseState", "build_beta_frontier_release_manifest"]
