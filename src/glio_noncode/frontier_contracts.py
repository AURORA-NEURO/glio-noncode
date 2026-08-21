"""Declarative contracts for every frontier operation.

The capability modules remain responsible for domain validation. This registry
adds a stable outer contract: operation family, required top-level fields,
expected output surface, and the catalog capability covered by a release
operation. It gives the CLI, fixtures, and downstream callers one place to
inspect the public operation inventory without importing implementation
details or guessing required inputs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .frontier_context_alpha import CONTEXT_FRONTIER_OPERATIONS
from .frontier_data_alpha import FRONTIER_OPERATIONS
from .frontier_end_to_end import END_TO_END_OPERATIONS
from .frontier_inference_alpha import INFERENCE_FRONTIER_OPERATIONS
from .frontier_release_hardening import HARDENING_OPERATIONS
from .serialization import content_hash, jsonable, require_non_empty


class OperationFamily(StrEnum):
    """Execution surface that owns a frontier operation."""

    DATA = "data"
    CONTEXT = "context"
    INFERENCE = "inference"
    RELEASE = "release"
    HARDENING = "hardening"
    END_TO_END = "end_to_end"


@dataclass(frozen=True, slots=True)
class OperationContract:
    """Public operation input and evidence contract."""

    operation: str
    family: OperationFamily
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    capability_ids: tuple[str, ...] = ()
    stage_id: str | None = None
    research_boundary: str = "deterministic local receipt; external validity remains separate"

    def __post_init__(self) -> None:
        require_non_empty(self.operation, "operation")
        if not self.required_fields:
            raise ValidationError(f"{self.operation} must declare required fields")
        if not self.output_fields:
            raise ValidationError(f"{self.operation} must declare output fields")
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValidationError(f"{self.operation} repeats required fields")
        if len(set(self.capability_ids)) != len(self.capability_ids):
            raise ValidationError(f"{self.operation} repeats capability IDs")

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        """Check the outer payload shape while leaving domain checks to handlers."""

        if not isinstance(payload, Mapping):
            raise ValidationError(f"{self.operation} payload must be an object")
        missing = tuple(field for field in self.required_fields if field not in payload)
        if missing:
            raise ValidationError(
                f"{self.operation} payload is missing required fields: {', '.join(missing)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FrontierContractRegistry:
    """Index and inspect all declared frontier operation contracts."""

    def __init__(self, contracts: Sequence[OperationContract]) -> None:
        ordered = tuple(contracts)
        operations = [contract.operation for contract in ordered]
        if len(set(operations)) != len(operations):
            raise ValidationError("frontier operation names must be unique")
        self._contracts = ordered
        self._by_operation = {contract.operation: contract for contract in ordered}

    def contracts(self) -> tuple[OperationContract, ...]:
        return self._contracts

    def get(self, operation: str) -> OperationContract:
        operation = require_non_empty(operation, "operation")
        try:
            return self._by_operation[operation]
        except KeyError as exc:
            raise ValidationError(f"unknown frontier operation: {operation}") from exc

    def validate_payload(self, operation: str, payload: Mapping[str, Any]) -> None:
        self.get(operation).validate_payload(payload)

    def by_family(self, family: OperationFamily) -> tuple[OperationContract, ...]:
        return tuple(contract for contract in self._contracts if contract.family == family)

    def by_capability(self, capability_id: str) -> tuple[OperationContract, ...]:
        capability_id = require_non_empty(capability_id, "capability_id")
        return tuple(
            contract for contract in self._contracts if capability_id in contract.capability_ids
        )

    def capability_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    capability_id
                    for contract in self._contracts
                    for capability_id in contract.capability_ids
                }
            )
        )

    def manifest(self) -> dict[str, Any]:
        payload = {
            "contract_version": "frontier-contracts-v1",
            "contracts": self._contracts,
        }
        return {
            "contract_version": payload["contract_version"],
            "contract_count": len(self._contracts),
            "family_counts": {
                family.value: len(self.by_family(family)) for family in OperationFamily
            },
            "capability_ids": self.capability_ids(),
            "contracts": [contract.to_dict() for contract in self._contracts],
            "manifest_address": content_hash(payload),
        }


def _contract(
    operation: str,
    family: OperationFamily,
    required_fields: Iterable[str],
    output_fields: Iterable[str],
    *,
    capability_id: str | None = None,
    stage_id: str | None = None,
) -> OperationContract:
    return OperationContract(
        operation,
        family,
        tuple(required_fields),
        tuple(output_fields),
        (capability_id,) if capability_id else (),
        stage_id,
    )


def default_frontier_contract_registry() -> FrontierContractRegistry:
    """Build the checked-in operation inventory."""

    contracts: list[OperationContract] = []
    for operation in FRONTIER_OPERATIONS:
        contracts.append(
            _contract(
                operation,
                OperationFamily.DATA,
                ("records", "context_key"),
                ("state", "content_address"),
            )
        )
    for operation in CONTEXT_FRONTIER_OPERATIONS:
        contracts.append(
            _contract(
                operation,
                OperationFamily.CONTEXT,
                ("records", "context_key"),
                ("state", "content_address"),
            )
        )
    for operation in INFERENCE_FRONTIER_OPERATIONS:
        contracts.append(
            _contract(
                operation,
                OperationFamily.INFERENCE,
                ("records", "context_key"),
                ("state", "content_address"),
            )
        )
    contracts.extend(
        (
            _contract(
                "estimate-off-target-risk",
                OperationFamily.RELEASE,
                ("records", "context_key"),
                ("results", "content_address"),
                capability_id="GNC-D13-C13",
                stage_id="off_target_risk",
            ),
            _contract(
                "optimize-validation-voi",
                OperationFamily.RELEASE,
                ("records", "plan_id", "budget", "context_key"),
                ("selected_ids", "content_address"),
                capability_id="GNC-D13-C14",
                stage_id="value_of_information",
            ),
            _contract(
                "export-experiment-package",
                OperationFamily.RELEASE,
                ("experiments", "package_id", "context_key"),
                ("files", "manifest_address"),
                capability_id="GNC-D13-C15",
                stage_id="experiment_package",
            ),
            _contract(
                "ingest-result-update-claims",
                OperationFamily.RELEASE,
                ("claims", "results", "context_key"),
                ("updates", "content_address"),
                capability_id="GNC-D13-C16",
                stage_id="claim_update",
            ),
            _contract(
                "reclassify-evidence",
                OperationFamily.RELEASE,
                ("records", "context_key"),
                ("decisions", "content_address"),
                capability_id="GNC-D14-C13",
                stage_id="reclassification",
            ),
            _contract(
                "manage-deprecation-supersession",
                OperationFamily.RELEASE,
                ("records", "context_key"),
                ("decisions", "content_address"),
                capability_id="GNC-D14-C14",
                stage_id="supersession",
            ),
            _contract(
                "build-audit-reproducibility-bundle",
                OperationFamily.RELEASE,
                ("sections", "bundle_id", "context_key"),
                ("section_addresses", "manifest_address"),
                capability_id="GNC-D14-C15",
                stage_id="audit_bundle",
            ),
            _contract(
                "publish-signed-dossier",
                OperationFamily.RELEASE,
                ("payload", "dossier_id", "key_id", "signing_secret", "context_key"),
                ("payload_address", "dossier_address"),
                capability_id="GNC-D14-C16",
                stage_id="signed_dossier",
            ),
            _contract(
                "verify-signed-dossier",
                OperationFamily.RELEASE,
                ("dossier", "signing_secret", "context_key"),
                ("valid_signature", "state"),
                capability_id="GNC-D14-C16",
                stage_id="signed_dossier",
            ),
            _contract(
                "evaluate-structured-review",
                OperationFamily.RELEASE,
                ("schema", "response", "form_id", "reviewer_id", "context_key"),
                ("fields", "content_address"),
                capability_id="GNC-D15-C13",
                stage_id="structured_review",
            ),
            _contract(
                "build-export-report",
                OperationFamily.RELEASE,
                ("sections", "report_id", "context_key"),
                ("sections", "report_address"),
                capability_id="GNC-D15-C14",
                stage_id="report_export",
            ),
            _contract(
                "search-command-palette",
                OperationFamily.RELEASE,
                ("records", "query", "context_key"),
                ("results", "content_address"),
                capability_id="GNC-D15-C15",
                stage_id="search_palette",
            ),
            _contract(
                "evaluate-accessibility-human-factors",
                OperationFamily.RELEASE,
                ("surface", "surface_id"),
                ("findings", "content_address"),
                capability_id="GNC-D15-C16",
                stage_id="accessibility",
            ),
            _contract(
                "evaluate-privacy-security-policy",
                OperationFamily.RELEASE,
                ("requests", "policies", "context_key"),
                ("decisions", "content_address"),
                capability_id="GNC-D16-C13",
                stage_id="security_policy",
            ),
            _contract(
                "build-local-deployment-bundle",
                OperationFamily.RELEASE,
                ("artifacts", "services", "bundle_id", "platform", "runtime_version"),
                ("artifacts", "manifest_address"),
                capability_id="GNC-D16-C14",
                stage_id="deployment_bundle",
            ),
            _contract(
                "coordinate-federated-execution",
                OperationFamily.RELEASE,
                ("tasks", "sites", "plan_id", "privacy_budget", "context_key"),
                ("assignments", "aggregate_address"),
                capability_id="GNC-D16-C15",
                stage_id="federated_execution",
            ),
            _contract(
                "decide-release-rollback",
                OperationFamily.RELEASE,
                ("release_id", "current_version", "requested_version", "checks"),
                ("failed_checks", "content_address"),
                capability_id="GNC-D16-C16",
                stage_id="release_rollback",
            ),
        )
    )
    for operation in HARDENING_OPERATIONS:
        contracts.append(
            _contract(
                operation,
                OperationFamily.HARDENING,
                ("context_key",),
                ("state", "content_address"),
            )
        )
    for operation in END_TO_END_OPERATIONS:
        contracts.append(
            _contract(
                operation,
                OperationFamily.END_TO_END,
                ("context_key", "pipeline_id"),
                ("stages", "content_address"),
            )
        )
    return FrontierContractRegistry(contracts)


__all__ = [
    "FrontierContractRegistry",
    "OperationContract",
    "OperationFamily",
    "default_frontier_contract_registry",
]
