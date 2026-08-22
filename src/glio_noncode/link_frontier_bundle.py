"""Evidence bundle assembly for Domain 10 link frontier releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation
from .link_frontier_lineage import LinkFrontierLineageReport
from .link_frontier_metrics import LinkFrontierMetrics
from .link_frontier_policy import LinkFrontierPolicyReport
from .link_frontier_public_data import LinkFrontierFixture
from .link_frontier_reconciliation import LinkFrontierReconciliation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LinkFrontierEvidenceBundle:
    bundle_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    reconciliation_address: str
    lineage_address: str
    metrics_address: str
    policy_address: str
    accepted: bool
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        if not self.record_ids or not self.source_ids:
            raise ValueError("link bundle requires records and sources")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_link_frontier_bundle(
    fixture: LinkFrontierFixture,
    evaluation: LinkFrontierEvaluation,
    reconciliation: LinkFrontierReconciliation,
    lineage: LinkFrontierLineageReport,
    metrics: LinkFrontierMetrics,
    policy: LinkFrontierPolicyReport,
    *,
    bundle_id: str = "link-frontier-release",
) -> LinkFrontierEvidenceBundle:
    body = {
        "bundle_id": bundle_id,
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "reconciliation_address": reconciliation.content_address,
        "lineage_address": lineage.content_address,
        "metrics_address": metrics.content_address,
        "policy_address": policy.content_address,
        "accepted": all((evaluation.accepted, reconciliation.accepted, lineage.valid, policy.accepted)),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "source_ids": tuple(source.source_id for source in fixture.sources),
    }
    return LinkFrontierEvidenceBundle(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierEvidenceBundle", "build_link_frontier_bundle"]
