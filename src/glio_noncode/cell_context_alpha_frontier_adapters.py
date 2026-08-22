"""Typed adapters from the C09-C12 fixture to context-alpha priors."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .cell_context_alpha import (
    CoreMarginTerritoryPrior,
    RecurrenceStatePrior,
    SpatialNichePrior,
    TreatmentInducedStatePrior,
)
from .cell_context_alpha_frontier_public_data import (
    CellContextAlphaFrontierOperation,
    CellContextAlphaFrontierRecord,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierAdapterSpec:
    operation: CellContextAlphaFrontierOperation
    primitive: str
    required_fields: tuple[str, ...]
    output_states: tuple[str, ...]
    retained_dimensions: tuple[str, ...]
    limits: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.primitive
            or not self.required_fields
            or not self.output_states
            or not self.retained_dimensions
            or not self.limits
        ):
            raise ValidationError("alpha adapter specification is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierAdapterResult:
    record_id: str
    operation: CellContextAlphaFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any]
    warnings: tuple[str, ...]
    primitive_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.state or not self.detail:
            raise ValidationError("alpha adapter result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierAdapterRegistry:
    specs: tuple[CellContextAlphaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.specs) != 4 or len({item.operation for item in self.specs}) != 4:
            raise ValidationError("alpha adapter registry must cover four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: CellContextAlphaFrontierOperation
    ) -> CellContextAlphaFrontierAdapterSpec:
        return next(item for item in self.specs if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rows(record: CellContextAlphaFrontierRecord) -> list[dict[str, Any]]:
    try:
        payload = json.loads(str(record.payload["observation_text"]))
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValidationError("alpha observation_text must be JSON") from error
    rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise ValidationError("alpha observation_text must contain an observations list")
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _measurements(
    operation: CellContextAlphaFrontierOperation, report: Any, parsed_count: int
) -> dict[str, Any]:
    results = [item.to_dict() for item in report.results]
    candidate_ids = []
    for item in report.results:
        candidate_ids.append(
            str(
                getattr(
                    item, "niche_id", getattr(item, "phase", getattr(item, "state_id", "unknown"))
                )
            )
        )
    return {
        "context_key": report.context_key,
        "candidate_ids": candidate_ids,
        "result_count": len(results),
        "results": results,
        "evidence_ids": [
            value for item in report.results for value in getattr(item, "observation_ids", ())
        ],
        "source_ids": sorted(
            {value for item in report.results for value in getattr(item, "source_ids", ())}
        ),
        "source_versions": ["aggregate-alpha-2026-01"],
        "uncertainty": round(
            sum(float(getattr(item, "support_spread", 0.0) or 0.0) for item in report.results)
            / max(1, len(report.results)),
            6,
        ),
        "parsed_count": parsed_count,
        "operation": operation.value,
    }


def execute_cell_context_alpha_frontier_record(
    record: CellContextAlphaFrontierRecord,
) -> CellContextAlphaFrontierAdapterResult:
    rows = _rows(record)
    context = str(record.payload["target_context_key"])
    operation = record.operation
    if operation is CellContextAlphaFrontierOperation.SPATIAL_NICHE:
        report = SpatialNichePrior().estimate(
            rows,
            context_key=context,
            ambiguity_margin=float(record.payload.get("ambiguity_margin", 0.1)),
        )
    elif operation is CellContextAlphaFrontierOperation.CORE_MARGIN:
        report = CoreMarginTerritoryPrior().estimate(
            rows,
            context_key=context,
            ambiguity_tolerance=float(record.payload.get("ambiguity_tolerance", 0.1)),
        )
    elif operation is CellContextAlphaFrontierOperation.RECURRENCE_STATE:
        report = RecurrenceStatePrior().estimate(
            rows,
            context_key=context,
            ambiguity_margin=float(record.payload.get("ambiguity_margin", 0.1)),
        )
    elif operation is CellContextAlphaFrontierOperation.TREATMENT_INDUCED:
        report = TreatmentInducedStatePrior().estimate(
            rows,
            context_key=context,
            induction_threshold=float(record.payload.get("induction_threshold", 0.1)),
        )
    else:
        raise ValidationError(f"unsupported alpha operation: {operation}")
    issue_codes = tuple(dict.fromkeys(str(item.code) for item in report.issues))
    measurements = _measurements(operation, report, len(rows))
    return CellContextAlphaFrontierAdapterResult(
        record.record_id,
        operation,
        report.state.value,
        issue_codes,
        "context-alpha report retains descriptive candidates and deltas",
        measurements,
        report.warnings,
        report.state.value,
    )


def build_cell_context_alpha_frontier_adapters() -> CellContextAlphaFrontierAdapterRegistry:
    states = (
        "supported",
        "partial",
        "ambiguous",
        "out_of_domain",
        "abstained",
        "contradictory",
        "invalid",
    )
    specs = (
        CellContextAlphaFrontierAdapterSpec(
            CellContextAlphaFrontierOperation.SPATIAL_NICHE,
            "SpatialNichePrior",
            ("observation_text", "target_context_key", "ambiguity_margin"),
            states,
            ("niche IDs", "median support", "sample aggregation", "score margin"),
            ("descriptive prior", "not cell-state truth"),
        ),
        CellContextAlphaFrontierAdapterSpec(
            CellContextAlphaFrontierOperation.CORE_MARGIN,
            "CoreMarginTerritoryPrior",
            ("observation_text", "target_context_key", "ambiguity_tolerance"),
            states,
            ("core score", "margin score", "territory label", "delta"),
            ("no localization claim", "missing sides stay partial"),
        ),
        CellContextAlphaFrontierAdapterSpec(
            CellContextAlphaFrontierOperation.RECURRENCE_STATE,
            "RecurrenceStatePrior",
            ("observation_text", "target_context_key", "ambiguity_margin"),
            states,
            ("phase", "rank", "phase margin", "source IDs"),
            ("not prognosis", "not response claim"),
        ),
        CellContextAlphaFrontierAdapterSpec(
            CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
            "TreatmentInducedStatePrior",
            ("observation_text", "target_context_key", "induction_threshold"),
            states,
            ("baseline", "post support", "delta", "induction label"),
            ("not resistance", "not treatment recommendation"),
        ),
    )
    return CellContextAlphaFrontierAdapterRegistry(specs, True)


__all__ = [
    "CellContextAlphaFrontierAdapterRegistry",
    "CellContextAlphaFrontierAdapterResult",
    "CellContextAlphaFrontierAdapterSpec",
    "build_cell_context_alpha_frontier_adapters",
    "execute_cell_context_alpha_frontier_record",
]
