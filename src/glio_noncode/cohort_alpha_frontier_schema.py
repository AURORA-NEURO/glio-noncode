"""Field schema and null policy for longitudinal aggregate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierField:
    operation: str
    name: str
    value_type: str
    required: bool
    role: str
    null_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSchemaReport:
    schema_id: str
    version: str
    fields: tuple[CohortAlphaFrontierField, ...]
    accepted: bool
    findings: tuple[str, ...]
    content_address: str

    def required_for(self, operation: str) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.operation == operation and item.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(operation: str, name: str, value_type: str, role: str, required: bool = True, null_policy: str = "reject") -> CohortAlphaFrontierField:
    body = {"operation": operation, "name": name, "value_type": value_type, "required": required, "role": role, "null_policy": null_policy}
    return CohortAlphaFrontierField(**body, content_address=content_hash(body, prefix="alpha-field"))


def default_cohort_alpha_frontier_schema() -> CohortAlphaFrontierSchemaReport:
    fields = (_field("C09", "variant_id", "string", "variant identity"), _field("C09", "sample_id", "string", "pseudonymous sample"), _field("C09", "cancer_cell_fraction", "number in [0,1]", "clonality measure", False, "partial"), _field("C09", "phase", "enum", "specimen phase"), _field("C09", "timepoint", "number", "temporal order", False, "indeterminate"), _field("C10", "locus_id", "string", "locus identity"), _field("C10", "phase", "enum", "primary or recurrence phase"), _field("C10", "frequency", "number in [0,1]", "phase frequency"), _field("C11", "treatment_id", "string", "exposure identity"), _field("C11", "selection_phase", "enum", "pre or post phase"), _field("C11", "frequency", "number in [0,1]", "frequency"), _field("C11", "response_label", "string", "declared response metadata", False, "retain_if_present"), _field("C12", "feature_id", "string", "replication feature"), _field("C12", "cohort_id", "string", "cohort identity"), _field("C12", "effect", "number", "cohort effect"), _field("C12", "support", "number in [0,1]", "bounded support"), _field("C12", "sample_count", "positive integer", "cohort sample floor"))
    findings = ("phase and treatment metadata remain explicit", "missing quantitative channels produce partial states", "no operation emits significance or clinical interpretation")
    body = {"schema_id": "GNC-D12-C09-C12-schema", "version": "1", "fields": fields, "findings": findings}
    return CohortAlphaFrontierSchemaReport(body["schema_id"], body["version"], fields, True, findings, content_hash(body, prefix="alpha-schema"))


def validate_cohort_alpha_frontier_schema(report: CohortAlphaFrontierSchemaReport | None = None) -> bool:
    value = report or default_cohort_alpha_frontier_schema()
    return value.accepted and {item.operation for item in value.fields} == {"C09", "C10", "C11", "C12"} and len(value.fields) >= 16


__all__ = ["CohortAlphaFrontierField", "CohortAlphaFrontierSchemaReport", "default_cohort_alpha_frontier_schema", "validate_cohort_alpha_frontier_schema"]
