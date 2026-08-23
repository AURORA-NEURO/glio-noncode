"""Content-addressed D07 evidence bundle assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureDataAudit,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitectureLedger,
    ChromatinArchitectureReviewQueue,
    addressed,
)
from .chromatin_architecture_lineage import ChromatinArchitectureLineage
from .chromatin_architecture_metrics import ChromatinArchitectureMetrics
from .chromatin_architecture_policy import ChromatinArchitecturePolicyReport
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureBundle:
    bundle_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    audit_address: str
    policy_address: str
    review_address: str
    lineage_address: str
    ledger_address: str
    metrics_address: str
    record_count: int
    source_count: int
    review_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_architecture_bundle(
    fixture: ChromatinArchitectureFixture,
    audit: ChromatinArchitectureDataAudit,
    evaluation: ChromatinArchitectureEvaluation,
    policy: ChromatinArchitecturePolicyReport,
    review: ChromatinArchitectureReviewQueue,
    lineage: ChromatinArchitectureLineage,
    ledger: ChromatinArchitectureLedger,
    metrics: ChromatinArchitectureMetrics,
) -> ChromatinArchitectureBundle:
    body = {
        "bundle_id": "d07-chromatin-architecture-bundle-v1",
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "audit_address": audit.content_address,
        "policy_address": policy.content_address,
        "review_address": review.content_address,
        "lineage_address": lineage.content_address,
        "ledger_address": ledger.content_address,
        "metrics_address": metrics.content_address,
        "record_count": len(evaluation.receipts),
        "source_count": len(fixture.sources),
        "review_count": len(review.items),
    }
    return ChromatinArchitectureBundle(
        **body,
        accepted=all(
            str(body[key]).startswith("sha256:") for key in body if key.endswith("_address")
        ),
        content_address=addressed(body, "chromatin-bundle"),
    )


__all__ = ["ChromatinArchitectureBundle", "build_chromatin_architecture_bundle"]
