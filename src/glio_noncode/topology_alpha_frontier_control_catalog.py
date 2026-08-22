"""Control inventory tying every fixture control to a review obligation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierControlDefinition:
    control_id: str
    record_id: str
    operation: str
    control_kind: str
    expected_state: str
    issue_codes: tuple[str, ...]
    review_question: str
    release_effect: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierControlCatalog:
    controls: tuple[TopologyAlphaFrontierControlDefinition, ...]
    operation_count: int
    control_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierControlDefinition, ...]:
        return tuple(item for item in self.controls if item.operation == operation)

    def for_kind(self, control_kind: str) -> tuple[TopologyAlphaFrontierControlDefinition, ...]:
        return tuple(item for item in self.controls if item.control_kind == control_kind)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"controls": [item.to_dict() for item in self.controls], "operation_count": self.operation_count, "control_count": self.control_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _kind(row: Any) -> str:
    if "context_mismatch" in row.observed_issue_codes:
        return "foreign_context"
    if row.observed_state == "ambiguous":
        return "disagreement"
    if row.observed_state == "partial":
        return "missing_or_invalid"
    return "control"


def build_topology_alpha_frontier_control_catalog(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierControlCatalog:
    controls = tuple(TopologyAlphaFrontierControlDefinition(f"control-{row.record_id}", row.record_id, row.operation, _kind(row), row.expected_state, row.observed_issue_codes, "Can the declared state and issue receipts be resolved without collapsing uncertainty?", "retain review until the exit condition is met") for row in evaluation.controls())
    return TopologyAlphaFrontierControlCatalog(controls, len({item.operation for item in controls}), len(controls), len(controls) == 12 and all(item.review_question and item.release_effect for item in controls))


__all__ = ["TopologyAlphaFrontierControlCatalog", "TopologyAlphaFrontierControlDefinition", "build_topology_alpha_frontier_control_catalog"]
