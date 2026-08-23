"""Explicit release gate checks for a platform runtime report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierReleaseCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierReleaseCheckReport:
    run_id: str
    checks: tuple[PlatformFrontierReleaseCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_release_checks(runtime: Any) -> PlatformFrontierReleaseCheckReport:
    values = (("runtime-accepted", runtime.accepted, True, "runtime closed required stages"), ("stage-count", len(runtime.stages), 24, "platform runtime contains 24 stages"), ("evaluation", runtime.evaluation.accepted, True, "row evaluation accepted"), ("quality", runtime.quality.accepted, True, "quality gate accepted"), ("replay", runtime.replay.deterministic, True, "replay is deterministic"), ("release", runtime.release.accepted, True, "release manifest accepted"), ("artifacts", runtime.artifacts.complete, True, "artifact inventory complete"), ("depth", runtime.depth.accepted, True, "depth audit accepted"), ("stage-ids", len({item.stage_id for item in runtime.stages}), len(runtime.stages), "stage IDs unique"), ("addresses", all(item.output_address.startswith("sha256:") for item in runtime.stages), True, "stage outputs addressed"))
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(PlatformFrontierReleaseCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierReleaseCheckReport(runtime.run_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierReleaseCheck", "PlatformFrontierReleaseCheckReport", "evaluate_platform_frontier_release_checks"]
