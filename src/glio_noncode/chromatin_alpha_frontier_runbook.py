"""Operational runbook for the chromatin-alpha tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierRunbookStep:
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
class ChromatinAlphaFrontierRunbook:
    runbook_id: str
    version: str
    steps: tuple[ChromatinAlphaFrontierRunbookStep, ...]
    boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.runbook_id or not self.version or not self.steps or not self.boundary:
            raise ValidationError("runbook is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def by_phase(self, phase: str) -> tuple[ChromatinAlphaFrontierRunbookStep, ...]:
        return tuple(step for step in self.steps if step.phase == phase)

    def commands(self) -> tuple[str, ...]:
        return tuple(step.command for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "step_count": len(self.steps),
            "phases": sorted({step.phase for step in self.steps}),
        }


def _step(index: int, value: tuple[str, str, str, str, str]) -> ChromatinAlphaFrontierRunbookStep:
    phase, command, output_kind, failure_action, detail = value
    return ChromatinAlphaFrontierRunbookStep(
        f"chromatin-alpha-runbook-{index:02d}", phase, command, output_kind, failure_action, detail
    )


def default_chromatin_alpha_frontier_runbook() -> ChromatinAlphaFrontierRunbook:
    values = (
        (
            "inspect",
            "chromatin-alpha-frontier-data",
            "data-audit",
            "stop on boundary failure",
            "verify public sources, versions, and counts",
        ),
        (
            "inspect",
            "chromatin-alpha-frontier-catalog",
            "catalog",
            "stop on missing operation",
            "inspect operation and source catalog",
        ),
        (
            "inspect",
            "chromatin-alpha-frontier-contracts",
            "contracts",
            "stop on missing field",
            "inspect typed primitive contracts",
        ),
        (
            "inspect",
            "chromatin-alpha-frontier-schema",
            "schema",
            "stop on schema failure",
            "inspect field and aggregate-boundary checks",
        ),
        (
            "execute",
            "chromatin-alpha-frontier-evaluate",
            "evaluation",
            "retain failed row",
            "execute four positive and twelve control rows",
        ),
        (
            "execute",
            "chromatin-alpha-frontier-replay",
            "replay",
            "stop on address mismatch",
            "compare repeated execution receipts",
        ),
        (
            "inspect",
            "chromatin-alpha-frontier-metrics",
            "metrics",
            "retain denominator",
            "inspect operation, state, and issue counts",
        ),
        (
            "inspect",
            "chromatin-alpha-frontier-lineage",
            "lineage",
            "stop on disconnected result",
            "inspect source-to-result edges",
        ),
        (
            "route",
            "chromatin-alpha-frontier-policy",
            "policy",
            "hold by default",
            "inspect release, review, and quarantine decisions",
        ),
        (
            "route",
            "chromatin-alpha-frontier-quality",
            "quality",
            "stop on blocking failure",
            "run quality gate and retain warnings",
        ),
        (
            "route",
            "chromatin-alpha-frontier-review-queue",
            "review",
            "retain required review",
            "route foreign, mixed, partial, and invalid paths",
        ),
        (
            "package",
            "chromatin-alpha-frontier-runtime",
            "runtime",
            "stop on stage failure",
            "run ten-stage rehearsal",
        ),
        (
            "package",
            "chromatin-alpha-frontier-release",
            "release",
            "do not publish",
            "build release manifest and cautions",
        ),
        (
            "package",
            "chromatin-alpha-frontier-bundle",
            "bundle",
            "do not publish",
            "assemble content-addressed results",
        ),
        (
            "package",
            "chromatin-alpha-frontier-accessibility",
            "a11y",
            "retain failed surface",
            "check labels and receipt fields",
        ),
        (
            "package",
            "chromatin-alpha-frontier-compliance",
            "boundary",
            "do not publish",
            "check aggregate-only fields",
        ),
        (
            "package",
            "chromatin-alpha-frontier-validation",
            "validation",
            "retain failed axis",
            "run operation-by-axis matrix",
        ),
        (
            "export",
            "export-chromatin-alpha-frontier-review",
            "review-export",
            "retain export error",
            "export sanitized review rows",
        ),
    )
    return ChromatinAlphaFrontierRunbook(
        "chromatin-alpha-frontier-runbook",
        "2026.08.d07.c09-c12.v1",
        tuple(_step(index, value) for index, value in enumerate(values, start=1)),
        (
            "research-use only; aggregate sources, explicit uncertainty, and declared "
            "references are required"
        ),
    )


__all__ = [
    "ChromatinAlphaFrontierRunbook",
    "ChromatinAlphaFrontierRunbookStep",
    "default_chromatin_alpha_frontier_runbook",
]
