"""Catalog of positive and control rows used by the replay suite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierControlDefinition:
    control_id: str
    operation: str
    record_id: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierControlCatalog:
    positives: tuple[LinkGraphAlphaFrontierControlDefinition, ...]
    controls: tuple[LinkGraphAlphaFrontierControlDefinition, ...]
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


def build_link_graph_alpha_frontier_control_catalog(fixture: LinkGraphAlphaFrontierFixture) -> LinkGraphAlphaFrontierControlCatalog:
    positives = tuple(LinkGraphAlphaFrontierControlDefinition(f"positive:{record.record_id}", record.operation.value, record.record_id, record.expected_state, record.expected_issue_codes, "positive bounded path") for record in fixture.positive_records)
    controls = tuple(LinkGraphAlphaFrontierControlDefinition(f"control:{record.record_id}", record.operation.value, record.record_id, record.expected_state, record.expected_issue_codes, "negative, ambiguous, contradictory, or boundary control") for record in fixture.control_records)
    return LinkGraphAlphaFrontierControlCatalog(positives, controls, len(positives) == 4 and len(controls) == 12)


__all__ = ["LinkGraphAlphaFrontierControlCatalog", "LinkGraphAlphaFrontierControlDefinition", "build_link_graph_alpha_frontier_control_catalog"]
