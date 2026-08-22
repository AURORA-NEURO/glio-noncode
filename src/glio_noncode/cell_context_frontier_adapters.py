"""Typed adapters from the C01-C04 fixture to Domain 08 primitives."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .cell_context import (
    AdultPediatricRouter,
    CellStateContextAssembler,
    ContextObservationParser,
    ContextResolutionState,
    DiseaseOntologyContextualizer,
    MalignantMicroenvironmentTerritoryResolver,
    MolecularClassStateContextualizer,
)
from .cell_context_frontier_public_data import (
    CellContextFrontierExpectedState,
    CellContextFrontierOperation,
    CellContextFrontierRecord,
)
from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierAdapterSpec:
    operation: CellContextFrontierOperation
    primitive: str
    required_fields: tuple[str, ...]
    output_states: tuple[str, ...]
    evidence_types: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.primitive or not self.required_fields or not self.output_states:
            raise ValidationError("cell context adapter spec is incomplete")
        if not self.limitations or not self.evidence_types:
            raise ValidationError("cell context adapter spec needs limits and evidence")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierAdapterResult:
    record_id: str
    operation: CellContextFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any]
    warnings: tuple[str, ...]
    primitive_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.state or not self.detail:
            raise ValidationError("cell context adapter result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierAdapterRegistry:
    specs: tuple[CellContextFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.specs) != 4 or len({item.operation for item in self.specs}) != 4:
            raise ValidationError("cell context adapter registry must cover four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: CellContextFrontierOperation
    ) -> CellContextFrontierAdapterSpec:
        for item in self.specs:
            if item.operation is operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rows(record: CellContextFrontierRecord) -> list[dict[str, Any]]:
    try:
        payload = json.loads(str(record.payload["observation_text"]))
    except (TypeError, json.JSONDecodeError, KeyError) as error:
        raise ValidationError("observation_text must be JSON") from error
    rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise ValidationError("observation_text must contain an observations list")
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _context(key: str) -> ReferenceContext:
    parts = key.split("|")
    if len(parts) != 6:
        raise ValidationError("context key must have six parts")
    return ReferenceContext(*parts[:4], territory=parts[4], treatment_phase=parts[5])


def _codes(issues: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item.code) for item in issues))


def _result(
    record: CellContextFrontierRecord,
    state: str,
    issue_codes: tuple[str, ...],
    detail: str,
    measurements: Mapping[str, Any],
    warnings: tuple[str, ...],
    primitive_state: str,
) -> CellContextFrontierAdapterResult:
    return CellContextFrontierAdapterResult(
        record.record_id,
        record.operation,
        state,
        tuple(dict.fromkeys(issue_codes)),
        detail,
        measurements,
        warnings,
        primitive_state,
    )


def _foreign_only(rows: list[dict[str, Any]], context_key: str) -> bool:
    contexts = {str(row.get("context_key", row.get("context", ""))) for row in rows}
    return bool(contexts) and context_key not in contexts


def _resolution_result(
    record: CellContextFrontierRecord,
    resolution: Any,
    issue_codes: tuple[str, ...],
    *,
    detail: str,
) -> CellContextFrontierAdapterResult:
    state = resolution.state.value
    if state == ContextResolutionState.SUPPORTED.value and issue_codes:
        state = CellContextFrontierExpectedState.PARTIAL.value
    return _result(
        record,
        state,
        issue_codes,
        detail,
        {
            "dimension": resolution.dimension.value,
            "selected_candidate_id": resolution.selected_candidate_id,
            "selected_candidate_label": resolution.selected_candidate_label,
            "candidate_ids": [item.candidate_id for item in resolution.candidates],
            "candidate_labels": [item.candidate_label for item in resolution.candidates],
            "evidence_ids": list(resolution.evidence_ids),
            "source_ids": list(resolution.source_ids),
            "uncertainty": resolution.uncertainty,
        },
        resolution.limitations,
        resolution.state.value,
    )


def _disease_operation(record: CellContextFrontierRecord) -> CellContextFrontierAdapterResult:
    rows = _rows(record)
    parser = ContextObservationParser()
    batch = parser.parse_text(
        json.dumps({"observations": rows}, sort_keys=True),
        source_id=record.source_ids[0],
        input_format="json",
    )
    if _foreign_only(rows, record.context_key):
        return _result(
            record,
            "out_of_domain",
            _codes(batch.issues),
            "disease context rows are outside the exact target context",
            {"parsed_count": len(batch.observations), "foreign_only": True},
            ("Context transport is not inferred.",),
            "out_of_domain",
        )
    resolution = DiseaseOntologyContextualizer().resolve(
        _context(record.context_key), batch.observations, subject_id="aggregate-cohort"
    )
    return _resolution_result(
        record,
        resolution,
        _codes(batch.issues),
        detail="disease ontology candidates are exact-context and taxonomy-scoped",
    )


def _age_operation(record: CellContextFrontierRecord) -> CellContextFrontierAdapterResult:
    rows = _rows(record)
    batch = ContextObservationParser().parse_text(
        json.dumps({"observations": rows}, sort_keys=True),
        source_id=record.source_ids[0],
        input_format="json",
    )
    if _foreign_only(rows, record.context_key):
        return _result(
            record,
            "out_of_domain",
            _codes(batch.issues),
            "age observations are outside the exact target context",
            {"parsed_count": len(batch.observations), "foreign_only": True},
            ("Age routes are not transported across context.",),
            "out_of_domain",
        )
    resolution = AdultPediatricRouter().route(
        _context(record.context_key), batch.observations, subject_id="aggregate-cohort"
    )
    return _resolution_result(
        record,
        resolution,
        _codes(batch.issues),
        detail="adult or pediatric routing preserves declared context and conflict",
    )


def _molecular_operation(record: CellContextFrontierRecord) -> CellContextFrontierAdapterResult:
    rows = _rows(record)
    batch = ContextObservationParser().parse_text(
        json.dumps({"observations": rows}, sort_keys=True),
        source_id=record.source_ids[0],
        input_format="json",
    )
    if _foreign_only(rows, record.context_key):
        return _result(
            record,
            "out_of_domain",
            _codes(batch.issues),
            "molecular observations are outside the exact target context",
            {"parsed_count": len(batch.observations), "foreign_only": True},
            ("Molecular context is not transported across groups.",),
            "out_of_domain",
        )
    resolution = MolecularClassStateContextualizer().resolve(
        _context(record.context_key), batch.observations, subject_id="aggregate-cohort"
    )
    state = resolution.state.value
    if batch.issues and state == ContextResolutionState.SUPPORTED.value:
        state = "partial"
    return _result(
        record,
        state,
        _codes(batch.issues),
        "molecular class and molecular state are resolved as separate dimensions",
        {
            "molecular_state": resolution.state.value,
            "class_state": resolution.molecular_class.state.value,
            "class_candidate_ids": [
                item.candidate_id for item in resolution.molecular_class.candidates
            ],
            "state_candidate_ids": [
                item.candidate_id for item in resolution.molecular_state.candidates
            ],
            "class_uncertainty": resolution.molecular_class.uncertainty,
            "state_uncertainty": resolution.molecular_state.uncertainty,
            "uncertainty": resolution.uncertainty,
        },
        resolution.limitations,
        resolution.state.value,
    )


def _assembly_operation(record: CellContextFrontierRecord) -> CellContextFrontierAdapterResult:
    rows = _rows(record)
    batch = ContextObservationParser().parse_text(
        json.dumps({"observations": rows}, sort_keys=True),
        source_id=record.source_ids[0],
        input_format="json",
    )
    context = _context(record.context_key)
    observations = batch.observations
    disease = DiseaseOntologyContextualizer().resolve(
        context, observations, subject_id="aggregate-cohort"
    )
    age = AdultPediatricRouter().route(context, observations, subject_id="aggregate-cohort")
    molecular = MolecularClassStateContextualizer().resolve(
        context, observations, subject_id="aggregate-cohort"
    )
    territory = MalignantMicroenvironmentTerritoryResolver().resolve(
        context, observations, subject_id="aggregate-cohort"
    )
    assembled = CellStateContextAssembler().assemble(
        "aggregate-cohort", context, disease, age, molecular, territory
    )
    state = assembled.state.value
    codes = _codes(batch.issues)
    if state == ContextResolutionState.SUPPORTED.value and codes:
        state = "partial"
    return _result(
        record,
        state,
        codes,
        "territory candidates propagate through a full disease, age, molecular, "
        "and context assembly",
        {
            "assembled_state": assembled.state.value,
            "disease_state": assembled.disease.state.value,
            "age_state": assembled.age_route.state.value,
            "molecular_state": assembled.molecular.state.value,
            "territory_state": assembled.territory.state.value,
            "territory_candidates": [item.candidate_id for item in territory.candidates],
            "source_ids": list(assembled.source_ids),
            "uncertainty": assembled.uncertainty,
        },
        assembled.limitations
        + ("Territory identity remains a taxonomy observation, not a clinical label.",),
        assembled.state.value,
    )


def execute_cell_context_frontier_record(
    record: CellContextFrontierRecord,
) -> CellContextFrontierAdapterResult:
    """Execute one row against the Domain 08 primitive for its operation."""

    try:
        if record.operation is CellContextFrontierOperation.DISEASE_ONTOLOGY:
            return _disease_operation(record)
        if record.operation is CellContextFrontierOperation.AGE_ROUTE:
            return _age_operation(record)
        if record.operation is CellContextFrontierOperation.MOLECULAR_STATE:
            return _molecular_operation(record)
        if record.operation is CellContextFrontierOperation.TERRITORY_ASSEMBLY:
            return _assembly_operation(record)
    except (TypeError, ValueError, ValidationError, KeyError) as error:
        return _result(
            record,
            "invalid",
            ("invalid_payload",),
            str(error),
            {},
            ("Malformed context input remains visible as invalid.",),
            "invalid",
        )
    raise ValidationError(f"unsupported cell context operation: {record.operation}")


def build_cell_context_frontier_adapters() -> CellContextFrontierAdapterRegistry:
    states = tuple(item.value for item in CellContextFrontierExpectedState)
    specs = (
        CellContextFrontierAdapterSpec(
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            "DiseaseOntologyContextualizer.resolve",
            ("observation_text", "context_key", "source_receipt"),
            states,
            ("disease ontology", "candidate", "exact context"),
            ("Taxonomy does not diagnose.", "Missing support is not negative."),
        ),
        CellContextFrontierAdapterSpec(
            CellContextFrontierOperation.AGE_ROUTE,
            "AdultPediatricRouter.route",
            ("observation_text", "context_key", "source_receipt"),
            states,
            ("adult route", "pediatric route", "declared context"),
            ("Unknown age abstains.", "Conflicting evidence is not silently overridden."),
        ),
        CellContextFrontierAdapterSpec(
            CellContextFrontierOperation.MOLECULAR_STATE,
            "MolecularClassStateContextualizer.resolve",
            ("observation_text", "context_key", "source_receipt"),
            states,
            ("molecular class", "molecular state", "uncertainty"),
            ("Class and state remain separate.", "No pathogenicity is inferred."),
        ),
        CellContextFrontierAdapterSpec(
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            "CellStateContextAssembler.assemble",
            ("observation_text", "context_key", "source_receipt"),
            states,
            ("territory", "disease", "age", "molecular", "assembled context"),
            ("Ambiguous territory propagates.", "Assembly is research context, not diagnosis."),
        ),
    )
    return CellContextFrontierAdapterRegistry(specs, True)


__all__ = [
    "CellContextFrontierAdapterRegistry",
    "CellContextFrontierAdapterResult",
    "CellContextFrontierAdapterSpec",
    "build_cell_context_frontier_adapters",
    "execute_cell_context_frontier_record",
]
