"""Treatment delta and territory contrast depth surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierDeltaObservation:
    record_id: str
    operation: str
    baseline: float | None
    post_treatment: float | None
    delta: float | None
    label: str
    context_qualified: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierDeltaDepthReport:
    observations: tuple[CellContextAlphaFrontierDeltaObservation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(sorted({item.label for item in self.observations}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"labels": list(self.labels)}


def audit_cell_context_alpha_frontier_deltas(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierDeltaDepthReport:
    observations = []
    for row in evaluation.records:
        for result in row.adapter.measurements.get("results", ()):
            if not isinstance(result, dict):
                continue
            observations.append(
                CellContextAlphaFrontierDeltaObservation(
                    row.record_id,
                    row.operation,
                    result.get("baseline_support"),
                    result.get("post_treatment_support"),
                    result.get("support_delta", result.get("core_margin_delta")),
                    str(
                        result.get(
                            "induction_label", result.get("territory_label", "not-applicable")
                        )
                    ),
                    row.adapter.measurements.get("context_key")
                    == row.record.payload.get("target_context_key"),
                )
            )
    labels = {item.label for item in observations}
    accepted = (
        bool(observations)
        and {"induced", "stable"}.issubset(labels)
        and all(
            item.context_qualified or row_state == "out_of_domain"
            for item in observations
            for row_state in ("out_of_domain",)
        )
    )
    return CellContextAlphaFrontierDeltaDepthReport(tuple(observations), accepted)


__all__ = [
    "CellContextAlphaFrontierDeltaDepthReport",
    "CellContextAlphaFrontierDeltaObservation",
    "audit_cell_context_alpha_frontier_deltas",
]
