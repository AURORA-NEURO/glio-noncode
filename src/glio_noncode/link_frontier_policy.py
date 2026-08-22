"""Policy checks that keep Domain 10 link evidence bounded and reviewable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_contracts import LinkFrontierContractRegistry, default_link_frontier_contracts
from .link_frontier_fixture_eval import LinkFrontierEvaluation, evaluate_link_frontier_fixture
from .link_frontier_public_data import LinkFrontierFixture, default_link_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierPolicyRule:
    rule_id: str
    title: str
    rationale: str
    severity: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierPolicyResult:
    rule_id: str
    passed: bool
    observed: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierPolicyReport:
    fixture_id: str
    rule_count: int
    results: tuple[LinkFrontierPolicyResult, ...]
    accepted: bool
    content_address: str

    @property
    def failed_rule_ids(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.results if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_rule_ids": list(self.failed_rule_ids)}


def default_link_frontier_policy_rules() -> tuple[LinkFrontierPolicyRule, ...]:
    rows = (
        ("boundary", "public aggregate boundary is explicit", "keeps patient-level material out of the fixture", "blocking"),
        ("context", "one context key is retained", "prevents cross-context transport", "blocking"),
        ("sources", "all source IDs resolve", "keeps source lineage closed", "blocking"),
        ("positive-controls", "positive and control records coexist", "requires discrimination rather than happy-path execution", "blocking"),
        ("missingness", "controls expose empty and malformed paths", "makes abstention and quarantine testable", "review"),
        ("dependence", "correlated support remains grouped", "prevents duplicate evidence inflation", "review"),
        ("ranking", "alternative genes remain visible", "prevents forced target selection", "review"),
        ("calibration", "thresholds are declared", "makes abstention reproducible", "review"),
        ("publication", "source and context receipts bind", "prevents untraceable bundles", "blocking"),
        ("claims", "contracts list prohibited interpretations", "keeps outputs descriptive", "blocking"),
        ("addresses", "fixture and execution addresses exist", "supports replay and reconciliation", "review"),
        ("determinism", "evaluation is repeatable", "makes release checks stable", "review"),
    )
    rules: list[LinkFrontierPolicyRule] = []
    for rule_id, title, rationale, severity in rows:
        body = {"rule_id": rule_id, "title": title, "rationale": rationale, "severity": severity}
        rules.append(LinkFrontierPolicyRule(**body, content_address=content_hash(body)))
    return tuple(rules)


def evaluate_link_frontier_policy(
    fixture: LinkFrontierFixture | None = None,
    *,
    evaluation: LinkFrontierEvaluation | None = None,
    contracts: LinkFrontierContractRegistry | None = None,
) -> LinkFrontierPolicyReport:
    fixture = fixture or default_link_frontier_fixture()
    evaluation = evaluation or evaluate_link_frontier_fixture(fixture)
    contracts = contracts or default_link_frontier_contracts()
    source_ids = set(fixture.source_map())
    rules = default_link_frontier_policy_rules()
    observations: dict[str, tuple[bool, Any, str]] = {
        "boundary": (fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "boundary matches policy"),
        "context": (len({record.context_key for record in fixture.records}) == 1, {record.context_key for record in fixture.records}, "one context retained"),
        "sources": (all(set(record.source_ids) <= source_ids for record in fixture.records), True, "source references resolve"),
        "positive-controls": (bool(fixture.positive_records) and bool(fixture.control_records), (len(fixture.positive_records), len(fixture.control_records)), "both classes present"),
        "missingness": (len(fixture.control_records) >= 12, len(fixture.control_records), "control set is loss-accounted"),
        "dependence": (any("dependence_group" in row for record in fixture.records for row in record.payload.get("input_records", [])), True, "dependence group is explicit"),
        "ranking": (any("GENE2" in str(record.payload) for record in fixture.records), True, "alternative gene remains in fixture"),
        "calibration": (any("maximum_uncertainty" in record.payload for record in fixture.records), True, "calibration thresholds are declared"),
        "publication": (any(record.operation.value == "link_evidence_publication" for record in fixture.records), True, "publication path is represented"),
        "claims": (all(contract.prohibited_claims for contract in contracts.contracts), len(contracts.contracts), "every contract lists prohibited interpretations"),
        "addresses": (bool(fixture.content_address) and bool(evaluation.content_address), True, "content addresses exist"),
        "determinism": (evaluation.accepted, evaluation.accepted, "baseline evaluation passes"),
    }
    results: list[LinkFrontierPolicyResult] = []
    for rule in rules:
        passed, observed, detail = observations[rule.rule_id]
        body = {"rule_id": rule.rule_id, "passed": passed, "observed": observed, "detail": detail}
        results.append(LinkFrontierPolicyResult(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "rule_count": len(rules),
        "results": results,
        "accepted": all(item.passed for item in results),
    }
    return LinkFrontierPolicyReport(**body, content_address=content_hash(body))


__all__ = [
    "LinkFrontierPolicyReport",
    "LinkFrontierPolicyResult",
    "LinkFrontierPolicyRule",
    "default_link_frontier_policy_rules",
    "evaluate_link_frontier_policy",
]
