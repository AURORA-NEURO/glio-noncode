"""Input and output schema receipts for evidence-release transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evidence_release_frontier_contracts import EvidenceReleaseOperation
from .evidence_release_frontier_support import mapping, sequence
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseSchema:
    version: str
    required_fields: Mapping[str, tuple[str, ...]]
    output_fields: Mapping[str, tuple[str, ...]]
    nested_fields: Mapping[str, tuple[str, ...]]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_release_frontier_schema() -> EvidenceReleaseSchema:
    required = {
        EvidenceReleaseOperation.RECLASSIFICATION.value: ("evidence_id", "context_key", "previous_tier", "proposed_tier", "evidence_score", "reviewer_ids", "source_ids"),
        EvidenceReleaseOperation.SUPERSESSION.value: ("context_key", "records"),
        EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE.value: ("bundle_id", "context_key", "sections"),
        EvidenceReleaseOperation.SIGNED_DOSSIER.value: ("dossier_id", "context_key", "audience", "expires_at", "payload"),
    }
    output = {operation.value: ("operation", "state", "issue_codes", "content_address") for operation in EvidenceReleaseOperation}
    nested = {EvidenceReleaseOperation.SUPERSESSION.value: ("record_id", "status"), EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE.value: ("section_id", "kind", "items")}
    body = {"version": "evidence-release-schema-v1", "required_fields": required, "output_fields": output, "nested_fields": nested}
    return EvidenceReleaseSchema(**body, content_address=content_hash(body))


def validate_evidence_release_schema(payload: Mapping[str, Any], operation: EvidenceReleaseOperation, schema: EvidenceReleaseSchema | None = None) -> tuple[str, ...]:
    schema = schema or default_evidence_release_frontier_schema()
    errors = [f"missing:{field}" for field in schema.required_fields[operation.value] if field not in payload]
    try:
        if "context_key" in payload and not isinstance(payload.get("context_key"), str):
            errors.append("context_key:not_text")
        if operation == EvidenceReleaseOperation.SUPERSESSION and "records" in payload:
            sequence(payload["records"], "records")
        if operation == EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE and "sections" in payload:
            sequence(payload["sections"], "sections")
        if operation == EvidenceReleaseOperation.SIGNED_DOSSIER and "payload" in payload:
            mapping(payload["payload"], "payload")
    except ValueError as exc:
        errors.append(f"shape:{exc}")
    return tuple(errors)


__all__ = ["EvidenceReleaseSchema", "default_evidence_release_frontier_schema", "validate_evidence_release_schema"]
