"""Typed operation contracts for the Domain 04 C13-C16 release frontier."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_release_frontier_public_data import ReferenceReleaseOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseContract:
    """Input, output, state, issue, and research boundary for one operation."""

    capability_id: str
    operation: ReferenceReleaseOperation
    title: str
    required_input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    review_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("capability_id", "title", "boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_input_fields or not self.output_fields:
            raise ValidationError("release contract fields must not be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("release input fields must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("release output fields must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("release accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("release contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        """Return missing fields without mutating or normalizing the payload."""

        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceReleaseContractRegistry:
    """Ordered registry with strict capability and operation uniqueness."""

    def __init__(self, contracts: Iterable[ReferenceReleaseContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("release contract registry cannot be empty")
        capability_ids = [contract.capability_id for contract in values]
        operations = [contract.operation for contract in values]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValidationError("duplicate release capability ID")
        if len(set(operations)) != len(operations):
            raise ValidationError("duplicate release operation")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[ReferenceReleaseContract, ...]:
        return self._contracts

    def by_operation(self, operation: ReferenceReleaseOperation | str) -> ReferenceReleaseContract:
        try:
            key = (
                operation
                if isinstance(operation, ReferenceReleaseOperation)
                else ReferenceReleaseOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown release operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> ReferenceReleaseContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown release capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        body = {"contracts": self._contracts}
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash(body),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.manifest()


def _contract(
    capability_id: str,
    operation: ReferenceReleaseOperation,
    title: str,
    required: tuple[str, ...],
    output: tuple[str, ...],
    accepted: tuple[str, ...],
    review: tuple[str, ...],
    issues: tuple[str, ...],
    boundary: str,
) -> ReferenceReleaseContract:
    body = {
        "capability_id": capability_id,
        "operation": operation,
        "title": title,
        "required_input_fields": required,
        "output_fields": output,
        "accepted_states": accepted,
        "review_states": review,
        "issue_codes": issues,
        "boundary": boundary,
    }
    return ReferenceReleaseContract(**body, content_address=content_hash(body))


def default_reference_release_contracts() -> ReferenceReleaseContractRegistry:
    """Return the four C13-C16 contracts in capability order."""

    contracts = (
        _contract(
            "GNC-D04-C13",
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "Source provenance and checksum closure",
            ("records", "context_key"),
            ("check_count", "compatible_ids", "review_ids", "checksum_matches", "issue_codes"),
            ("accepted",),
            ("review", "blocked", "abstained"),
            (
                "missing_source_uri",
                "missing_checksum",
                "missing_license",
                "checksum_unverified",
                "provenance_context_mismatch",
            ),
            (
                "Public source receipts retain URI, checksum, license, context, and review "
                "reasons; "
                "no resource bytes are fetched."
            ),
        ),
        _contract(
            "GNC-D04-C14",
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "Versioned annotation field drift",
            ("previous", "current", "context_key"),
            ("finding_count", "drifted_ids", "stable_ids", "changed_fields", "report_address"),
            ("accepted",),
            ("drift", "blocked", "abstained"),
            (
                "annotation_identity_missing",
                "annotation_context_mismatch",
                "drift_threshold_invalid",
            ),
            (
                "Field changes are descriptive release evidence; they do not select a preferred "
                "annotation or infer biological effect."
            ),
        ),
        _contract(
            "GNC-D04-C15",
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "Reproducible reference bundle assembly",
            ("records", "bundle_id", "context_key", "schema_hash"),
            ("bundle_id", "reference_ids", "record_count", "schema_hash", "bundle_address"),
            ("published",),
            ("blocked", "abstained"),
            (
                "bundle_context_mismatch",
                "bundle_unavailable",
                "bundle_missing_reference_id",
                "bundle_schema_missing",
            ),
            (
                "Only available, exact-context reference metadata enters a sorted "
                "content-addressed bundle."
            ),
        ),
        _contract(
            "GNC-D04-C16",
            ReferenceReleaseOperation.RELEASE_GATE,
            "Reference release integrity gate",
            ("release_id", "context_key", "bundle_address", "checks"),
            ("release_id", "bundle_address", "checks", "failed_checks", "issue_codes"),
            ("published",),
            ("blocked", "abstained"),
            ("release_check_failed", "release_context_missing", "release_bundle_missing"),
            (
                "Checksum, schema, license, context, and source checks gate a research release; "
                "a failed check blocks publication."
            ),
        ),
    )
    return ReferenceReleaseContractRegistry(contracts)


__all__ = [
    "ReferenceReleaseContract",
    "ReferenceReleaseContractRegistry",
    "default_reference_release_contracts",
]
