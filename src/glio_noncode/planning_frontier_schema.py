"""Schema manifests and payload diagnostics for D13 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .planning_frontier_adapters import build_planning_adapters
from .planning_frontier_contracts import PlanningOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningSchema:
    operation: PlanningOperation
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    research_only: bool
    content_address: str

    def missing(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(field for field in self.required_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningSchemaRegistry:
    schemas: tuple[PlanningSchema, ...]
    content_address: str

    def for_operation(self, operation: PlanningOperation | str) -> PlanningSchema:
        selected = operation if isinstance(operation, PlanningOperation) else PlanningOperation(str(operation))
        return next(item for item in self.schemas if item.operation is selected)

    def to_dict(self) -> dict[str, Any]:
        return {"schemas": tuple(item.to_dict() for item in self.schemas), "content_address": self.content_address}


def _schema(operation: PlanningOperation, required: tuple[str, ...], optional: tuple[str, ...], outputs: tuple[str, ...], issues: tuple[str, ...]) -> PlanningSchema:
    body = {"operation": operation, "required_fields": required, "optional_fields": optional, "output_fields": outputs, "issue_codes": issues, "research_only": True}
    return PlanningSchema(**body, content_address=content_hash(body, prefix="planning-schema"))


def default_planning_schema() -> PlanningSchemaRegistry:
    schemas = (
        _schema(PlanningOperation.MODEL_ELIGIBILITY, ("request_id", "context_key", "model_system", "observations", "minimum_evidence_strength"), ("controls", "readouts"), ("state", "results", "eligible_count", "issue_codes"), ("context_mismatch", "context_not_declared_supported", "evidence_below_threshold", "no_model_observations")),
        _schema(PlanningOperation.GUIDE_OLIGO, ("source_id", "source_version", "input_format", "text"), ("context_key",), ("state", "observations", "quarantined", "issue_codes"), ("invalid_guide_oligo_row", "context_mismatch", "empty_source")),
        _schema(PlanningOperation.CONTROLS_RANDOMIZATION, ("plan_id", "context_key", "targets", "control_types", "biological_replicates", "technical_replicates", "randomization_seed"), (), ("state", "assignments", "target_ids", "issue_codes"), ("context_mismatch", "missing_target_id", "no_targets")),
        _schema(PlanningOperation.POWER_REPLICATION, ("request_id", "context_key", "observations"), (), ("state", "results", "required_replicates", "issue_codes"), ("context_mismatch", "invalid_power_row", "no_power_observations")),
    )
    return PlanningSchemaRegistry(schemas, content_hash(schemas, prefix="planning-schema-registry"))


def validate_planning_payload(operation: PlanningOperation | str, payload: Mapping[str, Any]) -> dict[str, Any]:
    schema = default_planning_schema().for_operation(operation)
    missing = schema.missing(payload) if isinstance(payload, Mapping) else ("payload_not_an_object",)
    body = {"operation": schema.operation, "valid": not missing, "missing_fields": missing, "schema_address": schema.content_address}
    return body | {"content_address": content_hash(body, prefix="planning-schema-check")}


__all__ = ["PlanningSchema", "PlanningSchemaRegistry", "default_planning_schema", "validate_planning_payload"]
