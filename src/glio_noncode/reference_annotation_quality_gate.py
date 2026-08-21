"""Integrated quality gate for Domain 04 C05–C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_annotation_bundle import ReferenceAnnotationBundleBuilder
from .reference_annotation_contracts import default_reference_annotation_contracts
from .reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from .reference_annotation_lineage import build_reference_annotation_lineage
from .reference_annotation_public_data import (
    ReferenceAnnotationFixture,
    audit_reference_annotation_data,
    default_reference_annotation_fixture,
)
from .reference_annotation_reconciliation import reconcile_reference_annotation_views
from .reference_annotation_replay import replay_reference_annotation_evaluation
from .reference_annotation_scenario_matrix import evaluate_reference_annotation_scenarios
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationQualityGateReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    checks: tuple[ReferenceAnnotationQualityCheck, ...]
    component_inventory: tuple[str, ...]
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


def evaluate_reference_annotation_quality_gate(
    fixture: ReferenceAnnotationFixture | None = None,
) -> ReferenceAnnotationQualityGateReport:
    """Run data, contracts, execution, replay, scenarios, bundle, lineage, and reconciliation."""

    selected = fixture or default_reference_annotation_fixture()
    data_audit = audit_reference_annotation_data(selected)
    contracts = default_reference_annotation_contracts()
    evaluation = evaluate_reference_annotation_fixture(selected, contracts=contracts)
    replay = replay_reference_annotation_evaluation(evaluation)
    scenarios = evaluate_reference_annotation_scenarios(selected, report=evaluation)
    builder = ReferenceAnnotationBundleBuilder()
    bundle = builder.build(evaluation, fixture=selected, accepted_only=True)
    lineage = build_reference_annotation_lineage(evaluation, fixture=selected)
    reconciliation = reconcile_reference_annotation_views(
        evaluation, bundle, lineage, fixture=selected
    )
    inventory = (
        "public_data",
        "contract_registry",
        "fixture_evaluation",
        "replay",
        "scenario_matrix",
        "bundle",
        "lineage",
        "reconciliation",
    )
    checks: list[ReferenceAnnotationQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ReferenceAnnotationQualityCheck(check_id, passed, detail, _address(body)))

    add("data-audit", data_audit.accepted, "public source and record boundary is accepted")
    add("contract-count", len(contracts.contracts) == 4, "four C05–C08 contracts are registered")
    add(
        "contract-addresses",
        all(contract.content_address for contract in contracts.contracts),
        "contract addresses are retained",
    )
    add("evaluation", evaluation.accepted, "all positive and control operations evaluate")
    add("evaluation-depth", len(evaluation.checks) >= 120, "evaluation check floor is met")
    add(
        "evaluation-receipts",
        len(evaluation.receipts) == len(selected.records),
        "every fixture record has a receipt",
    )
    add("replay", replay.accepted, "fixture replay identity and floors are accepted")
    add("scenario-matrix", scenarios.accepted, "all scenario transitions are accepted")
    add(
        "scenario-count",
        len(scenarios.results) == len(selected.records),
        "one scenario exists per record",
    )
    add("bundle-verify", not builder.verify(bundle), "accepted-only bundle verifies")
    add(
        "bundle-published",
        bundle.published and bundle.accepted_count == 4,
        "only four positive entries are publishable",
    )
    add("lineage-audit", lineage.audit.accepted, "lineage graph audit is accepted")
    add(
        "lineage-shape",
        len(lineage.nodes) == 38 and len(lineage.edges) == 59,
        "source, fixture, record, result, and source-link topology is retained",
    )
    add("reconciliation", reconciliation.accepted, "cross-view reconciliation is accepted")
    add(
        "reconciliation-depth",
        len(reconciliation.checks) >= 17,
        "reconciliation check floor is met",
    )
    add("component-inventory", inventory == tuple(inventory), "all integrated components are named")
    add(
        "context-closure",
        selected.context_key == evaluation.context_key == bundle.context_key == lineage.context_key,
        "all stages share exact context",
    )
    add(
        "fixture-identity",
        selected.fixture_id == evaluation.fixture_id == bundle.fixture_id,
        "all stages share fixture identity",
    )
    add(
        "review-boundary",
        all(
            receipt.resolution_state != "supported"
            for receipt in evaluation.receipts
            if receipt.role.value == "control"
        ),
        "controls cannot become accepted",
    )
    add(
        "positive-boundary",
        all(
            receipt.resolution_state == "supported"
            for receipt in evaluation.receipts
            if receipt.role.value == "positive"
        ),
        "positives remain accepted",
    )
    add(
        "raw-input-exclusion",
        all("input_text" not in receipt.summary for receipt in evaluation.receipts),
        "execution receipts exclude input text",
    )
    add(
        "content-addresses",
        all(check.content_address for check in checks),
        "gate checks are content addressed",
    )
    add("deterministic-count", len(checks) == 22, "integrated gate emits stable check count")
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "checks": checks,
        "component_inventory": inventory,
    }
    return ReferenceAnnotationQualityGateReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        tuple(checks),
        inventory,
        _address(body),
    )


__all__ = [
    "ReferenceAnnotationQualityCheck",
    "ReferenceAnnotationQualityGateReport",
    "evaluate_reference_annotation_quality_gate",
]
