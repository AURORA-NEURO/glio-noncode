"""JSON-shaped schema view for the runtime report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_schema import CohortAlphaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierJsonSchemaView:
    schema_id: str
    version: str
    required_keys: tuple[str, ...]
    state_values: tuple[str, ...]
    additional_properties: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_json_schema_view(schema: CohortAlphaFrontierSchemaReport) -> CohortAlphaFrontierJsonSchemaView:
    required = tuple(sorted({field.name for field in schema.fields if field.required}))
    states = ("supported", "partial", "ambiguous", "out_of_domain", "abstained")
    body = {"schema_id": schema.schema_id, "version": schema.version, "required_keys": required, "states": states, "additional_properties": False}
    return CohortAlphaFrontierJsonSchemaView(schema.schema_id, schema.version, required, states, False, content_hash(body, prefix="alpha-json-schema"))


__all__ = ["CohortAlphaFrontierJsonSchemaView", "build_cohort_alpha_frontier_json_schema_view"]
