"""Integrated quality gate for Domain 04 C09–C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_governance_bundle import ReferenceGovernanceBundleBuilder
from .reference_governance_fixture_eval import (
    ReferenceGovernanceEvaluationReport,
    evaluate_reference_governance_fixture,
)
from .reference_governance_lineage import build_reference_governance_lineage
from .reference_governance_policy import (
    evaluate_reference_governance_policy,
    verify_reference_governance_policy,
)
from .reference_governance_public_data import (
    ReferenceGovernanceFixture,
    audit_reference_governance_data,
    build_reference_governance_catalog,
    default_reference_governance_fixture,
)
from .reference_governance_reconciliation import reconcile_reference_governance_views
from .reference_governance_replay import replay_reference_governance_evaluation
from .reference_governance_scenario_matrix import evaluate_reference_governance_scenarios
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceQualityCheck:
    """One integrated quality assertion."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceQualityGateReport:
    """Data, execution, replay, scenario, lineage, bundle, and reconciliation gate."""

    fixture_id: str
    fixture_version: str
    checks: tuple[ReferenceGovernanceQualityCheck, ...]
    evaluation: ReferenceGovernanceEvaluationReport
    replay_address: str
    lineage_address: str
    reconciliation_address: str
    bundle_address: str
    policy_address: str
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


def evaluate_reference_governance_quality_gate(
    fixture: ReferenceGovernanceFixture | None = None,
) -> ReferenceGovernanceQualityGateReport:
    """Run the full C09–C12 evidence gate."""

    selected = fixture or default_reference_governance_fixture()
    data = audit_reference_governance_data(selected)
    evaluation = evaluate_reference_governance_fixture(selected)
    replay = replay_reference_governance_evaluation(evaluation, fixture=selected)
    scenarios = evaluate_reference_governance_scenarios(selected, report=evaluation)
    lineage = build_reference_governance_lineage(evaluation, fixture=selected)
    bundle = ReferenceGovernanceBundleBuilder().build(
        evaluation, fixture=selected, accepted_only=True
    )
    bundle_failures = ReferenceGovernanceBundleBuilder().verify(bundle)
    reconciliation = reconcile_reference_governance_views(
        selected, data, evaluation, replay, scenarios, lineage
    )
    policy = evaluate_reference_governance_policy(selected, evaluation)
    policy_failures = verify_reference_governance_policy(policy)
    checks: list[ReferenceGovernanceQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ReferenceGovernanceQualityCheck(check_id, passed, detail, _address(body)))

    add("data-audit", data.accepted, "public source and payload audit is accepted")
    add("evaluation", evaluation.accepted, "all fixture execution checks pass")
    add("replay", replay.accepted, "deterministic replay checks pass")
    add("scenarios", scenarios.accepted, "independent state scenarios pass")
    add("lineage", lineage.audit(evaluation).passed, "lineage closure and sanitization pass")
    add("bundle", not bundle_failures, "accepted-only bundle verifies")
    add("reconciliation", reconciliation.accepted, "all evidence views reconcile")
    add(
        "policy",
        policy.accepted and not policy_failures,
        "explicit evidence-boundary policy is accepted",
    )
    add(
        "fixture-id",
        data.fixture_id == evaluation.fixture_id == selected.fixture_id,
        "fixture identities agree",
    )
    add(
        "fixture-version",
        data.fixture_version == evaluation.fixture_version == selected.fixture_version,
        "fixture versions agree",
    )
    add(
        "context",
        data.context_key == evaluation.context_key == selected.context_key,
        "contexts agree",
    )
    add("positive-count", evaluation.positive_count == 4, "positive floor is four")
    add("control-count", evaluation.control_count == 12, "control floor is twelve")
    add(
        "receipt-count",
        len(evaluation.receipts) == 16,
        "one receipt exists for every fixture record",
    )
    add(
        "operation-count",
        len({receipt.operation for receipt in evaluation.receipts}) == 4,
        "four operation families execute",
    )
    add(
        "issue-preservation",
        all(
            set(receipt.expected_issue_codes) <= set(receipt.observed_issue_codes)
            for receipt in evaluation.receipts
        ),
        "expected review issue codes remain visible",
    )
    add(
        "positive-floor",
        all(
            receipt.adapter_state == "supported"
            for receipt in evaluation.receipts
            if receipt.role.value == "positive"
        ),
        "positive receipts are supported",
    )
    add(
        "control-floor",
        all(
            receipt.adapter_state != "supported"
            for receipt in evaluation.receipts
            if receipt.role.value == "control"
        ),
        "controls remain non-supported",
    )
    add(
        "no-input-copy",
        all(
            "records" not in receipt.summary and "restrictions" not in receipt.summary
            for receipt in evaluation.receipts
        ),
        "execution summaries are sanitized",
    )
    add(
        "bundle-count",
        len(bundle.entries) == 4,
        "accepted-only bundle contains four positive entries",
    )
    add(
        "graph-size",
        len(lineage.nodes) >= 40 and len(lineage.edges) >= 40,
        "lineage retains source, record, receipt, and check nodes",
    )
    add(
        "scenario-size",
        len(scenarios.results) >= 12,
        "scenario coverage is broad enough for four operations",
    )
    add(
        "replay-address",
        replay.current_evaluation_address == evaluation.content_address,
        "replay points to evaluated content",
    )
    add(
        "catalog-address",
        evaluation.catalog_address == build_reference_governance_catalog(selected).content_address,
        "catalog address is stable",
    )
    add(
        "accepted-state",
        evaluation.accepted and replay.accepted and scenarios.accepted and reconciliation.accepted,
        "all publication prerequisites are accepted",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "checks": checks,
        "evaluation": evaluation,
        "replay_address": replay.content_address,
        "lineage_address": lineage.content_address,
        "reconciliation_address": reconciliation.content_address,
        "bundle_address": bundle.content_address,
        "policy_address": policy.content_address,
    }
    return ReferenceGovernanceQualityGateReport(
        selected.fixture_id,
        selected.fixture_version,
        tuple(checks),
        evaluation,
        replay.content_address,
        lineage.content_address,
        reconciliation.content_address,
        bundle.content_address,
        policy.content_address,
        _address(body),
    )


__all__ = [
    "ReferenceGovernanceQualityCheck",
    "ReferenceGovernanceQualityGateReport",
    "evaluate_reference_governance_quality_gate",
]
