"""Field-level schema report for the public aggregate C05-C08 plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierField:
    operation: str
    name: str
    value_type: str
    required: bool
    semantic_role: str
    null_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSchemaReport:
    schema_id: str
    version: str
    fields: tuple[CohortBetaFrontierField, ...]
    accepted: bool
    findings: tuple[str, ...]
    content_address: str

    def required_for(self, operation: str) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields if item.operation == operation and item.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(operation: str, name: str, value_type: str, role: str, *, required: bool = True, null_policy: str = "reject") -> CohortBetaFrontierField:
    body = {"operation": operation, "name": name, "value_type": value_type, "required": required, "semantic_role": role, "null_policy": null_policy}
    return CohortBetaFrontierField(**body, content_address=content_hash(body, prefix="field"))


def default_cohort_beta_frontier_schema() -> CohortBetaFrontierSchemaReport:
    fields = [_field("C05", "record_id", "string", "row identity"), _field("C05", "variant_id", "string", "variant identity"), _field("C05", "sample_id", "string", "pseudonymous sample identity"), _field("C05", "position", "integer", "genomic coordinate"), _field("C05", "callable", "boolean", "callable-space filter", required=False, null_policy="true"), _field("C06", "region_id", "string", "regional key"), _field("C06", "callable_bases", "positive integer", "denominator"), _field("C06", "background_rate", "non-negative number", "descriptive comparator", required=False, null_policy="partial"), _field("C07", "feature_id", "string", "functional feature"), _field("C07", "feature_class", "string", "feature namespace"), _field("C07", "support", "number in [0,1]", "bounded support"), _field("C07", "is_control", "boolean", "comparator membership", required=False, null_policy="false"), _field("C08", "gene_id", "string", "gene membership"), _field("C08", "set_id", "string", "pathway or regulon key"), _field("C08", "set_kind", "enum", "set namespace"), _field("C08", "direction", "enum", "declared direction")]
    findings = ("variant and sample identities are pseudonymous", "context is a required execution key", "optional comparators produce partial rather than inferred significance")
    body = {"schema_id": "GNC-D12-C05-C08-schema", "version": "1", "fields": fields, "findings": findings}
    return CohortBetaFrontierSchemaReport(body["schema_id"], body["version"], tuple(fields), True, findings, content_hash(body, prefix="schema"))


def validate_cohort_beta_frontier_schema(report: CohortBetaFrontierSchemaReport | None = None) -> bool:
    value = report or default_cohort_beta_frontier_schema()
    operations = {item.operation for item in value.fields}
    return value.accepted and operations == {"C05", "C06", "C07", "C08"} and len(value.fields) >= 16


__all__ = ["CohortBetaFrontierField", "CohortBetaFrontierSchemaReport", "default_cohort_beta_frontier_schema", "validate_cohort_beta_frontier_schema"]
