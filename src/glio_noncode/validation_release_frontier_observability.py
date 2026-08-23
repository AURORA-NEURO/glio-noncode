"""Structured stage observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseStageObservation:
    stage_id: str
    sequence: int
    state: str
    detail: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseTrace:
    run_id: str
    observations: tuple[ValidationReleaseStageObservation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_trace(run_id: str, observations: tuple[dict[str, Any], ...], accepted: bool) -> ValidationReleaseTrace:
    rows = []
    for sequence, raw in enumerate(observations, start=1):
        body = {"stage_id": raw["stage_id"], "sequence": sequence, "state": raw.get("state", "completed"), "detail": raw.get("detail", ""), "output_address": raw["output_address"]}
        rows.append(ValidationReleaseStageObservation(**body, content_address=content_hash(body)))
    return ValidationReleaseTrace(run_id, tuple(rows), accepted, content_hash(tuple(rows)))


__all__ = ["ValidationReleaseStageObservation", "ValidationReleaseTrace", "build_validation_release_trace"]
