"""Human-readable runbook steps with explicit stop conditions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRunbookStep:
    step_id: str
    order: int
    command: str
    purpose: str
    stop_if: str
    output_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRunbook:
    run_id: str
    steps: tuple[LifecycleBetaFrontierRunbookStep, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_runbook(runtime: LifecycleBetaFrontierRuntimeReport) -> LifecycleBetaFrontierRunbook:
    commands = (
        ("audit", "lifecycle-beta-frontier-data-audit", "verify public source and record receipts", "stop on boundary or source failure"),
        ("evaluate", "lifecycle-beta-frontier-evaluate", "execute positives and controls", "stop on fixture mismatch"),
        ("quality", "lifecycle-beta-frontier-quality-gate", "run blocking quality checks", "stop on any blocking check"),
        ("replay", "lifecycle-beta-frontier-replay", "replay deterministic receipts", "stop on address drift"),
        ("release", "lifecycle-beta-frontier-release", "write research-only manifest", "hold if review is required"),
    )
    steps = []
    for order, (step_id, command, purpose, stop_if) in enumerate(commands, 1):
        address = runtime.stages[order - 1].output_address if order <= len(runtime.stages) else runtime.content_address
        steps.append(LifecycleBetaFrontierRunbookStep(step_id, order, command, purpose, stop_if, address))
    return LifecycleBetaFrontierRunbook(runtime.run_id, tuple(steps), content_hash({"run_id": runtime.run_id, "steps": tuple(steps)}))


__all__ = ["LifecycleBetaFrontierRunbook", "LifecycleBetaFrontierRunbookStep", "build_lifecycle_beta_frontier_runbook"]
