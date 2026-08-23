"""Freshness receipt for public deployment source anchors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierFixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierFreshnessReport:
    fixture_id: str
    observed_date: str
    source_count: int
    receipts_complete: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_freshness(fixture: DeploymentFrontierFixture, *, observed_date: str = "2026-08-23") -> DeploymentFrontierFreshnessReport:
    complete = all(item.uri.startswith("https://") and item.content_address.startswith("sha256:") for item in fixture.sources)
    body = {"fixture_id": fixture.fixture_id, "observed_date": observed_date, "source_count": len(fixture.sources), "receipts_complete": complete, "accepted": complete and bool(observed_date)}
    return DeploymentFrontierFreshnessReport(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierFreshnessReport", "evaluate_deployment_frontier_freshness"]
