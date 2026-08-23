"""Executable examples for the four operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_beta_frontier_public_data import C05_C08_CONTEXT
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierContractExample:
    operation: str
    example_id: str
    input_summary: str
    expected_state: str
    required_boundary: str
    prohibited_inference: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_contract_examples() -> tuple[CohortBetaFrontierContractExample, ...]:
    raw = (
        ("C05", "recurrence-positive", "two distinct samples share one callable variant", "supported", "distinct sample IDs and recurrence threshold", "driver conclusion"),
        ("C05", "recurrence-foreign", "row uses a foreign context key", "out_of_domain", "exact context equality", "transport into target"),
        ("C05", "recurrence-partial", "exact rows are non-callable", "partial", "callable flag", "recurrence absence"),
        ("C06", "burden-positive", "two distinct variants overlap callable region", "supported", "callable bases and background rate", "significance claim"),
        ("C06", "burden-absent", "region has zero overlapping observations", "absent", "empty overlap is retained", "regional protection"),
        ("C06", "burden-partial", "overlap exists without background comparator", "partial", "comparator presence", "enrichment p-value"),
        ("C07", "function-positive", "observed support exceeds matched controls", "supported", "feature namespace and control rows", "causal effect"),
        ("C07", "function-absent", "controls exist without observed variants", "absent", "observed/control label", "functional null proof"),
        ("C07", "function-partial", "observed feature support has no controls", "partial", "control availability", "feature significance"),
        ("C08", "set-positive", "two observed genes share a versioned pathway", "supported", "set namespace and membership version", "pathway causality"),
        ("C08", "set-contradictory", "leading set has opposing directions", "contradictory", "direction retention", "averaged direction"),
        ("C08", "set-partial", "set evidence has no controls", "partial", "control availability", "set enrichment"),
    )
    return tuple(CohortBetaFrontierContractExample(operation, example_id, input_summary, expected_state, required_boundary, prohibited, content_hash({"operation": operation, "example_id": example_id, "expected_state": expected_state}, prefix="contract-example")) for operation, example_id, input_summary, expected_state, required_boundary, prohibited in raw)


def contract_example_map() -> Mapping[str, CohortBetaFrontierContractExample]:
    return {item.example_id: item for item in default_cohort_beta_frontier_contract_examples()}


def contract_example_context() -> str:
    return C05_C08_CONTEXT


__all__ = ["CohortBetaFrontierContractExample", "contract_example_context", "contract_example_map", "default_cohort_beta_frontier_contract_examples"]
