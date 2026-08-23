"""File-level package manifest for public release artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_bundle import CohortBetaFrontierReleaseBundle
from .cohort_beta_frontier_release import CohortBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPackageFile:
    path: str
    media_type: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPackageManifest:
    package_id: str
    files: tuple[CohortBetaFrontierPackageFile, ...]
    ready: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_package_manifest(bundle: CohortBetaFrontierReleaseBundle, release: CohortBetaFrontierReleaseManifest) -> CohortBetaFrontierPackageManifest:
    paths = ("fixture.json", "evaluation.json", "review.csv", "report.md", "provenance.json", "replay.json", "claims.md")
    files = tuple(CohortBetaFrontierPackageFile(path, "text/markdown" if path.endswith("md") else "text/csv" if path.endswith("csv") else "application/json", True, content_hash({"path": path, "bundle": bundle.content_address}, prefix="package-file")) for path in paths)
    return CohortBetaFrontierPackageManifest("cohort-beta-frontier-c05-c08-package", files, bundle.accepted and release.ready and len(files) == 7, content_hash(files, prefix="package"))


__all__ = ["CohortBetaFrontierPackageFile", "CohortBetaFrontierPackageManifest", "build_cohort_beta_frontier_package_manifest"]
