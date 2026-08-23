"""Runtime trace materialization for D07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureRuntimeStage, addressed
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureTrace:
    fixture_id: str
    stages: tuple[ChromatinArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_chromatin_architecture_run(
    fixture_id: str,
    stages: tuple[ChromatinArchitectureRuntimeStage, ...],
) -> ChromatinArchitectureTrace:
    body = {
        "fixture_id": fixture_id,
        "stage_ids": tuple(item.stage_id for item in stages),
        "addresses": tuple(item.output_address for item in stages),
    }
    return ChromatinArchitectureTrace(
        fixture_id=fixture_id,
        stages=stages,
        accepted=bool(stages) and all(item.state == "accepted" for item in stages),
        content_address=addressed(body, "chromatin-observability"),
    )


__all__ = ["ChromatinArchitectureTrace", "observe_chromatin_architecture_run"]
