"""Human-readable execution transcript built from immutable stage records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTranscriptLine:
    sequence: int
    stage_id: str
    status: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTranscript:
    lines: tuple[CohortAlphaFrontierTranscriptLine, ...]
    text: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_transcript(stages: tuple[CohortAlphaFrontierRuntimeStage, ...]) -> CohortAlphaFrontierTranscript:
    lines = tuple(CohortAlphaFrontierTranscriptLine(index, stage.stage_id, "accepted" if stage.accepted else "blocked", stage.detail, content_hash({"sequence": index, "stage": stage.stage_id, "status": stage.accepted, "detail": stage.detail}, prefix="alpha-transcript-line")) for index, stage in enumerate(stages, 1))
    text = "\n".join(f"{line.sequence:02d} | {line.status:<8} | {line.stage_id} | {line.detail}" for line in lines)
    return CohortAlphaFrontierTranscript(lines, text, bool(lines) and all(item.status == "accepted" for item in lines), content_hash({"lines": lines, "text": text}, prefix="alpha-transcript"))


__all__ = ["CohortAlphaFrontierTranscript", "CohortAlphaFrontierTranscriptLine", "build_cohort_alpha_frontier_transcript"]
