"""Small API projection that avoids exposing internal dataclass structure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation
from .lifecycle_beta_frontier_views import LifecycleBetaFrontierView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierApiView:
    api_version: str
    fixture_id: str
    accepted: bool
    record_count: int
    entries: tuple[dict[str, Any], ...]
    links: dict[str, str]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_api_view(evaluation: LifecycleBetaFrontierEvaluation, view: LifecycleBetaFrontierView) -> LifecycleBetaFrontierApiView:
    entries = tuple({"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.state.value, "accepted": item.accepted, "issues": list(item.issue_codes)} for item in view.entries)
    links = {"evaluation": evaluation.content_address, "review": view.content_address}
    body = {"api_version": "2026.08.v1", "fixture_id": evaluation.fixture_id, "accepted": evaluation.accepted, "record_count": len(entries), "entries": entries, "links": links}
    return LifecycleBetaFrontierApiView(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierApiView", "build_lifecycle_beta_frontier_api_view"]
