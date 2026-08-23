"""Projection of operation schemas into consumer-facing field groups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_schema import CohortAlphaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSchemaProjection:
    operation: str
    identity_fields: tuple[str, ...]
    measurement_fields: tuple[str, ...]
    boundary_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSchemaProjectionReport:
    projections: tuple[CohortAlphaFrontierSchemaProjection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_schema_projection(schema: CohortAlphaFrontierSchemaReport) -> CohortAlphaFrontierSchemaProjectionReport:
    projections = []
    for operation in ("C09", "C10", "C11", "C12"):
        fields = tuple(item for item in schema.fields if item.operation == operation)
        identity = tuple(item.name for item in fields if "identity" in item.role or item.name.endswith("_id"))
        measurement = tuple(item.name for item in fields if "measure" in item.role or "frequency" in item.name or item.name in {"effect", "support", "sample_count"})
        boundary = tuple(item.name for item in fields if item.null_policy != "reject" or item.name in {"phase", "selection_phase", "context_key", "cohort_id"})
        accepted = bool(identity) and bool(measurement) and bool(boundary)
        projections.append(CohortAlphaFrontierSchemaProjection(operation, identity, measurement, boundary, accepted, content_hash({"operation": operation, "identity": identity, "measurement": measurement, "boundary": boundary}, prefix="alpha-schema-projection")))
    values = tuple(projections)
    return CohortAlphaFrontierSchemaProjectionReport(values, schema.accepted and all(item.accepted for item in values), content_hash(values, prefix="alpha-schema-projections"))


__all__ = ["CohortAlphaFrontierSchemaProjection", "CohortAlphaFrontierSchemaProjectionReport", "build_cohort_alpha_frontier_schema_projection"]
