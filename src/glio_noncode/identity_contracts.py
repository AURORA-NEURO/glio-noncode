"""Operation contracts for the Domain 01 identity evidence stack."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity_public_data import IdentityRecordKind
from .serialization import content_hash, jsonable, require_non_empty


class IdentityContractFamily(StrEnum):
    """Stable contract families for the four identity operations."""

    EQUIVALENCE = "equivalence"
    RECONCILIATION = "reconciliation"
    SAMPLE = "sample"
    CUSTODY = "custody"


@dataclass(frozen=True, slots=True)
class IdentityOperationContract:
    """Required inputs, outputs, states, and evidence role for one operation."""

    capability_id: str
    family: IdentityContractFamily
    kind: IdentityRecordKind
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
            raise ValidationError("identity contract required fields must be unique")
        if len(self.output_fields) != len(set(self.output_fields)):
            raise ValidationError("identity contract output fields must be unique")
        if not self.accepted_states:
            raise ValidationError("identity contract must declare accepted states")
        if not self.review_states:
            raise ValidationError("identity contract must declare review states")

    def accepts_state(self, state: str) -> bool:
        return state in self.accepted_states or state in self.review_states

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class IdentityContractRegistry:
    """Index and validate the four public identity operation contracts."""

    def __init__(self, contracts: Sequence[IdentityOperationContract]) -> None:
        self._contracts = tuple(contracts)
        if len({contract.capability_id for contract in self._contracts}) != len(self._contracts):
            raise ValidationError("identity contract capability IDs must be unique")
        if len({contract.kind for contract in self._contracts}) != len(self._contracts):
            raise ValidationError("identity contract kinds must be unique")

    @property
    def contracts(self) -> tuple[IdentityOperationContract, ...]:
        return self._contracts

    def contract_for_kind(self, kind: IdentityRecordKind | str) -> IdentityOperationContract:
        kind_value = IdentityRecordKind(str(kind))
        for contract in self._contracts:
            if contract.kind == kind_value:
                return contract
        raise ValidationError(f"no identity contract for kind {kind_value.value}")

    def contract_for_operation(self, operation: str) -> IdentityOperationContract:
        require_non_empty(operation, "identity operation")
        for contract in self._contracts:
            if contract.operation == operation:
                return contract
        raise ValidationError(f"no identity contract for operation {operation}")

    def validate_record(
        self,
        kind: IdentityRecordKind | str,
        payload: Mapping[str, Any],
    ) -> tuple[str, ...]:
        contract = self.contract_for_kind(kind)
        missing = tuple(field for field in contract.required_fields if field not in payload)
        return missing

    def manifest(self) -> dict[str, Any]:
        body = {
            "contract_version": "identity-contracts-v1",
            "contract_count": len(self._contracts),
            "contracts": self._contracts,
        }
        result = jsonable(body)
        result["content_address"] = content_hash(body)
        return result


def default_identity_contract_registry() -> IdentityContractRegistry:
    """Return the checked-in contracts for C09 through C12."""

    return IdentityContractRegistry(
        (
            IdentityOperationContract(
                "GNC-D01-C09",
                IdentityContractFamily.EQUIVALENCE,
                IdentityRecordKind.EQUIVALENCE,
                "resolve-variant-equivalence",
                ("records", "query"),
                (
                    "state",
                    "equivalence_key",
                    "record_ids",
                    "variant_ids",
                    "source_ids",
                    "methods",
                    "competing_keys",
                    "content_address",
                ),
                ("supported",),
                ("ambiguous", "absent", "out_of_domain", "abstained"),
                "resolve declared normalized identity without rewriting source records",
                "RefGet-backed equivalence and broad structural identity remain external gates",
            ),
            IdentityOperationContract(
                "GNC-D01-C10",
                IdentityContractFamily.RECONCILIATION,
                IdentityRecordKind.RECONCILIATION,
                "reconcile-variant-aliases",
                ("records",),
                (
                    "state",
                    "groups",
                    "duplicate_record_ids",
                    "ambiguous_aliases",
                    "ungrouped_record_ids",
                    "content_address",
                ),
                ("supported",),
                ("partial", "ambiguous", "abstained"),
                "retain all duplicate and alias evidence without selecting a winner",
                (
                    "Source stewardship, specimen identity, and institutional adjudication "
                    "remain external"
                ),
            ),
            IdentityOperationContract(
                "GNC-D01-C11",
                IdentityContractFamily.SAMPLE,
                IdentityRecordKind.SAMPLE,
                "check-batch-sample-identity",
                ("observations",),
                (
                    "state",
                    "observations",
                    "batch_to_samples",
                    "sample_to_subjects",
                    "issues",
                    "missing_observation_ids",
                    "source_ids",
                    "content_address",
                ),
                ("supported",),
                ("partial", "contradictory", "abstained"),
                "check declared metadata completeness and cross-record mapping conflicts",
                "Biological authentication, consent, and specimen identity remain external",
            ),
            IdentityOperationContract(
                "GNC-D01-C12",
                IdentityContractFamily.CUSTODY,
                IdentityRecordKind.CUSTODY,
                "capture-chain-of-custody",
                ("events",),
                (
                    "state",
                    "chains",
                    "issues",
                    "event_count",
                    "artifact_count",
                    "content_address",
                ),
                ("supported",),
                ("contradictory", "abstained"),
                "preserve declared artifact transitions, hashes, and broken links",
                "Digital signatures and institutional custody attestation remain external",
            ),
        )
    )


__all__ = [
    "IdentityContractFamily",
    "IdentityContractRegistry",
    "IdentityOperationContract",
    "default_identity_contract_registry",
]
