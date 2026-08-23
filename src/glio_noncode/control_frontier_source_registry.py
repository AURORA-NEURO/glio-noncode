"""Resolved public source registry for control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierFixture, ControlFrontierSourceReceipt
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierSourceRegistry:
    sources: tuple[ControlFrontierSourceReceipt, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def source(self, source_id: str) -> ControlFrontierSourceReceipt:
        require_non_empty(source_id, "source_id")
        return next(item for item in self.sources if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_source_registry(fixture: ControlFrontierFixture) -> ControlFrontierSourceRegistry:
    sources = tuple(sorted(fixture.sources, key=lambda item: item.source_id))
    source_ids = tuple(item.source_id for item in sources)
    accepted = len(source_ids) == len(set(source_ids)) and all(item.uri.startswith("https://") for item in sources)
    return ControlFrontierSourceRegistry(sources, source_ids, accepted, content_hash({"sources": sources, "accepted": accepted}))


__all__ = ["ControlFrontierSourceRegistry", "build_control_frontier_source_registry"]
