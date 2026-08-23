"""Support contacts and escalation vocabulary for the review package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierSupportRoute:
    route_id: str
    issue_family: str
    primary_role: str
    backup_role: str
    escalation_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierSupportDirectory:
    routes: tuple[LifecycleBetaFrontierSupportRoute, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_lifecycle_beta_frontier_support_directory() -> LifecycleBetaFrontierSupportDirectory:
    rows = (
        ("context", "context_translation", "domain_expert", "foreign context remains blocked"),
        ("provenance", "data_provenance", "computational_methods", "source or parent cannot be resolved"),
        ("statistics", "statistical_review", "domain_expert", "contradiction or split decision persists"),
        ("assay", "molecular_assay", "domain_expert", "tier evidence is unclassified"),
        ("release", "domain_expert", "data_provenance", "blocking gate or missing role"),
        ("integrity", "computational_methods", "data_provenance", "content address drift"),
    )
    routes = []
    for issue_family, primary_role, backup_role, escalation_condition in rows:
        body = {"route_id": f"route:{issue_family}", "issue_family": issue_family, "primary_role": primary_role, "backup_role": backup_role, "escalation_condition": escalation_condition}
        routes.append(LifecycleBetaFrontierSupportRoute(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierSupportDirectory(tuple(routes), content_hash({"routes": tuple(routes)}))


__all__ = ["LifecycleBetaFrontierSupportDirectory", "LifecycleBetaFrontierSupportRoute", "default_lifecycle_beta_frontier_support_directory"]
