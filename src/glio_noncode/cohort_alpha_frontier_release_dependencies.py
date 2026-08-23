"""Dependency graph for quality, policy, and release decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseDependency:
    parent: str
    child: str
    required: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseDependencyGraph:
    dependencies: tuple[CohortAlphaFrontierReleaseDependency, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_release_dependencies() -> CohortAlphaFrontierReleaseDependencyGraph:
    raw = (("fixture", "evaluation"), ("evaluation", "metrics"), ("evaluation", "policy"), ("policy", "reconciliation"), ("reconciliation", "quality"), ("quality", "bundle"), ("bundle", "manifest"), ("manifest", "package"), ("package", "report"), ("report", "release"))
    dependencies = tuple(CohortAlphaFrontierReleaseDependency(parent, child, True, True, content_hash({"parent": parent, "child": child, "required": True, "accepted": True}, prefix="alpha-release-dependency")) for parent, child in raw)
    return CohortAlphaFrontierReleaseDependencyGraph(dependencies, len(dependencies) == 10 and all(item.required and item.accepted for item in dependencies), content_hash(dependencies, prefix="alpha-release-dependencies"))


__all__ = ["CohortAlphaFrontierReleaseDependency", "CohortAlphaFrontierReleaseDependencyGraph", "default_cohort_alpha_frontier_release_dependencies"]
