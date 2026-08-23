"""Runtime stage types for the validation-beta frontier rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierRuntimeStage:
    sequence: int
    stage_id: str
    accepted: bool
    state: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = ["ValidationBetaFrontierRuntimeStage"]
