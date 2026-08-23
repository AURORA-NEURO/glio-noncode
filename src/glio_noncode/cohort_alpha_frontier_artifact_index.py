"""Artifact index used to assemble and inspect the release package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_package import CohortAlphaFrontierPackageManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierArtifact:
    artifact_id: str
    path: str
    category: str
    required: bool
    address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierArtifactIndex:
    artifacts: tuple[CohortAlphaFrontierArtifact, ...]
    category_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_artifact_index(package: CohortAlphaFrontierPackageManifest) -> CohortAlphaFrontierArtifactIndex:
    artifacts = tuple(CohortAlphaFrontierArtifact(f"artifact-{index:02d}", entry.path, "data" if entry.path.endswith("json") else "documentation", entry.required, entry.content_address, content_hash({"id": index, "path": entry.path, "category": "data" if entry.path.endswith("json") else "documentation", "required": entry.required, "address": entry.content_address}, prefix="alpha-artifact")) for index, entry in enumerate(package.entries, 1))
    counts = {category: sum(item.category == category for item in artifacts) for category in sorted({item.category for item in artifacts})}
    return CohortAlphaFrontierArtifactIndex(artifacts, counts, package.accepted and len(artifacts) == 10 and all(item.address for item in artifacts), content_hash({"artifacts": artifacts, "counts": counts}, prefix="alpha-artifact-index"))


__all__ = ["CohortAlphaFrontierArtifact", "CohortAlphaFrontierArtifactIndex", "build_cohort_alpha_frontier_artifact_index"]
