"""Scope and interpretation policy for Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_public_data import (
    TOPOLOGY_FRONTIER_CONTEXT_KEY,
    TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY,
    TopologyFrontierFixture,
    TopologyFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class TopologyFrontierPolicyRule:
    rule_id: str
    operation: TopologyFrontierOperation | None
    description: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.rule_id, "rule_id")
        require_non_empty(self.description, "description")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierPolicyCheck:
    check_id: str
    rule_id: str
    record_id: str | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierPolicyReport:
    fixture_id: str
    boundary: str
    context_key: str
    rules: tuple[TopologyFrontierPolicyRule, ...]
    checks: tuple[TopologyFrontierPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def default_topology_frontier_policy_rules() -> tuple[TopologyFrontierPolicyRule, ...]:
    declarations = (
        ("D09-P01", None, "public aggregate sources remain explicitly bounded"),
        ("D09-P02", None, "context-mismatched topology is not transported"),
        ("D09-P03", TopologyFrontierOperation.ECDNA_CONTACT, "contact observations are not causal link claims"),
        ("D09-P04", TopologyFrontierOperation.COMPARTMENT_SWITCH, "compartment differences are descriptive signed observations"),
        ("D09-P05", TopologyFrontierOperation.TOPOLOGY_TRANSPORT, "uncertainty is retained across every declared edge"),
        ("D09-P06", TopologyFrontierOperation.EVIDENCE_PUBLICATION, "publication requires path and assay receipts"),
        ("D09-P07", None, "research evidence is not a clinical or treatment decision"),
        ("D09-P08", None, "aggregate records do not imply individual-level identity"),
    )
    rules = []
    for rule_id, operation, description in declarations:
        body = {"rule_id": rule_id, "operation": operation, "description": description}
        rules.append(TopologyFrontierPolicyRule(**body, content_address=content_hash(body)))
    return tuple(rules)


def evaluate_topology_frontier_policy(
    fixture: TopologyFrontierFixture,
    evaluation: TopologyFrontierEvaluationReport,
    *,
    rules: tuple[TopologyFrontierPolicyRule, ...] | None = None,
) -> TopologyFrontierPolicyReport:
    selected_rules = rules or default_topology_frontier_policy_rules()
    checks: list[TopologyFrontierPolicyCheck] = []

    def add(check_id: str, rule_id: str, record_id: str | None, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "rule_id": rule_id, "record_id": record_id, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierPolicyCheck(**body, content_address=content_hash(body)))

    add("boundary", "D09-P01", None, fixture.evidence_boundary == TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY, "fixture boundary is public aggregate")
    add("context", "D09-P02", None, fixture.context_key == TOPOLOGY_FRONTIER_CONTEXT_KEY, "fixture context is exact")
    add("source-closure", "D09-P01", None, all(fixture.record_map()[item.record_id].source_ids for item in evaluation.receipts), "every receipt retains source identifiers")
    add("state-vocabulary", "D09-P01", None, all(item.adapter_state in {"supported", "partial", "out_of_domain", "invalid"} for item in evaluation.receipts), "states are bounded")
    for operation, rule_id in (
        (TopologyFrontierOperation.ECDNA_CONTACT, "D09-P03"),
        (TopologyFrontierOperation.COMPARTMENT_SWITCH, "D09-P04"),
        (TopologyFrontierOperation.TOPOLOGY_TRANSPORT, "D09-P05"),
        (TopologyFrontierOperation.EVIDENCE_PUBLICATION, "D09-P06"),
    ):
        rows = tuple(item for item in evaluation.receipts if item.operation is operation)
        add(f"{operation.value}:coverage", rule_id, None, len(rows) == 4, "operation has one positive and three controls")
        add(f"{operation.value}:context", "D09-P02", None, all(item.context_key == fixture.context_key for item in rows), "operation receipts retain exact context")
    add("research-scope", "D09-P07", None, True, "fixture is research evidence only")
    add("aggregate-scope", "D09-P08", None, fixture.evidence_boundary == TOPOLOGY_FRONTIER_EVIDENCE_BOUNDARY, "aggregate boundary is retained")
    body = {"fixture_id": fixture.fixture_id, "boundary": fixture.evidence_boundary, "context_key": fixture.context_key, "rules": selected_rules, "checks": checks}
    return TopologyFrontierPolicyReport(fixture.fixture_id, fixture.evidence_boundary, fixture.context_key, selected_rules, tuple(checks), content_hash(body))


__all__ = [
    "TopologyFrontierPolicyCheck",
    "TopologyFrontierPolicyReport",
    "TopologyFrontierPolicyRule",
    "default_topology_frontier_policy_rules",
    "evaluate_topology_frontier_policy",
]
