"""Operation-owned field dictionary for public planning inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningField:
    field_name: str
    operation: PlanningOperation
    direction: str
    type_name: str
    required: bool
    definition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningDictionary:
    fields: tuple[PlanningField, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_data_dictionary() -> PlanningDictionary:
    rows = (
        ("context_key", PlanningOperation.MODEL_ELIGIBILITY, "input", "string", True, "exact genome, disease, age, state, territory, and treatment context"),
        ("model_system", PlanningOperation.MODEL_ELIGIBILITY, "input", "string", True, "declared model-system family requested by the planner"),
        ("declared_context_keys", PlanningOperation.MODEL_ELIGIBILITY, "input", "sequence[string]", True, "contexts the source explicitly supports"),
        ("evidence_strength", PlanningOperation.MODEL_ELIGIBILITY, "input", "enum", True, "ordinal public evidence strength"),
        ("observations", PlanningOperation.MODEL_ELIGIBILITY, "input", "sequence[object]", True, "model-system observations to gate"),
        ("source_id", PlanningOperation.GUIDE_OLIGO, "input", "string", True, "public source receipt identity"),
        ("source_version", PlanningOperation.GUIDE_OLIGO, "input", "string", True, "source version or portal receipt"),
        ("text", PlanningOperation.GUIDE_OLIGO, "input", "json|csv|tsv", True, "public aggregate guide/oligo rows"),
        ("sequence", PlanningOperation.GUIDE_OLIGO, "input", "DNA string", True, "guide or oligo sequence"),
        ("quarantined", PlanningOperation.GUIDE_OLIGO, "output", "sequence[object]", True, "rows held after adaptation checks"),
        ("plan_id", PlanningOperation.CONTROLS_RANDOMIZATION, "input", "string", True, "stable control-plan identity"),
        ("control_types", PlanningOperation.CONTROLS_RANDOMIZATION, "input", "sequence[string]", True, "declared control classes"),
        ("biological_replicates", PlanningOperation.CONTROLS_RANDOMIZATION, "input", "positive integer", True, "biological repetition count"),
        ("technical_replicates", PlanningOperation.CONTROLS_RANDOMIZATION, "input", "positive integer", True, "technical repetition count"),
        ("randomization_seed", PlanningOperation.CONTROLS_RANDOMIZATION, "input", "string", True, "deterministic assignment seed"),
        ("assignments", PlanningOperation.CONTROLS_RANDOMIZATION, "output", "sequence[object]", True, "content-addressed control assignments"),
        ("effect_size", PlanningOperation.POWER_REPLICATION, "input", "finite number", True, "effect proxy for approximation"),
        ("variance", PlanningOperation.POWER_REPLICATION, "input", "positive finite number", True, "variance proxy for approximation"),
        ("alpha", PlanningOperation.POWER_REPLICATION, "input", "fraction", True, "two-sided error-rate input"),
        ("target_power", PlanningOperation.POWER_REPLICATION, "input", "fraction", True, "desired power input"),
        ("required_replicates", PlanningOperation.POWER_REPLICATION, "output", "positive integer", True, "transparent approximation requirement"),
        ("replicate_shortfall", PlanningOperation.POWER_REPLICATION, "output", "non-negative integer", True, "difference between required and planned repetitions"),
    )
    fields = []
    for field_name, operation, direction, type_name, required, definition in rows:
        body = {"field_name": field_name, "operation": operation, "direction": direction, "type_name": type_name, "required": required, "definition": definition}
        fields.append(PlanningField(**body, content_address=content_hash(body, prefix="planning-field")))
    values = tuple(fields)
    return PlanningDictionary(values, content_hash(values, prefix="planning-dictionary"))


__all__ = ["PlanningDictionary", "PlanningField", "build_planning_data_dictionary"]
