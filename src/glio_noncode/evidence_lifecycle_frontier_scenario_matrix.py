"""Boundary scenario matrix for Domain 14 evidence lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleScenario:
    scenario_id: str
    operation: EvidenceLifecycleOperation
    dimensions: tuple[tuple[str, str], ...]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    review_required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleScenarioMatrix:
    matrix_id: str
    dimensions: tuple[str, ...]
    scenarios: tuple[EvidenceLifecycleScenario, ...]
    content_address: str

    @property
    def review_scenarios(self) -> tuple[EvidenceLifecycleScenario, ...]:
        return tuple(item for item in self.scenarios if item.review_required)

    def by_operation(self, operation: EvidenceLifecycleOperation) -> tuple[EvidenceLifecycleScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_lifecycle_scenario_matrix() -> EvidenceLifecycleScenarioMatrix:
    dimensions = ("source_shape", "citation_resolution", "lineage", "context", "edge_state", "disagreement")
    values = (("complete", "resolved", "active", "exact", "supported", "clear"), ("malformed", "quarantined", "orphan", "exact", "partial", "incomplete"), ("duplicate", "quarantined", "superseded", "exact", "contradictory", "contradictory"), ("complete", "resolved", "active", "mismatch", "out_of_domain", "out_of_domain"))
    rows: list[EvidenceLifecycleScenario] = []
    operations = tuple(EvidenceLifecycleOperation)
    for index in range(27):
        operation = operations[index % len(operations)]
        pattern = values[index % len(values)]
        state = {"citation_resolution": ("supported", "partial", "partial", "abstained"), "graph_construction": ("supported", "partial", "supported", "out_of_domain"), "edge_validation": ("supported", "partial", "contradictory", "out_of_domain"), "disagreement_tracking": ("clear", "incomplete", "contradictory", "out_of_domain")}[operation.value][index % len(values)]
        issues = () if state in {"supported", "clear"} else (("context_mismatch",) if state == "out_of_domain" else ("review_required",))
        body = {"scenario_id": f"D14-S{index + 1:03d}", "operation": operation, "dimensions": tuple(zip(dimensions, pattern, strict=True)), "expected_state": state, "expected_issue_codes": issues, "review_required": state not in {"supported", "clear"}}
        rows.append(EvidenceLifecycleScenario(**body, content_address=content_hash(body)))
    for index, operation in enumerate(operations, start=1):
        body = {"scenario_id": f"D14-OP-{index:02d}", "operation": operation, "dimensions": (("surface", "positive"), ("control_count", "three")), "expected_state": "review_required", "expected_issue_codes": (), "review_required": False}
        rows.append(EvidenceLifecycleScenario(**body, content_address=content_hash(body)))
    body = {"matrix_id": "evidence-lifecycle-scenarios", "dimensions": dimensions, "scenarios": tuple(rows)}
    return EvidenceLifecycleScenarioMatrix(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleScenario", "EvidenceLifecycleScenarioMatrix", "build_evidence_lifecycle_scenario_matrix"]
