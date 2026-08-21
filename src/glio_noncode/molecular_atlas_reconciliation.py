"""Cross-view reconciliation for Domain 05 C05–C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .molecular_atlas_fixture_eval import MolecularAtlasEvaluationReport
from .molecular_atlas_lineage import MolecularAtlasLineageGraph
from .molecular_atlas_public_data import (
    MolecularAtlasDataAudit,
    MolecularAtlasFixture,
    build_molecular_atlas_catalog,
)
from .molecular_atlas_replay import MolecularAtlasReplayReport
from .molecular_atlas_scenario_matrix import MolecularAtlasScenarioMatrix
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MolecularAtlasReconciliationCheck:
    """One identity, coverage, or boundary assertion."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasReconciliationReport:
    """Reconciled data, execution, replay, scenario, and graph views."""

    fixture_id: str
    checks: tuple[MolecularAtlasReconciliationCheck, ...]
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


def reconcile_molecular_atlas_views(
    fixture: MolecularAtlasFixture,
    data_audit: MolecularAtlasDataAudit,
    evaluation: MolecularAtlasEvaluationReport,
    replay: MolecularAtlasReplayReport,
    scenarios: MolecularAtlasScenarioMatrix,
    lineage: MolecularAtlasLineageGraph,
) -> MolecularAtlasReconciliationReport:
    """Verify that independent artifacts describe one evidence boundary."""

    catalog = build_molecular_atlas_catalog(fixture)
    checks: list[MolecularAtlasReconciliationCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(MolecularAtlasReconciliationCheck(check_id, passed, detail, _address(body)))

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
    add(
        "boundary",
        data_audit.evidence_boundary == fixture.evidence_boundary,
        "all views remain within public aggregate scope",
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
        "evaluation receipts cover catalog records in order",
    )
    add(
        "operation-coverage",
        {item.operation for item in evaluation.receipts} == set(catalog.operations),
        "all four operation families execute",
    )
    add(
        "role-coverage",
        evaluation.positive_count == 4 and evaluation.control_count == 12,
        "positive and control floors agree",
    )
    add(
        "replay-address",
        replay.current_evaluation_address == evaluation.content_address,
        "replay points at current evaluation",
    )
    add(
        "lineage-size",
        len(lineage.nodes) >= 40 and len(lineage.edges) >= 40,
        "lineage retains source, record, receipt, and check nodes",
    )
    add(
        "scenario-floor",
        len(scenarios.results) >= 15,
        "independent state and histone floors remain present",
    )
    add(
        "source-closure",
        all(
            set(record.source_ids) <= {source.source_id for source in fixture.sources}
            for record in fixture.records
        ),
        "records reference only declared public sources",
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return MolecularAtlasReconciliationReport(fixture.fixture_id, tuple(checks), _address(body))


__all__ = [
    "MolecularAtlasReconciliationCheck",
    "MolecularAtlasReconciliationReport",
    "reconcile_molecular_atlas_views",
]
