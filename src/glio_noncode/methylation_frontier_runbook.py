"""Operational runbook for inspecting the methylation frontier package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierRunbookStep:
    step_id: str
    phase: str
    command: str
    output_kind: str
    failure_action: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not all(
            (
                self.step_id,
                self.phase,
                self.command,
                self.output_kind,
                self.failure_action,
                self.detail,
            )
        ):
            raise ValidationError("runbook step is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierRunbook:
    runbook_id: str
    version: str
    steps: tuple[MethylationFrontierRunbookStep, ...]
    boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.runbook_id or not self.version or not self.steps or not self.boundary:
            raise ValidationError("runbook is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def by_phase(self, phase: str) -> tuple[MethylationFrontierRunbookStep, ...]:
        return tuple(step for step in self.steps if step.phase == phase)

    def commands(self) -> tuple[str, ...]:
        return tuple(step.command for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "step_count": len(self.steps),
            "phases": sorted({step.phase for step in self.steps}),
        }


def _step(index: int, value: tuple[str, str, str, str, str]) -> MethylationFrontierRunbookStep:
    phase, command, output_kind, failure_action, detail = value
    return MethylationFrontierRunbookStep(
        f"methylation-runbook-{index:02d}", phase, command, output_kind, failure_action, detail
    )


def default_methylation_frontier_runbook() -> MethylationFrontierRunbook:
    values = (
        (
            "inspect",
            "methylation-frontier-data-audit",
            "data-audit",
            "stop on boundary failure",
            "verify source receipts and counts",
        ),
        (
            "inspect",
            "methylation-frontier-catalog",
            "catalog",
            "stop on missing operation",
            "inspect operation and source catalog",
        ),
        (
            "inspect",
            "methylation-frontier-contracts",
            "contracts",
            "stop on missing field",
            "inspect typed operation contracts",
        ),
        (
            "inspect",
            "methylation-frontier-schema",
            "schema",
            "stop on schema failure",
            "inspect field and boundary checks",
        ),
        (
            "execute",
            "methylation-frontier-evaluate",
            "evaluation",
            "retain failed row",
            "run positive and control records",
        ),
        (
            "execute",
            "methylation-frontier-replay",
            "replay",
            "stop on receipt mismatch",
            "compare repeated execution",
        ),
        (
            "inspect",
            "methylation-frontier-metrics",
            "metrics",
            "retain denominator",
            "inspect operation and quality ratios",
        ),
        (
            "inspect",
            "methylation-frontier-lineage",
            "lineage",
            "stop on disconnected result",
            "inspect source-to-result edges",
        ),
        (
            "route",
            "methylation-frontier-policy",
            "policy",
            "hold by default",
            "inspect release and review decisions",
        ),
        (
            "route",
            "methylation-frontier-quality",
            "quality",
            "stop on blocking failure",
            "run release gate",
        ),
        (
            "route",
            "methylation-frontier-review-queue",
            "review",
            "retain required review",
            "route uncertainty and controls",
        ),
        (
            "package",
            "methylation-frontier-runtime",
            "runtime",
            "stop on stage failure",
            "run full rehearsal",
        ),
        (
            "package",
            "methylation-frontier-release",
            "release",
            "do not publish",
            "build release manifest",
        ),
        (
            "package",
            "methylation-frontier-bundle",
            "bundle",
            "do not publish",
            "assemble address-only bundle",
        ),
        (
            "package",
            "methylation-frontier-accessibility",
            "a11y",
            "retain failed surface",
            "check labels and state text",
        ),
        (
            "package",
            "methylation-frontier-compliance",
            "boundary",
            "do not publish",
            "check public aggregate boundary",
        ),
        (
            "package",
            "methylation-frontier-validation",
            "validation",
            "retain failed axis",
            "run operation-by-axis matrix",
        ),
        (
            "export",
            "export-methylation-frontier-review",
            "review-export",
            "retain export error",
            "export review-safe rows",
        ),
    )
    steps = tuple(_step(index, value) for index, value in enumerate(values, start=1))
    return MethylationFrontierRunbook(
        "methylation-frontier-runbook",
        "2026.08.d07.c05-c08.v1",
        steps,
        "research-use only; public aggregate evidence and explicit uncertainty are required",
    )


__all__ = [
    "MethylationFrontierRunbook",
    "MethylationFrontierRunbookStep",
    "default_methylation_frontier_runbook",
]
