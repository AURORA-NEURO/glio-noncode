"""Operational runbook for inspecting and releasing the frontier package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class GammaFrontierRunbookStep:
    """One ordered operational step."""

    step_id: str
    phase: str
    command: str
    output_kind: str
    failure_action: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "step_id",
            "phase",
            "command",
            "output_kind",
            "failure_action",
            "detail",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierRunbook:
    """Inspectable phase-ordered runbook."""

    runbook_id: str
    version: str
    steps: tuple[GammaFrontierRunbookStep, ...]
    boundary: str
    content_address: str

    def by_phase(self, phase: str) -> tuple[GammaFrontierRunbookStep, ...]:
        return tuple(item for item in self.steps if item.phase == phase)

    def commands(self) -> tuple[str, ...]:
        return tuple(item.command for item in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "step_count": len(self.steps),
            "phases": sorted({item.phase for item in self.steps}),
        }


def _step(
    index: int, phase: str, command: str, output_kind: str, failure_action: str, detail: str
) -> GammaFrontierRunbookStep:
    body = {
        "step_id": f"gamma-runbook-{index:02d}",
        "phase": phase,
        "command": command,
        "output_kind": output_kind,
        "failure_action": failure_action,
        "detail": detail,
    }
    return GammaFrontierRunbookStep(**body, content_address=content_hash(body, prefix="runbook"))


def default_gamma_frontier_runbook() -> GammaFrontierRunbook:
    """Return the public 14-step operational sequence."""

    values = (
        (
            "inspect",
            "gamma-frontier-data-audit",
            "data-audit",
            "stop on boundary failure",
            "verify source receipts and counts",
        ),
        (
            "inspect",
            "gamma-frontier-contracts",
            "contracts",
            "stop on missing operation",
            "inspect typed operation contracts",
        ),
        (
            "inspect",
            "gamma-frontier-schema",
            "schema",
            "stop on missing required field",
            "inspect field manifest",
        ),
        (
            "execute",
            "gamma-frontier-evaluate",
            "evaluation",
            "retain failed row",
            "run positive and control records",
        ),
        (
            "execute",
            "gamma-frontier-replay",
            "replay",
            "stop on address mismatch",
            "compare repeated execution",
        ),
        (
            "inspect",
            "gamma-frontier-metrics",
            "metrics",
            "retain denominator",
            "inspect surface counts",
        ),
        (
            "inspect",
            "gamma-frontier-lineage",
            "lineage",
            "stop on disconnected output",
            "inspect source-to-output graph",
        ),
        (
            "route",
            "gamma-frontier-policy",
            "policy",
            "hold by default",
            "inspect explicit policy decisions",
        ),
        (
            "route",
            "gamma-frontier-quality-gate",
            "quality",
            "stop on blocking failure",
            "run release gate",
        ),
        (
            "route",
            "gamma-frontier-review-queue",
            "review-queue",
            "retain required review",
            "route issues and holds",
        ),
        (
            "package",
            "gamma-frontier-runtime",
            "runtime",
            "stop on stage failure",
            "run full rehearsal",
        ),
        (
            "package",
            "gamma-frontier-release",
            "release",
            "do not publish",
            "build release manifest",
        ),
        (
            "package",
            "gamma-frontier-bundle",
            "bundle",
            "do not publish",
            "assemble address-only bundle",
        ),
        (
            "package",
            "export-gamma-frontier-review-csv",
            "csv",
            "retain export error",
            "export review rows",
        ),
    )
    steps = tuple(_step(index, *value) for index, value in enumerate(values, start=1))
    body = {
        "runbook_id": "workspace-gamma-frontier-runbook",
        "version": "2026.08.d15.c09-c12.v1",
        "steps": steps,
        "boundary": (
            "research-use only; external identity and institutional controls remain required"
        ),
    }
    return GammaFrontierRunbook(
        **body, content_address=content_hash(body, prefix="runbook-manifest")
    )


__all__ = ["GammaFrontierRunbook", "GammaFrontierRunbookStep", "default_gamma_frontier_runbook"]
