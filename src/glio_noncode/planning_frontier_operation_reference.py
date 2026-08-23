"""Detailed operation reference used by API consumers and release reviewers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReferenceField:
    operation: PlanningOperation
    field_name: str
    type_name: str
    lifecycle: str
    review_question: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningOperationReference:
    operation: PlanningOperation
    purpose: str
    fields: tuple[PlanningReferenceField, ...]
    review_questions: tuple[str, ...]
    excluded_interpretations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(operation: PlanningOperation, name: str, type_name: str, lifecycle: str, question: str) -> PlanningReferenceField:
    body = {"operation": operation, "field_name": name, "type_name": type_name, "lifecycle": lifecycle, "review_question": question}
    return PlanningReferenceField(**body, content_address=content_hash(body, prefix="planning-reference-field"))


def _reference(operation: PlanningOperation, purpose: str, rows: tuple[tuple[str, str, str, str], ...], questions: tuple[str, ...]) -> PlanningOperationReference:
    fields = tuple(_field(operation, *row) for row in rows)
    exclusions = ("not a biological efficacy result", "not a safety result", "not a clinical result", "not institutional approval")
    body = {"operation": operation, "purpose": purpose, "fields": fields, "review_questions": questions, "excluded_interpretations": exclusions}
    return PlanningOperationReference(**body, content_address=content_hash(body, prefix="planning-operation-reference"))


def build_planning_operation_references() -> tuple[PlanningOperationReference, ...]:
    return (
        _reference(PlanningOperation.MODEL_ELIGIBILITY, "exact-context model-system gate", (
            ("request_id", "string", "input", "what request is being reviewed?"),
            ("context_key", "exact context", "input", "does the request use the required context?"),
            ("model_system", "string", "input", "what model family is requested?"),
            ("model_id", "string", "observation", "is each model uniquely identified?"),
            ("cell_state", "string", "observation", "is cell state explicit?"),
            ("declared_context_keys", "sequence[string]", "observation", "does the source declare support?"),
            ("evidence_strength", "ordinal enum", "observation", "does strength meet the floor?"),
            ("supports_context", "boolean", "observation", "does the row affirm support?"),
            ("blockers", "sequence[string]", "observation", "are blockers visible?"),
            ("eligible", "boolean", "output", "is eligibility only a planning gate?"),
            ("observation_address", "content address", "output", "can the row be replayed?"),
            ("eligible_count", "integer", "output", "is the denominator visible?"),
        ), ("Was context support declared?", "Was evidence strength above the threshold?", "Were blockers retained?", "Is the result free of fidelity language?")),
        _reference(PlanningOperation.GUIDE_OLIGO, "lossless public guide and oligo adaptation", (
            ("source_id", "string", "input", "can the source be cited?"),
            ("source_version", "string", "input", "can the source snapshot be identified?"),
            ("input_format", "enum", "input", "was parser behavior explicit?"),
            ("text", "JSON CSV TSV", "input", "is the original public row set supplied?"),
            ("observation_id", "string", "row", "is the observation unique?"),
            ("design_id", "string", "row", "is design identity retained?"),
            ("target_id", "string", "row", "is target identity retained?"),
            ("oligo_id", "string", "row", "is oligo identity retained?"),
            ("sequence", "DNA string", "row", "does sequence pass alphabet checks?"),
            ("strand", "string", "row", "is strand explicit or unspecified?"),
            ("start_offset", "integer", "row", "is offset non-negative?"),
            ("pam", "string", "row", "is PAM retained without inference?"),
            ("quarantined", "sequence[object]", "output", "can malformed rows be repaired?"),
        ), ("Was identity preserved?", "Was context checked?", "Were malformed rows quarantined?", "Is adaptation separated from activity?")),
        _reference(PlanningOperation.CONTROLS_RANDOMIZATION, "seeded controls and replicate planning", (
            ("plan_id", "string", "input", "can the plan be named?"),
            ("context_key", "exact context", "input", "does the plan match the context?"),
            ("randomization_seed", "string", "input", "can assignments be replayed?"),
            ("control_types", "sequence[string]", "input", "are control classes explicit?"),
            ("biological_replicates", "positive integer", "input", "is biological repetition explicit?"),
            ("technical_replicates", "positive integer", "input", "is technical repetition explicit?"),
            ("target_id", "string", "target", "is every target stable?"),
            ("condition", "string", "target", "is condition retained?"),
            ("assignment_id", "content address", "output", "is assignment identity stable?"),
            ("randomization_key", "content address", "output", "is sort order deterministic?"),
            ("assignment_count", "integer", "output", "is the plan size visible?"),
            ("target_ids", "sequence[string]", "output", "is target closure visible?"),
        ), ("Was the seed explicit?", "Are control dimensions separated?", "Are foreign targets held?", "Is determinism separated from balance?")),
        _reference(PlanningOperation.POWER_REPLICATION, "transparent effect-noise replication planning", (
            ("request_id", "string", "input", "can the request be named?"),
            ("context_key", "exact context", "input", "does the observation match context?"),
            ("observation_id", "string", "row", "is each observation unique?"),
            ("design_id", "string", "row", "is design identity retained?"),
            ("assay_id", "string", "row", "is assay identity retained?"),
            ("effect_size", "finite number", "row", "is the effect proxy non-zero?"),
            ("variance", "positive number", "row", "is the noise proxy positive?"),
            ("alpha", "fraction", "row", "is alpha bounded?"),
            ("target_power", "fraction", "row", "is target power bounded?"),
            ("planned_replicates", "positive integer", "row", "is planned repetition explicit?"),
            ("blocking_factor_count", "positive integer", "row", "is blocking explicit?"),
            ("required_replicates", "integer", "output", "is the requirement visible?"),
            ("achieved_power", "fraction", "output", "is the proxy visible?"),
            ("replicate_shortfall", "integer", "output", "is shortfall visible?"),
            ("assumptions", "sequence[string]", "output", "are approximation assumptions named?"),
        ), ("Are inputs finite?", "Are assumptions visible?", "Is shortfall held for review?", "Is approximation separated from guarantee?")),
    )


def planning_reference_field_index() -> dict[tuple[str, str], PlanningReferenceField]:
    index: dict[tuple[str, str], PlanningReferenceField] = {}
    for reference in build_planning_operation_references():
        for field in reference.fields:
            index[(reference.operation.value, field.field_name)] = field
    return index


__all__ = ["PlanningOperationReference", "PlanningReferenceField", "build_planning_operation_references", "planning_reference_field_index"]
