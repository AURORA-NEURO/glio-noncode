"""Cross-view reconciliation for Domain 04 C09–C12 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_governance_fixture_eval import ReferenceGovernanceEvaluationReport
from .reference_governance_lineage import ReferenceGovernanceLineageGraph
from .reference_governance_public_data import (
    ReferenceGovernanceDataAudit,
    ReferenceGovernanceFixture,
    build_reference_governance_catalog,
)
from .reference_governance_replay import ReferenceGovernanceReplayReport
from .reference_governance_scenario_matrix import ReferenceGovernanceScenarioMatrix
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceReconciliationCheck:
    """One cross-view identity or coverage assertion."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceReconciliationReport:
    """Reconciled public data, execution, replay, scenario, and graph views."""

    fixture_id: str
    checks: tuple[ReferenceGovernanceReconciliationCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def reconcile_reference_governance_views(
    fixture: ReferenceGovernanceFixture,
    data_audit: ReferenceGovernanceDataAudit,
    evaluation: ReferenceGovernanceEvaluationReport,
    replay: ReferenceGovernanceReplayReport,
    scenarios: ReferenceGovernanceScenarioMatrix,
    lineage: ReferenceGovernanceLineageGraph,
) -> ReferenceGovernanceReconciliationReport:
    """Verify that independent artifacts describe the same fixture boundary."""

    catalog = build_reference_governance_catalog(fixture)
    checks: list[ReferenceGovernanceReconciliationCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(
            ReferenceGovernanceReconciliationCheck(check_id, passed, detail, _address(body))
        )

    add(
        "fixture-id",
        all(
            item == fixture.fixture_id
            for item in (
                data_audit.fixture_id,
                evaluation.fixture_id,
                lineage.fixture_id,
                replay.expectation.fixture_id,
                scenarios.fixture_id,
            )
        ),
        "all views share fixture identity",
    )
    add(
        "fixture-version",
        data_audit.fixture_version
        == evaluation.fixture_version
        == replay.expectation.fixture_version
        == fixture.fixture_version,
        "all views share fixture version",
    )
    add(
        "context",
        data_audit.context_key
        == evaluation.context_key
        == replay.expectation.context_key
        == fixture.context_key,
        "all views share exact context",
    )
    add("data-accepted", data_audit.accepted, "public source audit is accepted")
    add("evaluation-accepted", evaluation.accepted, "fixture execution is accepted")
    add("replay-accepted", replay.accepted, "fixture replay is accepted")
    add("scenario-accepted", scenarios.accepted, "scenario matrix is accepted")
    add("lineage-accepted", lineage.audit(evaluation).passed, "lineage graph is accepted")
    add(
        "catalog-address",
        evaluation.catalog_address == catalog.content_address,
        "evaluation references the fixture catalog",
    )
    add(
        "record-coverage",
        tuple(item.record_id for item in evaluation.receipts) == catalog.record_ids,
        "evaluation receipts cover records in catalog order",
    )
    add(
        "operation-coverage",
        {item.operation for item in evaluation.receipts} == set(catalog.operations),
        "evaluation covers every operation",
    )
    add(
        "role-coverage",
        evaluation.positive_count == 4 and evaluation.control_count == 12,
        "positive and control floors agree",
    )
    add(
        "replay-address",
        replay.current_evaluation_address == evaluation.content_address,
        "replay points at the current evaluation address",
    )
    add(
        "lineage-address",
        lineage.audit(evaluation).node_count >= len(evaluation.receipts),
        "lineage retains receipt nodes",
    )
    add(
        "scenario-floor",
        len(scenarios.results) >= 12,
        "scenario matrix retains independent state floors",
    )
    add(
        "source-closure",
        all(
            set(record.source_ids) <= set(item.source_id for item in fixture.sources)
            for record in fixture.records
        ),
        "records reference only declared public sources",
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return ReferenceGovernanceReconciliationReport(
        fixture.fixture_id, tuple(checks), _address(body)
    )


__all__ = [
    "ReferenceGovernanceReconciliationCheck",
    "ReferenceGovernanceReconciliationReport",
    "reconcile_reference_governance_views",
]
