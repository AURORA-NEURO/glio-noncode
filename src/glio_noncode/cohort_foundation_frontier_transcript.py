"""Human-readable stage transcript with stable ordering and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationTranscriptLine:
    ordinal: int
    stage_id: str
    status: str
    detail: str
    address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationTranscript:
    transcript_id: str
    lines: tuple[CohortFoundationTranscriptLine, ...]
    accepted: bool
    content_address: str

    def to_text(self) -> str:
        return "\n".join(f"{item.ordinal:02d} {item.status.upper():9s} {item.stage_id}: {item.detail} [{item.address}]" for item in self.lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_transcript(stages: Iterable[Any]) -> CohortFoundationTranscript:
    lines = tuple(CohortFoundationTranscriptLine(index, stage.stage_id, "accepted" if stage.accepted else "failed", stage.detail, stage.output_address, content_hash((index, stage.stage_id, stage.accepted, stage.output_address))) for index, stage in enumerate(stages, start=1))
    body = {"transcript_id": "cohort-foundation-frontier-transcript", "lines": lines}
    return CohortFoundationTranscript(body["transcript_id"], lines, bool(lines) and all(item.status == "accepted" for item in lines), content_hash(body))


__all__ = ["CohortFoundationTranscript", "CohortFoundationTranscriptLine", "build_cohort_foundation_frontier_transcript"]
