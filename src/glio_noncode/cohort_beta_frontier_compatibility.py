"""Compatibility checks for serialized release projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_beta_frontier_schema import CohortBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierCompatibilityReport:
    schema_version: str
    required_fields: tuple[str, ...]
    observed_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_beta_frontier_compatibility(schema: CohortBetaFrontierSchemaReport, payload: Mapping[str, Any], operation: str) -> CohortBetaFrontierCompatibilityReport:
    required = schema.required_for(operation)
    observed = tuple(sorted(payload))
    missing = tuple(field for field in required if field not in payload)
    return CohortBetaFrontierCompatibilityReport(schema.version, required, observed, missing, not missing, content_hash({"operation": operation, "required": required, "observed": observed, "missing": missing}, prefix="compatibility"))


__all__ = ["CohortBetaFrontierCompatibilityReport", "evaluate_cohort_beta_frontier_compatibility"]
