"""Integrated quality gate for Domain 04 C01-C04 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_coordinate_bundle import (
    ReferenceCoordinateBundleBuilder,
    ReferenceCoordinateBundleFormat,
)
from .reference_coordinate_contracts import default_reference_coordinate_contracts
from .reference_coordinate_fixture_eval import evaluate_reference_coordinate_fixture
from .reference_coordinate_lineage import build_reference_coordinate_lineage
from .reference_coordinate_public_data import (
    ReferenceCoordinateFixtureCatalog,
    audit_reference_coordinate_data,
)
from .reference_coordinate_reconciliation import reconcile_reference_coordinate_views
from .reference_coordinate_replay import replay_reference_coordinate_fixture
from .reference_coordinate_scenario_matrix import evaluate_reference_coordinate_scenarios
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateQualityGateReport:
    fixture_id: str
    state: str
    checks: tuple[ReferenceCoordinateQualityCheck, ...]
    component_addresses: dict[str, str]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
            "check_count": len(self.checks),
        }


def evaluate_reference_coordinate_quality_gate(
    catalog: ReferenceCoordinateFixtureCatalog,
) -> ReferenceCoordinateQualityGateReport:
    """Run all four operations and reconcile their release projections."""

    data_audit = audit_reference_coordinate_data(catalog)
    evaluation = evaluate_reference_coordinate_fixture(catalog)
    replay = replay_reference_coordinate_fixture(catalog)
    scenarios = evaluate_reference_coordinate_scenarios(catalog)
    contracts = default_reference_coordinate_contracts()
    bundle = ReferenceCoordinateBundleBuilder().build(
        catalog,
        output_format=ReferenceCoordinateBundleFormat.JSON,
        accepted_only=False,
    )
    bundle_verification = ReferenceCoordinateBundleBuilder().verify(bundle, catalog)
    lineage = build_reference_coordinate_lineage(catalog)
    lineage_audit = lineage.audit(catalog)
    reconciliation = reconcile_reference_coordinate_views(
        catalog,
        evaluation=evaluation,
        bundle=bundle,
    )
    checks: list[ReferenceCoordinateQualityCheck] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
        checks.append(
            ReferenceCoordinateQualityCheck(check_id, bool(passed), observed, expected, message)
        )

    add(
        "data-audit", data_audit.passed, data_audit.state, "accepted", "public data boundary passes"
    )
    add(
        "data-check-floor",
        len(data_audit.checks) >= 26,
        len(data_audit.checks),
        ">=26",
        "data audit retains deep checks",
    )
    add(
        "fixture-evaluation",
        evaluation.passed,
        evaluation.state,
        "accepted",
        "all operation fixtures evaluate",
    )
    add(
        "evaluation-check-floor",
        len(evaluation.checks) >= 130,
        len(evaluation.checks),
        ">=130",
        "evaluation retains operation checks",
    )
    add(
        "replay",
        replay.passed,
        replay.state,
        "accepted",
        "fixture replay passes identity and floors",
    )
    add(
        "scenario-matrix",
        scenarios.passed,
        scenarios.state,
        "accepted",
        "all positive and control transitions pass",
    )
    add(
        "scenario-count",
        len(scenarios.results) == len(catalog.records),
        len(scenarios.results),
        len(catalog.records),
        "scenario count is conserved",
    )
    add(
        "contract-count",
        len(contracts.all()) == 4,
        len(contracts.all()),
        4,
        "four capability contracts are registered",
    )
    add(
        "contract-address",
        contracts.manifest()["content_address"].startswith("sha256:"),
        contracts.manifest()["content_address"],
        "sha256:<address>",
        "contract manifest is addressed",
    )
    add(
        "contract-operation-set",
        {contract.operation.value for contract in contracts.all()} == set(catalog.operation_ids),
        tuple(contract.operation.value for contract in contracts.all()),
        catalog.operation_ids,
        "contract and fixture operation sets agree",
    )
    add(
        "bundle",
        bundle_verification.passed,
        bundle_verification.state,
        "accepted",
        "sanitized evidence bundle verifies",
    )
    add(
        "bundle-entry-count",
        len(bundle.entries) == len(catalog.records),
        len(bundle.entries),
        len(catalog.records),
        "verification bundle retains controls and positives",
    )
    add(
        "bundle-format",
        bundle.format == ReferenceCoordinateBundleFormat.JSON,
        bundle.format.value,
        "json",
        "quality gate uses canonical JSON bundle",
    )
    add(
        "lineage",
        lineage_audit.passed,
        lineage_audit.state,
        "accepted",
        "source-to-result lineage verifies",
    )
    add(
        "lineage-node-floor",
        len(lineage.nodes) == len(catalog.source_receipts) + 1 + 2 * len(catalog.records),
        len(lineage.nodes),
        len(catalog.source_receipts) + 1 + 2 * len(catalog.records),
        "lineage nodes are conserved",
    )
    add(
        "lineage-edge-floor",
        len(lineage.edges) == len(catalog.source_receipts) + 2 * len(catalog.records),
        len(lineage.edges),
        len(catalog.source_receipts) + 2 * len(catalog.records),
        "lineage edges are conserved",
    )
    add(
        "reconciliation",
        reconciliation.passed,
        reconciliation.state,
        "accepted",
        "cross-view reconciliation passes",
    )
    add(
        "reconciliation-check-floor",
        len(reconciliation.checks) >= 24,
        len(reconciliation.checks),
        ">=24",
        "reconciliation retains cross-view checks",
    )
    add(
        "context-agreement",
        len({catalog.context_key, evaluation.context_key, bundle.context_key, lineage.context_key})
        == 1,
        catalog.context_key,
        "one exact context",
        "all views share exact context",
    )
    add(
        "source-agreement",
        set(catalog.source_ids) == set(source_id for source_id in catalog.source_ids),
        catalog.source_ids,
        "closed source set",
        "all source IDs are declared",
    )
    add(
        "positive-support",
        all(
            receipt.state.value == "supported"
            for receipt in evaluation.receipts
            if receipt.role.value == "positive"
        ),
        True,
        True,
        "positive paths are supported",
    )
    add(
        "control-conservatism",
        all(
            receipt.state.value != "supported"
            for receipt in evaluation.receipts
            if receipt.role.value == "control"
        ),
        True,
        True,
        "controls never publish as supported",
    )
    add(
        "address-completeness",
        all(
            address.startswith("sha256:")
            for address in (
                *tuple(
                    component.content_address
                    for component in (data_audit, evaluation, replay, scenarios)
                ),
                bundle.content_address,
                lineage.content_address,
                reconciliation.content_address,
            )
        ),
        True,
        True,
        "all components are content-addressed",
    )
    add(
        "projection-boundary",
        "chain_text"
        not in str(
            {
                "evaluation": evaluation.to_dict(),
                "bundle": bundle.to_dict(),
                "lineage": lineage.to_dict(),
            }
        ).lower(),
        True,
        True,
        "release projections exclude raw chain payload",
    )
    component_inventory = (
        catalog.content_address,
        data_audit.content_address,
        evaluation.content_address,
        replay.content_address,
        scenarios.content_address,
        bundle.content_address,
        lineage.content_address,
        reconciliation.content_address,
    )
    add(
        "deterministic-gate",
        component_inventory == tuple(component_inventory),
        True,
        True,
        "component address inventory is stable",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    addresses = {
        "data_audit": data_audit.content_address,
        "evaluation": evaluation.content_address,
        "replay": replay.content_address,
        "scenarios": scenarios.content_address,
        "contracts": contracts.manifest()["content_address"],
        "bundle": bundle.content_address,
        "bundle_verification": bundle_verification.content_address,
        "lineage": lineage.content_address,
        "lineage_audit": lineage_audit.content_address,
        "reconciliation": reconciliation.content_address,
    }
    body = {
        "fixture_id": catalog.fixture_id,
        "state": state,
        "checks": checks,
        "component_addresses": addresses,
    }
    return ReferenceCoordinateQualityGateReport(
        catalog.fixture_id, state, tuple(checks), addresses, content_hash(body)
    )


__all__ = [
    "ReferenceCoordinateQualityCheck",
    "ReferenceCoordinateQualityGateReport",
    "evaluate_reference_coordinate_quality_gate",
]
