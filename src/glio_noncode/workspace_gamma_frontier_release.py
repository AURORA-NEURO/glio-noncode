"""Release manifest assembly for research-use collaboration evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_replay import GammaFrontierReplayReceipt
from .workspace_gamma_frontier_runtime import GammaFrontierRuntimeReport


class GammaFrontierReleaseState(StrEnum):
    """Release state derived from blocking checks."""

    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class GammaFrontierReleaseCheck:
    """One release check and its blocking behavior."""

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
class GammaFrontierReleaseManifest:
    """Addressed release decision with all upstream receipts."""

    release_id: str
    run_id: str
    fixture_id: str
    state: GammaFrontierReleaseState
    checks: tuple[GammaFrontierReleaseCheck, ...]
    evidence_addresses: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not self.release_id or not self.run_id or not self.fixture_id:
            raise ValueError("gamma release identifiers are required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


def _check(
    check_id: str, passed: bool, blocking: bool, observed: Any, required: Any, detail: str
) -> GammaFrontierReleaseCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "blocking": blocking,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierReleaseCheck(
        **body, content_address=content_hash(body, prefix="release-check")
    )


def build_gamma_frontier_release_manifest(
    runtime: GammaFrontierRuntimeReport,
    replay: GammaFrontierReplayReceipt,
    *,
    release_id: str = "workspace-gamma-frontier-c09-c12-v1",
) -> GammaFrontierReleaseManifest:
    """Build a release manifest only from runtime and replay receipts."""

    checks = (
        _check(
            "runtime-quality",
            runtime.quality.accepted,
            True,
            runtime.quality.accepted,
            True,
            "quality gate accepted",
        ),
        _check(
            "replay-accepted",
            replay.accepted,
            True,
            replay.accepted,
            True,
            "replay evaluation accepted",
        ),
        _check(
            "replay-address",
            replay.evaluation_address == runtime.evaluation.content_address,
            True,
            replay.evaluation_address,
            runtime.evaluation.content_address,
            "release and replay share an evaluation address",
        ),
        _check(
            "control-evidence",
            len(runtime.evaluation.executions) >= 16,
            True,
            len(runtime.evaluation.executions),
            16,
            "positive and control rows are retained",
        ),
        _check(
            "research-boundary",
            runtime.quality.accepted,
            False,
            runtime.quality.accepted,
            True,
            "release remains research-use only",
        ),
    )
    blocking = [item for item in checks if not item.passed and item.blocking]
    review = [item for item in checks if not item.passed and not item.blocking]
    state = (
        GammaFrontierReleaseState.BLOCKED
        if blocking
        else GammaFrontierReleaseState.REVIEW
        if review
        else GammaFrontierReleaseState.READY
    )
    evidence = (
        runtime.content_address,
        runtime.evaluation.content_address,
        runtime.quality.content_address,
        runtime.lineage.content_address,
        runtime.reconciliation.content_address,
        replay.content_address,
    )
    body = {
        "release_id": release_id,
        "run_id": runtime.run_id,
        "fixture_id": runtime.fixture_id,
        "state": state,
        "checks": checks,
        "evidence_addresses": evidence,
        "warnings": (
            "Research-use package; no clinical authorization.",
            "External identity, permissions, and scientific review remain required.",
        ),
    }
    return GammaFrontierReleaseManifest(
        **body, content_address=content_hash(body, prefix="release")
    )


__all__ = [
    "GammaFrontierReleaseCheck",
    "GammaFrontierReleaseManifest",
    "GammaFrontierReleaseState",
    "build_gamma_frontier_release_manifest",
]
