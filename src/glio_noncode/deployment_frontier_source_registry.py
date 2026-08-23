"""Source registry for public portal receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierFixture, DeploymentFrontierSourceReceipt
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierSourceRegistry:
    sources: tuple[DeploymentFrontierSourceReceipt, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_source_registry(fixture: DeploymentFrontierFixture) -> DeploymentFrontierSourceRegistry:
    ids = tuple(item.source_id for item in fixture.sources)
    body = {"sources": fixture.sources, "source_ids": ids, "accepted": len(ids) == len(set(ids)) and all(item.uri.startswith("https://") for item in fixture.sources)}
    return DeploymentFrontierSourceRegistry(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierSourceRegistry", "build_deployment_frontier_source_registry"]
