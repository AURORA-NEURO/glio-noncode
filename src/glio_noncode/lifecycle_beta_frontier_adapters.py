"""Adapter registry for the eight Domain 14 beta-frontier operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import (
    LifecycleBetaFrontierExecution,
    LifecycleBetaFrontierOperation,
    LifecycleBetaFrontierRecord,
    LifecycleBetaFrontierState,
)
from .lifecycle_beta_frontier_fixture_eval import execute_lifecycle_beta_frontier_record
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAdapterSpec:
    operation: LifecycleBetaFrontierOperation
    capability_ids: tuple[str, ...]
    input_contract: str
    output_contract: str
    deterministic: bool
    mutation_scope: str
    source_requirement: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAdapterResult:
    record_id: str
    adapter_operation: LifecycleBetaFrontierOperation
    execution: LifecycleBetaFrontierExecution
    adapter_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAdapterRegistry:
    specs: tuple[LifecycleBetaFrontierAdapterSpec, ...]
    content_address: str

    def spec(self, operation: LifecycleBetaFrontierOperation | str) -> LifecycleBetaFrontierAdapterSpec:
        selected = operation if isinstance(operation, LifecycleBetaFrontierOperation) else LifecycleBetaFrontierOperation(str(operation))
        return next(item for item in self.specs if item.operation is selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_adapters() -> LifecycleBetaFrontierAdapterRegistry:
    rows = (
        (LifecycleBetaFrontierOperation.TIER_ADJUDICATION, ("GNC-D14-C05",), "tier_observations", "tier_adjudication", "immutable_observation", "tier receipts"),
        (LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE, ("GNC-D14-C06",), "claim_graph", "lineage_view", "view_only", "claim and citation receipts"),
        (LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER, ("GNC-D14-C07",), "uncertainty_entries", "uncertainty_ledger", "immutable_observation", "dimension receipts"),
        (LifecycleBetaFrontierOperation.REVIEW_ROUTING, ("GNC-D14-C08",), "claim_graph_and_signals", "review_assignments", "queue_only", "graph and staffing receipts"),
        (LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION, ("GNC-D14-C09",), "masked_cases_and_decisions", "adjudication_result", "append_review_only", "masked evidence receipts"),
        (LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG, ("GNC-D14-C10",), "comments_and_changes", "append_only_log", "append_review_only", "review receipt"),
        (LifecycleBetaFrontierOperation.RELEASE_DECISION, ("GNC-D14-C11",), "graph_and_release_gates", "research_release_record", "record_only", "gate receipts"),
        (LifecycleBetaFrontierOperation.EVIDENCE_DELTA, ("GNC-D14-C12",), "before_after_graphs", "delta_report", "compare_only", "snapshot receipts"),
    )
    specs = []
    for operation, capabilities, input_contract, output_contract, mutation_scope, source_requirement in rows:
        body = {
            "operation": operation,
            "capability_ids": capabilities,
            "input_contract": input_contract,
            "output_contract": output_contract,
            "deterministic": True,
            "mutation_scope": mutation_scope,
            "source_requirement": source_requirement,
        }
        specs.append(LifecycleBetaFrontierAdapterSpec(**body, content_address=content_hash(body)))
    body = {"specs": tuple(specs)}
    return LifecycleBetaFrontierAdapterRegistry(tuple(specs), content_hash(body))


def execute_lifecycle_beta_frontier_record_with_adapter(record: LifecycleBetaFrontierRecord, registry: LifecycleBetaFrontierAdapterRegistry | None = None) -> LifecycleBetaFrontierAdapterResult:
    registry = registry or build_lifecycle_beta_frontier_adapters()
    spec = registry.spec(record.operation)
    execution = execute_lifecycle_beta_frontier_record(record)
    address = content_hash({"spec": spec.content_address, "execution": execution.content_address})
    return LifecycleBetaFrontierAdapterResult(record.record_id, spec.operation, execution, address)


__all__ = [
    "LifecycleBetaFrontierAdapterRegistry",
    "LifecycleBetaFrontierAdapterResult",
    "LifecycleBetaFrontierAdapterSpec",
    "build_lifecycle_beta_frontier_adapters",
    "execute_lifecycle_beta_frontier_record_with_adapter",
]
