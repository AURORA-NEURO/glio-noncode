"""Resolved public source registry for the lifecycle beta fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierFixture, LifecycleBetaFrontierSourceReceipt
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierSourceRegistry:
    sources: tuple[LifecycleBetaFrontierSourceReceipt, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def source(self, source_id: str) -> LifecycleBetaFrontierSourceReceipt:
        require_non_empty(source_id, "source_id")
        return next(item for item in self.sources if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_source_registry(fixture: LifecycleBetaFrontierFixture) -> LifecycleBetaFrontierSourceRegistry:
    sources = tuple(sorted(fixture.sources, key=lambda item: item.source_id))
    source_ids = tuple(item.source_id for item in sources)
    accepted = len(source_ids) == len(set(source_ids)) and all(item.uri.startswith("https://") for item in sources)
    return LifecycleBetaFrontierSourceRegistry(sources, source_ids, accepted, content_hash({"sources": sources, "accepted": accepted}))


__all__ = ["LifecycleBetaFrontierSourceRegistry", "build_lifecycle_beta_frontier_source_registry"]
