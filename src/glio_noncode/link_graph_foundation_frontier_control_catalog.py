"""Positive and control catalog for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierControlDefinition:
    control_id: str
    record_id: str
    operation: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierControlCatalog:
    positives: tuple[LinkGraphFoundationFrontierControlDefinition, ...]
    controls: tuple[LinkGraphFoundationFrontierControlDefinition, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"positives": [item.to_dict() for item in self.positives], "controls": [item.to_dict() for item in self.controls], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_control_catalog(fixture: LinkGraphFoundationFrontierFixture) -> LinkGraphFoundationFrontierControlCatalog:
    positives = tuple(LinkGraphFoundationFrontierControlDefinition(f"positive:{row.record_id}", row.record_id, row.operation.value, row.expected_state, row.expected_issue_codes, "positive baseline") for row in fixture.positive_records)
    controls = tuple(LinkGraphFoundationFrontierControlDefinition(f"control:{row.record_id}", row.record_id, row.operation.value, row.expected_state, row.expected_issue_codes, "control for absence, ambiguity, contradiction, or context") for row in fixture.control_records)
    return LinkGraphFoundationFrontierControlCatalog(positives, controls, len(positives) == 4 and len(controls) == 12)


__all__ = ["LinkGraphFoundationFrontierControlCatalog", "LinkGraphFoundationFrontierControlDefinition", "build_link_graph_foundation_frontier_control_catalog"]
