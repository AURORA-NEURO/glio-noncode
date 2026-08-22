"""Release manifest for research-workspace frontier artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_bundle import WorkspaceFrontierReleaseBundle
from .workspace_frontier_quality_gate import WorkspaceFrontierQualityGate
from .workspace_frontier_replay import WorkspaceFrontierReplayReceipt
from .workspace_frontier_runtime import WorkspaceFrontierRuntimeReport


class WorkspaceFrontierReleaseState(StrEnum):
    READY = "ready"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReleaseCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    state: WorkspaceFrontierReleaseState
    accepted: bool
    public_boundary: str
    artifact_addresses: tuple[str, ...]
    checks: tuple[WorkspaceFrontierReleaseCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(check_id: str, passed: bool, detail: str) -> WorkspaceFrontierReleaseCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return WorkspaceFrontierReleaseCheck(**body, content_address=content_hash(body))


def build_workspace_frontier_release_manifest(bundle: WorkspaceFrontierReleaseBundle, quality: WorkspaceFrontierQualityGate, replay: WorkspaceFrontierReplayReceipt, runtime: WorkspaceFrontierRuntimeReport | None = None) -> WorkspaceFrontierReleaseManifest:
    runtime = runtime or run_runtime_for_release(bundle)
    checks = (
        _check("bundle-accepted", bundle.accepted, "bundle inputs accepted"),
        _check("quality-accepted", quality.accepted, "quality gate accepted"),
        _check("replay-stable", replay.stable, "replay receipt is stable"),
        _check("runtime-accepted", runtime.accepted, "runtime stages accepted"),
        _check("public-boundary", bundle.public_boundary == "public_aggregate_non_patient", "public aggregate boundary retained"),
        _check("addresses-present", all(bool(address) for address in bundle.to_dict().values() if isinstance(address, str)), "bundle addresses are present"),
    )
    accepted = all(item.passed for item in checks)
    body = {"release_id": f"workspace-release:{bundle.fixture_id}", "fixture_id": bundle.fixture_id, "state": WorkspaceFrontierReleaseState.READY if accepted else WorkspaceFrontierReleaseState.HOLD, "accepted": accepted, "public_boundary": bundle.public_boundary, "artifact_addresses": (bundle.content_address, quality.content_address, replay.content_address, runtime.content_address), "checks": checks}
    return WorkspaceFrontierReleaseManifest(**body, content_address=content_hash(body))


def run_runtime_for_release(bundle: WorkspaceFrontierReleaseBundle) -> WorkspaceFrontierRuntimeReport:
    from .workspace_frontier_runtime import run_workspace_frontier_runtime

    return run_workspace_frontier_runtime(run_id=f"release:{bundle.fixture_id}")


__all__ = ["WorkspaceFrontierReleaseCheck", "WorkspaceFrontierReleaseManifest", "WorkspaceFrontierReleaseState", "build_workspace_frontier_release_manifest"]
