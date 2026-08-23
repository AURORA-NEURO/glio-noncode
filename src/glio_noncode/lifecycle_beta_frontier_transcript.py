"""Plain-text transcript for a completed lifecycle beta run."""

from __future__ import annotations

from dataclasses import dataclass

from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierTranscript:
    run_id: str
    lines: tuple[str, ...]
    content_address: str

    def to_text(self) -> str:
        return "\n".join(self.lines) + "\n"

    def to_dict(self) -> dict[str, object]:
        return jsonable(self)


def build_lifecycle_beta_frontier_transcript(runtime: LifecycleBetaFrontierRuntimeReport) -> LifecycleBetaFrontierTranscript:
    lines = [f"run_id={runtime.run_id}", f"accepted={runtime.accepted}", f"fixture_id={runtime.fixture.fixture_id}", f"content_address={runtime.content_address}"]
    lines.extend(f"{item.sequence:02d} {item.stage_id} state={item.state} output={item.output_address} duration_ms={item.duration_ms}" for item in runtime.stages)
    return LifecycleBetaFrontierTranscript(runtime.run_id, tuple(lines), content_hash(tuple(lines)))


__all__ = ["LifecycleBetaFrontierTranscript", "build_lifecycle_beta_frontier_transcript"]
