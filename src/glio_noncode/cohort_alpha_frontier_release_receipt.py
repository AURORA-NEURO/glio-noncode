"""Final receipt connecting release manifest, package, and runtime digest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReleaseManifest
from .cohort_alpha_frontier_package import CohortAlphaFrontierPackageManifest
from .cohort_alpha_frontier_runtime_digest import CohortAlphaFrontierRuntimeDigest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseReceipt:
    receipt_id: str
    release_id: str
    package_id: str
    runtime_digest: str
    ready: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_release_receipt(manifest: CohortAlphaFrontierReleaseManifest, package: CohortAlphaFrontierPackageManifest, digest: CohortAlphaFrontierRuntimeDigest) -> CohortAlphaFrontierReleaseReceipt:
    body = {"id": "cohort-alpha-frontier-release-receipt", "release": manifest.release_id, "package": package.package_id, "digest": digest.content_address, "ready": manifest.ready and package.accepted and digest.failed_count == 0}
    return CohortAlphaFrontierReleaseReceipt(body["id"], manifest.release_id, package.package_id, digest.content_address, body["ready"], content_hash(body, prefix="alpha-release-receipt"))


__all__ = ["CohortAlphaFrontierReleaseReceipt", "build_cohort_alpha_frontier_release_receipt"]
