"""Typed adapters from the public beta fixture to context-prior primitives."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .cell_context_beta import (
    CellContextBetaState,
    ContextPriorObservationParser,
    DevelopmentalLineagePrior,
    GlioblastomaMalignantStatePrior,
    H3K27AlteredDevelopmentalStatePrior,
    IdhMutantLineageStatePrior,
)
from .cell_context_beta_frontier_public_data import (
    CellContextBetaFrontierExpectedState,
    CellContextBetaFrontierOperation,
    CellContextBetaFrontierRecord,
)
from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierAdapterSpec:
    operation: CellContextBetaFrontierOperation
    primitive: str
    required_fields: tuple[str, ...]
    output_states: tuple[str, ...]
    evidence_types: tuple[str, ...]
    limits: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.primitive or not self.required_fields or not self.output_states:
            raise ValidationError("beta adapter specification is incomplete")
        if not self.evidence_types or not self.limits:
            raise ValidationError("beta adapter specification needs evidence and limits")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierAdapterResult:
    record_id: str
    operation: CellContextBetaFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any]
    warnings: tuple[str, ...]
    primitive_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.state or not self.detail:
            raise ValidationError("beta adapter result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierAdapterRegistry:
    specs: tuple[CellContextBetaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.specs) != 4 or len({item.operation for item in self.specs}) != 4:
            raise ValidationError("beta adapter registry must cover four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: CellContextBetaFrontierOperation
    ) -> CellContextBetaFrontierAdapterSpec:
        for item in self.specs:
            if item.operation is operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _context(key: str) -> ReferenceContext:
    parts = key.split("|")
    if len(parts) != 6:
        raise ValidationError("beta target context must have six parts")
    return ReferenceContext(*parts[:4], territory=parts[4], treatment_phase=parts[5])


def _rows(record: CellContextBetaFrontierRecord) -> list[dict[str, Any]]:
    try:
        value = json.loads(str(record.payload["observation_text"]))
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValidationError("beta observation_text must be JSON") from error
    rows = value.get("observations", value) if isinstance(value, Mapping) else value
    if not isinstance(rows, list):
        raise ValidationError("beta observation_text must contain an observations list")
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _result(
    record: CellContextBetaFrontierRecord,
    primitive: Any,
    issues: tuple[str, ...],
    parsed_count: int,
) -> CellContextBetaFrontierAdapterResult:
    state = primitive.state.value
    if issues and state == CellContextBetaState.SUPPORTED.value:
        state = CellContextBetaFrontierExpectedState.PARTIAL.value
    measurements = {
        "target_context_key": primitive.context_key,
        "selected_candidate_id": primitive.selected_candidate_id,
        "selected_candidate_label": primitive.selected_candidate_label,
        "candidate_ids": [item.candidate_id for item in primitive.candidates],
        "candidate_support": {
            item.candidate_id: item.support_score for item in primitive.candidates
        },
        "candidate_uncertainty": {
            item.candidate_id: item.uncertainty for item in primitive.candidates
        },
        "candidate_evidence_counts": {
            item.candidate_id: item.evidence_count for item in primitive.candidates
        },
        "evidence_ids": list(primitive.evidence_ids),
        "source_ids": list(primitive.source_ids),
        "source_versions": list(primitive.source_versions),
        "uncertainty": primitive.uncertainty,
        "applicable": primitive.applicable,
        "missing_requirements": list(primitive.missing_requirements),
        "parsed_count": parsed_count,
    }
    return CellContextBetaFrontierAdapterResult(
        record.record_id,
        record.operation,
        state,
        issues,
        primitive.reason,
        measurements,
        primitive.warnings,
        primitive.state.value,
    )


def execute_cell_context_beta_frontier_record(
    record: CellContextBetaFrontierRecord,
) -> CellContextBetaFrontierAdapterResult:
    rows = _rows(record)
    payload = record.payload
    batch = ContextPriorObservationParser().parse_text(
        json.dumps({"observations": rows}, sort_keys=True),
        source_id=str(record.source_ids[0]),
        source_version=str(payload.get("source_version", "unspecified")),
        input_format="json",
    )
    context = _context(str(payload["target_context_key"]))
    kwargs = {
        "subject_id": "aggregate-cohort",
        "model_version": str(payload.get("model_version", "beta-1")),
        "minimum_evidence": int(payload.get("minimum_evidence", 1)),
        "ambiguity_margin": float(payload.get("ambiguity_margin", 0.15)),
    }
    operation = record.operation
    if operation is CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE:
        primitive = DevelopmentalLineagePrior().estimate(context, batch.observations, **kwargs)
    elif operation is CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE:
        primitive = GlioblastomaMalignantStatePrior().estimate(
            context, batch.observations, **kwargs
        )
    elif operation is CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE:
        primitive = IdhMutantLineageStatePrior().estimate(
            context,
            batch.observations,
            declared_molecular_state=str(payload.get("declared_molecular_state", "")),
            **kwargs,
        )
    elif operation is CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE:
        primitive = H3K27AlteredDevelopmentalStatePrior().estimate(
            context,
            batch.observations,
            declared_molecular_state=str(payload.get("declared_molecular_state", "")),
            **kwargs,
        )
    else:
        raise ValidationError(f"unsupported beta operation: {operation}")
    issues = tuple(dict.fromkeys(str(item.code) for item in batch.issues))
    return _result(record, primitive, issues, len(batch.observations))


def build_cell_context_beta_frontier_adapters() -> CellContextBetaFrontierAdapterRegistry:
    states = tuple(item.value for item in CellContextBetaState)
    common = ("observation_text", "target_context_key", "model_version", "ambiguity_margin")
    specs = (
        CellContextBetaFrontierAdapterSpec(
            CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
            "DevelopmentalLineagePrior",
            common,
            states,
            ("versioned observation", "exact context", "candidate score"),
            ("not a calibrated probability", "not a diagnosis"),
        ),
        CellContextBetaFrontierAdapterSpec(
            CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
            "GlioblastomaMalignantStatePrior",
            common,
            states,
            ("disease gate", "malignant-state candidate", "contradiction"),
            ("GBM context is required", "not a diagnosis"),
        ),
        CellContextBetaFrontierAdapterSpec(
            CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
            "IdhMutantLineageStatePrior",
            common + ("declared_molecular_state",),
            states,
            ("molecular gate", "lineage candidate", "source version"),
            ("IDH-mutant declaration is required", "not a treatment claim"),
        ),
        CellContextBetaFrontierAdapterSpec(
            CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
            "H3K27AlteredDevelopmentalStatePrior",
            common + ("declared_molecular_state",),
            states,
            ("molecular gate", "developmental candidate", "ambiguity"),
            ("H3K27-altered declaration is required", "not a developmental diagnosis"),
        ),
    )
    return CellContextBetaFrontierAdapterRegistry(specs, True)


__all__ = [
    "CellContextBetaFrontierAdapterRegistry",
    "CellContextBetaFrontierAdapterResult",
    "CellContextBetaFrontierAdapterSpec",
    "build_cell_context_beta_frontier_adapters",
    "execute_cell_context_beta_frontier_record",
]
