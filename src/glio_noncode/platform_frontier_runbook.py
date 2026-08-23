"""Executable response runbook for platform frontier failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierRunbookStep:
    step_id: str
    trigger: str
    action: str
    preserve: str
    stop_release: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierRunbook:
    steps: tuple[PlatformFrontierRunbookStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_runbook() -> PlatformFrontierRunbook:
    specs = (("preserve", "any failure", "retain original receipt", "fixture and address", True), ("classify", "failed check", "classify issue code", "check and output", True), ("review", "control or abstention", "route bounded review", "queue item", False), ("replay", "address mismatch", "replay same input", "both evaluations", True), ("repair", "contract error", "repair declared boundary", "old version", True), ("release", "all gates pass", "publish aggregate manifest", "all addresses", False))
    steps = []
    for step_id, trigger, action, preserve, stop_release in specs:
        body = {"step_id": step_id, "trigger": trigger, "action": action, "preserve": preserve, "stop_release": stop_release}
        steps.append(PlatformFrontierRunbookStep(**body, content_address=content_hash(body)))
    return PlatformFrontierRunbook(tuple(steps), len(steps) == 6, content_hash(tuple(steps)))


__all__ = ["PlatformFrontierRunbook", "PlatformFrontierRunbookStep", "build_platform_frontier_runbook"]
