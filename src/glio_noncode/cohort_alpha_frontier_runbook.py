"""Operational runbook for repeatable C09-C12 execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierQualityGate, CohortAlphaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRunbookStep:
    step_id: str
    order: int
    command: str
    expected: str
    stop_on_failure: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRunbook:
    runbook_id: str
    prerequisites: tuple[str, ...]
    steps: tuple[CohortAlphaFrontierRunbookStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_runbook(quality: CohortAlphaFrontierQualityGate, manifest: CohortAlphaFrontierReleaseManifest) -> CohortAlphaFrontierRunbook:
    raw = (("fixture", "python -m glio_noncode.cli cohort-alpha-frontier-fixture", "fixture file emitted"), ("evaluate", "python -m glio_noncode.cli cohort-alpha-frontier-evaluate", "sixteen rows evaluated"), ("quality", "python -m glio_noncode.cli cohort-alpha-frontier-quality", "quality gate accepted"), ("replay", "python -m glio_noncode.cli cohort-alpha-frontier-replay", "replay deterministic"), ("report", "python -m glio_noncode.cli cohort-alpha-frontier-report", "markdown report emitted"), ("release", "python -m glio_noncode.cli run-cohort-alpha-frontier-pipeline", "manifest ready"))
    steps = tuple(CohortAlphaFrontierRunbookStep(f"runbook-{step_id}", index, command, expected, True, content_hash({"step_id": step_id, "order": index, "command": command, "expected": expected}, prefix="alpha-runbook-step")) for index, (step_id, command, expected) in enumerate(raw, 1))
    return CohortAlphaFrontierRunbook("cohort-alpha-frontier-runbook", ("Python 3.11", "public fixture receipt", "clean output directory"), steps, quality.accepted and manifest.ready and len(steps) == 6, content_hash({"steps": steps, "quality": quality.content_address, "manifest": manifest.content_address}, prefix="alpha-runbook"))


__all__ = ["CohortAlphaFrontierRunbook", "CohortAlphaFrontierRunbookStep", "build_cohort_alpha_frontier_runbook"]
