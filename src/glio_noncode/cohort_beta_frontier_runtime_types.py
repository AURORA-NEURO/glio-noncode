"""Small runtime value types kept separate to avoid governance import cycles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRuntimeStage:
    ordinal: int
    stage_id: str
    accepted: bool
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = ["CohortBetaFrontierRuntimeStage"]
