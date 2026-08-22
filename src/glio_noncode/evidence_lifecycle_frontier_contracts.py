"""Operation contracts for the Domain 14 evidence lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleContract:
    operation: EvidenceLifecycleOperation
    required_inputs: tuple[str, ...]
    required_outputs: tuple[str, ...]
    issue_codes: tuple[str, ...]
    state_values: tuple[str, ...]
    review_boundary: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.review_boundary, "review_boundary")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleContractRegistry:
    registry_id: str
    version: str
    contracts: tuple[EvidenceLifecycleContract, ...]
    content_address: str

    def by_operation(self, operation: EvidenceLifecycleOperation) -> EvidenceLifecycleContract:
        return next(item for item in self.contracts if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.contracts for code in item.issue_codes}))

    def manifest(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "contracts": [item.to_dict() for item in self.contracts], "issue_codes": list(self.issue_codes()), "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_lifecycle_contracts() -> EvidenceLifecycleContractRegistry:
    common = ("record_id", "context_key", "source_ids", "payload")
    rows = (
        EvidenceLifecycleContract(EvidenceLifecycleOperation.CITATION_RESOLUTION, common + ("text", "source_id"), ("citations", "issues", "input_hash", "state"), ("invalid_lifecycle_input", "invalid_json", "missing_header", "missing_required_field", "duplicate_citation_id"), ("supported", "partial", "abstained"), "malformed rows remain quarantined", ""),
        EvidenceLifecycleContract(EvidenceLifecycleOperation.GRAPH_CONSTRUCTION, common + ("claims", "citations"), ("claims", "active_claim_ids", "superseded_claim_ids", "orphan_claim_ids", "state"), ("invalid_graph_input", "graph_context_mismatch", "duplicate_claim_id", "orphan_claim", "citation_context_mismatch"), ("supported", "partial", "out_of_domain", "contradictory", "abstained", "superseded", "invalid"), "history remains append-only", ""),
        EvidenceLifecycleContract(EvidenceLifecycleOperation.EDGE_VALIDATION, common + ("claims", "citations", "edge_id"), ("claim_ids", "active_claim_ids", "missing_source_ids", "uncertainty", "state"), ("invalid_lifecycle_input", "missing_source", "edge_context_mismatch", "edge_absent"), ("supported", "partial", "out_of_domain", "contradictory", "abstained", "absent"), "edge checks do not average claims", ""),
        EvidenceLifecycleContract(EvidenceLifecycleOperation.DISAGREEMENT_TRACKING, common + ("claims", "citations", "edge_ids"), ("records", "contradictory_edge_ids", "unresolved_edge_ids"), ("invalid_lifecycle_input", "contradiction_unresolved", "incomplete_disagreement", "disagreement_out_of_domain"), ("clear", "contradictory", "incomplete", "out_of_domain"), "competing observations remain separate", ""),
    )
    addressed = tuple(EvidenceLifecycleContract(item.operation, item.required_inputs, item.required_outputs, item.issue_codes, item.state_values, item.review_boundary, content_hash({"operation": item.operation, "required_inputs": item.required_inputs, "required_outputs": item.required_outputs, "issue_codes": item.issue_codes, "state_values": item.state_values, "review_boundary": item.review_boundary})) for item in rows)
    body = {"registry_id": "evidence-lifecycle-frontier-contracts", "version": "2026.08.d14.v1", "contracts": addressed}
    return EvidenceLifecycleContractRegistry(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleContract", "EvidenceLifecycleContractRegistry", "default_evidence_lifecycle_contracts"]
