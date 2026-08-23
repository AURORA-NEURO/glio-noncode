"""Compact execution transcript for audit and release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .cohort_beta_frontier_runtime_types import CohortBetaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierTranscriptLine:
    ordinal: int
    stage_id: str
    status: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierTranscript:
    lines: tuple[CohortBetaFrontierTranscriptLine, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_transcript(stages: Iterable[CohortBetaFrontierRuntimeStage]) -> CohortBetaFrontierTranscript:
    lines = tuple(CohortBetaFrontierTranscriptLine(stage.ordinal, stage.stage_id, "accepted" if stage.accepted else "held", stage.detail, content_hash({"ordinal": stage.ordinal, "stage_id": stage.stage_id, "accepted": stage.accepted}, prefix="transcript-line")) for stage in stages)
    return CohortBetaFrontierTranscript(lines, bool(lines) and all(item.status == "accepted" for item in lines), content_hash(lines, prefix="transcript"))


__all__ = ["CohortBetaFrontierTranscript", "CohortBetaFrontierTranscriptLine", "build_cohort_beta_frontier_transcript"]
