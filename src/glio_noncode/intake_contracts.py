"""Declarative operation contracts for Domain 01 intake capabilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .intake_public_data import IntakeRecordKind
from .serialization import content_hash, jsonable, require_non_empty


class IntakeContractFamily(StrEnum):
    """Stable contract families for C13 through C16."""

    POLICY = "policy"
    QUARANTINE = "quarantine"
    COMPLETENESS = "completeness"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class IntakeOperationContract:
    """Required payload, output receipt, states, and external boundary."""

    capability_id: str
    family: IntakeContractFamily
    kind: IntakeRecordKind
    operation: str
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    review_states: tuple[str, ...]
    evidence_role: str
    external_boundary: str

    def __post_init__(self) -> None:
        for name in (
            "capability_id",
            "operation",
            "evidence_role",
            "external_boundary",
        ):
            require_non_empty(getattr(self, name), name)
        if len(self.required_fields) != len(set(self.required_fields)):
            raise ValidationError("intake contract required fields must be unique")
        if len(self.output_fields) != len(set(self.output_fields)):
            raise ValidationError("intake contract output fields must be unique")
        if not self.accepted_states:
            raise ValidationError("intake contract must declare accepted states")
        if not self.review_states:
            raise ValidationError("intake contract must declare review states")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("intake accepted and review states must be disjoint")

    def accepts_state(self, state: str) -> bool:
        return state in self.accepted_states or state in self.review_states

    def missing_fields(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(field for field in self.required_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class IntakeContractRegistry:
    """Index and validate all four intake contracts."""

    def __init__(self, contracts: Sequence[IntakeOperationContract]) -> None:
        self._contracts = tuple(contracts)
        if len({contract.capability_id for contract in self._contracts}) != len(self._contracts):
            raise ValidationError("intake contract capability IDs must be unique")
        if len({contract.kind for contract in self._contracts}) != len(self._contracts):
            raise ValidationError("intake contract kinds must be unique")
        if len({contract.operation for contract in self._contracts}) != len(self._contracts):
            raise ValidationError("intake contract operations must be unique")

    @property
    def contracts(self) -> tuple[IntakeOperationContract, ...]:
        return self._contracts

    def contract_for_kind(self, kind: IntakeRecordKind | str) -> IntakeOperationContract:
        kind_value = IntakeRecordKind(str(kind))
        for contract in self._contracts:
            if contract.kind == kind_value:
                return contract
        raise ValidationError(f"no intake contract for kind {kind_value.value}")

    def contract_for_operation(self, operation: str) -> IntakeOperationContract:
        require_non_empty(operation, "intake operation")
        for contract in self._contracts:
            if contract.operation == operation:
                return contract
        raise ValidationError(f"no intake contract for operation {operation}")

    def validate_record(
        self,
        kind: IntakeRecordKind | str,
        payload: Mapping[str, Any],
    ) -> tuple[str, ...]:
        return self.contract_for_kind(kind).missing_fields(payload)

    def manifest(self) -> dict[str, Any]:
        body = {
            "contract_version": "intake-contracts-v1",
            "contract_count": len(self._contracts),
            "capability_ids": tuple(contract.capability_id for contract in self._contracts),
            "contracts": self._contracts,
        }
        result = jsonable(body)
        result["content_address"] = content_hash(body)
        return result


def default_intake_contract_registry() -> IntakeContractRegistry:
    """Return the checked-in contracts for C13-C16."""

    return IntakeContractRegistry(
        (
            IntakeOperationContract(
                "GNC-D01-C13",
                IntakeContractFamily.POLICY,
                IntakeRecordKind.CONSENT,
                "attach-consent-policy",
                (
                    "records",
                    "policy_id",
                    "policy_version",
                    "purpose",
                    "permitted_uses",
                ),
                (
                    "attachments",
                    "accepted_record_ids",
                    "blocked_record_ids",
                    "issues",
                    "content_address",
                ),
                ("accepted",),
                ("blocked", "review"),
                "bind declared policy scope and active status to each intake record",
                "Institutional consent adjudication and legal interpretation remain external",
            ),
            IntakeOperationContract(
                "GNC-D01-C14",
                IntakeContractFamily.QUARANTINE,
                IntakeRecordKind.ANOMALY,
                "quarantine-input-anomalies",
                ("records", "allowed_bases"),
                (
                    "observations",
                    "accepted_record_ids",
                    "quarantined_record_ids",
                    "issues",
                    "content_address",
                ),
                ("accepted",),
                ("quarantined", "review"),
                "retain malformed rows and expose stable anomaly codes without deletion",
                "Biological quality interpretation and source correction remain external",
            ),
            IntakeOperationContract(
                "GNC-D01-C15",
                IntakeContractFamily.COMPLETENESS,
                IntakeRecordKind.COMPLETENESS,
                "score-data-completeness",
                ("records", "required_fields", "weights", "minimum_score"),
                (
                    "scores",
                    "mean_score",
                    "accepted_record_ids",
                    "review_record_ids",
                    "content_address",
                ),
                ("accepted",),
                ("review",),
                "make weighted field coverage and missingness auditable",
                "Field semantics, assay validity, and scientific sufficiency remain external",
            ),
            IntakeOperationContract(
                "GNC-D01-C16",
                IntakeContractFamily.EXPORT,
                IntakeRecordKind.BUNDLE,
                "export-intake-bundle",
                ("records", "bundle_id", "source_ids", "require_accepted"),
                (
                    "bundle_id",
                    "context_key",
                    "source_ids",
                    "record_count",
                    "manifest",
                    "content_address",
                    "state",
                ),
                ("published",),
                ("review",),
                "publish deterministic context-bound intake manifests only after gates pass",
                "Downstream storage, publication approval, and clinical use remain external",
            ),
        )
    )


__all__ = [
    "IntakeContractFamily",
    "IntakeContractRegistry",
    "IntakeOperationContract",
    "default_intake_contract_registry",
]
