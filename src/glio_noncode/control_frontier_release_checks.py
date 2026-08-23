"""Explicit release gate checks over the complete control frontier runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_runtime import ControlFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierReleaseCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierReleaseCheckReport:
    run_id: str
    checks: tuple[ControlFrontierReleaseCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_control_frontier_release_checks(runtime: ControlFrontierRuntimeReport) -> ControlFrontierReleaseCheckReport:
    """Evaluate the release gate without changing runtime state."""

    values = (
        ("runtime-accepted", runtime.accepted, True, "runtime closed all required stages"),
        ("stage-count", len(runtime.stages), 24, "ordered depth runtime contains 24 stages"),
        ("evaluation-accepted", runtime.evaluation.accepted, True, "positive and control row evaluation passed"),
        ("quality-accepted", runtime.quality.accepted, True, "quality gate passed"),
        ("replay-deterministic", runtime.replay.deterministic, True, "replay agrees with execution"),
        ("release-accepted", runtime.release.accepted, True, "release manifest is bounded"),
        ("artifact-complete", runtime.artifacts.complete, True, "artifact inventory closes"),
        ("depth-accepted", runtime.depth.accepted, True, "depth audit passed"),
        ("unique-stages", len({item.stage_id for item in runtime.stages}), len(runtime.stages), "stage identifiers are unique"),
        ("addressed-stages", all(item.output_address.startswith("sha256:") for item in runtime.stages), True, "every stage has an output address"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(ControlFrontierReleaseCheck(**body, content_address=content_hash(body)))
    return ControlFrontierReleaseCheckReport(runtime.run_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["ControlFrontierReleaseCheck", "ControlFrontierReleaseCheckReport", "evaluate_control_frontier_release_checks"]
