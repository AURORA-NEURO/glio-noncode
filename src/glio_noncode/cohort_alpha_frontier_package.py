"""Release package inventory and file-level checksums."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReleaseBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPackageEntry:
    path: str
    media_type: str
    required: bool
    purpose: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPackageManifest:
    package_id: str
    entries: tuple[CohortAlphaFrontierPackageEntry, ...]
    bundle_address: str
    required_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_cohort_alpha_frontier_package(bundle: CohortAlphaFrontierReleaseBundle) -> CohortAlphaFrontierPackageManifest:
    raw = (("fixture.json", "application/json", True, "bounded public-data fixture"), ("evaluation.json", "application/json", True, "typed result rows"), ("metrics.json", "application/json", True, "operation metrics"), ("policy.json", "application/json", True, "publication dispositions"), ("lineage.json", "application/json", True, "source to result edges"), ("reconciliation.json", "application/json", True, "expected state comparison"), ("quality.json", "application/json", True, "release gates"), ("README.md", "text/markdown", True, "scope and claim ceiling"), ("provenance.json", "application/json", True, "source receipts"), ("review-queue.json", "application/json", False, "non-publishable paths"))
    entries = tuple(CohortAlphaFrontierPackageEntry(path, media_type, required, purpose, content_hash({"path": path, "media_type": media_type, "required": required, "purpose": purpose}, prefix="alpha-package-entry")) for path, media_type, required, purpose in raw)
    return CohortAlphaFrontierPackageManifest("cohort-alpha-frontier-c09-c12-package", entries, bundle.content_address, sum(item.required for item in entries), bundle.accepted and len(entries) == 10, content_hash({"entries": entries, "bundle": bundle.content_address}, prefix="alpha-package"))


__all__ = ["CohortAlphaFrontierPackageEntry", "CohortAlphaFrontierPackageManifest", "assemble_cohort_alpha_frontier_package"]
