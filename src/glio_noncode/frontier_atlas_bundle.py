"""Immutable C13-C16 evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_fixture_eval import FrontierAtlasEvaluationReport
from .frontier_atlas_lineage import FrontierAtlasLineageReport
from .frontier_atlas_metrics import FrontierAtlasMetrics
from .frontier_atlas_policy import FrontierAtlasPolicyReport
from .frontier_atlas_public_data import FrontierAtlasDataAudit, FrontierAtlasFixture
from .frontier_atlas_reconciliation import FrontierAtlasReconciliationReport
from .frontier_atlas_replay import FrontierAtlasReplayReport
from .frontier_atlas_scenario_matrix import FrontierAtlasScenarioReport
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasBundle:
    bundle_id: str
    bundle_version: str
    fixture: FrontierAtlasFixture
    data_audit: FrontierAtlasDataAudit
    evaluation: FrontierAtlasEvaluationReport
    replay: FrontierAtlasReplayReport
    scenarios: FrontierAtlasScenarioReport
    policy: FrontierAtlasPolicyReport
    lineage: FrontierAtlasLineageReport
    reconciliation: FrontierAtlasReconciliationReport
    metrics: FrontierAtlasMetrics
    content_address: str

    def __post_init__(self) -> None:
        for name in ("bundle_id", "bundle_version", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    @property
    def accepted(self) -> bool:
        return all(
            (
                self.data_audit.accepted,
                self.evaluation.accepted,
                self.replay.accepted,
                self.scenarios.accepted,
                self.policy.accepted,
                self.lineage.accepted,
                self.reconciliation.accepted,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_frontier_atlas_bundle(
    fixture: FrontierAtlasFixture,
    data_audit: FrontierAtlasDataAudit,
    evaluation: FrontierAtlasEvaluationReport,
    replay: FrontierAtlasReplayReport,
    scenarios: FrontierAtlasScenarioReport,
    policy: FrontierAtlasPolicyReport,
    lineage: FrontierAtlasLineageReport,
    reconciliation: FrontierAtlasReconciliationReport,
    metrics: FrontierAtlasMetrics,
) -> FrontierAtlasBundle:
    body = {
        "bundle_id": "frontier-atlas-bundle",
        "bundle_version": "2026.08.d05-c13-c16.v1",
        "fixture": fixture,
        "data_audit": data_audit,
        "evaluation": evaluation,
        "replay": replay,
        "scenarios": scenarios,
        "policy": policy,
        "lineage": lineage,
        "reconciliation": reconciliation,
        "metrics": metrics,
    }
    return FrontierAtlasBundle(**body, content_address=content_hash(body))


def write_frontier_atlas_bundle(bundle: FrontierAtlasBundle, path: str) -> None:
    from pathlib import Path

    Path(path).write_text(
        __import__("json").dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = ["FrontierAtlasBundle", "build_frontier_atlas_bundle", "write_frontier_atlas_bundle"]
