"""Runtime stage value type for the C09-C12 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRuntimeStage:
    ordinal: int
    stage_id: str
    accepted: bool
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = ["CohortAlphaFrontierRuntimeStage"]
