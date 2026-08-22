"""Operation contracts for the Domain 13 validation-planning frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_frontier_public_data import ValidationFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationFrontierContract:
    operation: ValidationFrontierOperation
    required_payload_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_vocabulary: tuple[str, ...]
    accepted_states: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not self.required_payload_fields or not self.output_fields:
            raise ValueError("validation frontier contract requires fields")
        if not self.issue_vocabulary:
            raise ValueError("validation frontier contract requires issue vocabulary")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierContractRegistry:
    contracts: tuple[ValidationFrontierContract, ...]
    version: str
    content_address: str

    def __post_init__(self) -> None:
        if {item.operation for item in self.contracts} != set(ValidationFrontierOperation):
            raise ValueError("validation frontier contracts must cover operations")

    def by_operation(self, operation: ValidationFrontierOperation) -> ValidationFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.contracts for code in item.issue_vocabulary}))

    def manifest(self) -> dict[str, Any]:
        return {"version": self.version, "contracts": [item.to_dict() for item in self.contracts], "content_address": self.content_address}


def _contract(operation: ValidationFrontierOperation, required: tuple[str, ...], output: tuple[str, ...], issues: tuple[str, ...], states: tuple[str, ...]) -> ValidationFrontierContract:
    body = {"operation": operation, "required_payload_fields": required, "output_fields": output, "issue_vocabulary": issues, "accepted_states": states}
    return ValidationFrontierContract(**body, content_address=content_hash(body))


def default_validation_frontier_contracts() -> ValidationFrontierContractRegistry:
    common = ("context_key",)
    contracts = (
        _contract(ValidationFrontierOperation.EVIDENCE_GAP, common + ("hypothesis",), ("hypothesis_id", "gaps", "priority_order", "warnings"), ("context_mismatch", "invalid_evidence_gap_input", "complete_hypothesis_control"), ("partial", "ready_for_review", "invalid")),
        _contract(ValidationFrontierOperation.ASSAY_ELIGIBILITY, common + ("constraints", "inventory"), ("routes", "blockers", "alternatives", "sensitivity"), ("model_system_not_available", "missing_controls", "missing_readouts", "assay_not_present_in_inventory", "invalid_assay_eligibility_input"), ("ready_for_review", "blocked", "abstained", "invalid")),
        _contract(ValidationFrontierOperation.MPRA_PLANNING, common + ("constraints", "targets"), ("package_id", "constructs", "controls", "blockers", "limitations"), ("context_mismatch", "insert_length", "max_constructs_exceeded", "no_validation_targets", "invalid_validation_design_input"), ("ready_for_review", "blocked", "abstained", "invalid")),
        _contract(ValidationFrontierOperation.STARR_SEQ_PLANNING, common + ("constraints", "targets"), ("package_id", "constructs", "controls", "blockers", "limitations"), ("context_mismatch", "insert_length", "max_constructs_exceeded", "no_validation_targets", "invalid_validation_design_input"), ("ready_for_review", "blocked", "abstained", "invalid")),
    )
    body = {"version": "2026.08.d13.v1", "contracts": contracts}
    require_non_empty(body["version"], "contract version")
    return ValidationFrontierContractRegistry(contracts=contracts, version=body["version"], content_address=content_hash(body))


__all__ = ["ValidationFrontierContract", "ValidationFrontierContractRegistry", "default_validation_frontier_contracts"]
