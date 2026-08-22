"""Resource limits for local and Actions runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierResourceLimits:
    maximum_records: int
    maximum_sources: int
    maximum_events: int
    maximum_seconds: float
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def within(self, *, records: int, sources: int, events: int, seconds: float) -> bool:
        return records <= self.maximum_records and sources <= self.maximum_sources and events <= self.maximum_events and seconds <= self.maximum_seconds

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"maximum_records": self.maximum_records, "maximum_sources": self.maximum_sources, "maximum_events": self.maximum_events, "maximum_seconds": self.maximum_seconds, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_resource_limits() -> LinkGraphAlphaFrontierResourceLimits:
    return LinkGraphAlphaFrontierResourceLimits(10000, 100, 32, 60.0, True)


__all__ = ["LinkGraphAlphaFrontierResourceLimits", "default_link_graph_alpha_frontier_resource_limits"]
