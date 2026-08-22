"""Scope and interpretation policy for Domain 08 cell-state evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cell_state_frontier_fixture_eval import (
    CellStateFrontierEvaluationReport,
    evaluate_cell_state_frontier_fixture,
)
from .cell_state_frontier_public_data import (
    CELL_STATE_FRONTIER_CONTEXT_KEY,
    CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY,
    CellStateFrontierFixture,
    CellStateFrontierOperation,
    default_cell_state_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


class CellStateFrontierPolicyDisposition(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class CellStateFrontierPolicyRule:
    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: CellStateFrontierPolicyDisposition
    applies_to: tuple[CellStateFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "title", "requirement", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.applies_to:
            raise ValueError("cell state policy rule requires operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierPolicyCheck:
    rule_id: str
    passed: bool
    disposition: CellStateFrontierPolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierPolicyReport:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[CellStateFrontierPolicyRule, ...]
    checks: tuple[CellStateFrontierPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            item.passed and item.disposition is CellStateFrontierPolicyDisposition.PASS
            for item in self.checks
        )

    @property
    def failed_rule_ids(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_rule_ids": list(self.failed_rule_ids),
        }


def _rule(
    rule_id: str,
    title: str,
    requirement: str,
    disposition: CellStateFrontierPolicyDisposition,
    applies_to: tuple[CellStateFrontierOperation, ...],
) -> CellStateFrontierPolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return CellStateFrontierPolicyRule(**body, content_address=content_hash(body))


def default_cell_state_frontier_policy_rules() -> tuple[CellStateFrontierPolicyRule, ...]:
    all_operations = tuple(CellStateFrontierOperation)
    return (
        _rule("scope-public-aggregate", "Public aggregate scope", "fixture is public aggregate non-patient evidence", CellStateFrontierPolicyDisposition.DENY, all_operations),
        _rule("context-exact", "Exact context", "positive records retain the declared exact context", CellStateFrontierPolicyDisposition.DENY, all_operations),
        _rule("source-closure", "Source closure", "every record source resolves to a receipt", CellStateFrontierPolicyDisposition.DENY, all_operations),
        _rule("no-subject-identifiers", "Aggregate identifiers only", "payloads contain no subject-level identifiers", CellStateFrontierPolicyDisposition.DENY, all_operations),
        _rule("positive-state-floor", "Positive state floor", "positive records are supported", CellStateFrontierPolicyDisposition.REVIEW, all_operations),
        _rule("controls-visible", "Controls visible", "controls remain non-supported review outcomes", CellStateFrontierPolicyDisposition.REVIEW, all_operations),
        _rule("parser-no-fetch", "No raw fetch", "receipts retain summaries without raw input text", CellStateFrontierPolicyDisposition.DENY, all_operations),
        _rule("abundance-not-clinical", "Abundance is bounded", "interval estimates are descriptive abundance evidence", CellStateFrontierPolicyDisposition.DENY, (CellStateFrontierOperation.ABUNDANCE_INTERVAL,)),
        _rule("mapping-not-diagnostic", "Mapping is descriptive", "reference mapping is not a diagnostic label", CellStateFrontierPolicyDisposition.DENY, (CellStateFrontierOperation.REFERENCE_MAPPING,)),
        _rule("ood-not-diagnosis", "OOD is bounded", "out-of-domain review is not a diagnosis", CellStateFrontierPolicyDisposition.DENY, (CellStateFrontierOperation.OOD_DETECTION,)),
        _rule("publisher-terms-visible", "Publisher terms visible", "publication retains upstream receipt addresses", CellStateFrontierPolicyDisposition.DENY, (CellStateFrontierOperation.CONTEXT_PUBLICATION,)),
        _rule("missing-not-negative", "Missing is not negative", "missing values remain partial without negative inference", CellStateFrontierPolicyDisposition.DENY, all_operations),
    )


def _contains_key(value: Any, prohibited: set[str]) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in prohibited or _contains_key(item, prohibited) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_key(item, prohibited) for item in value)
    return False


def evaluate_cell_state_frontier_policy(
    fixture: CellStateFrontierFixture | None = None,
    evaluation: CellStateFrontierEvaluationReport | None = None,
    *,
    rules: tuple[CellStateFrontierPolicyRule, ...] | None = None,
) -> CellStateFrontierPolicyReport:
    selected = fixture or default_cell_state_frontier_fixture()
    report = evaluation or evaluate_cell_state_frontier_fixture(selected)
    selected_rules = rules or default_cell_state_frontier_policy_rules()
    source_ids = set(selected.source_map())
    checks: list[CellStateFrontierPolicyCheck] = []

    def add(rule: CellStateFrontierPolicyRule, passed: bool, detail: str) -> None:
        disposition = CellStateFrontierPolicyDisposition.PASS if passed else rule.disposition_on_failure
        body = {"rule_id": rule.rule_id, "passed": passed, "disposition": disposition, "detail": detail}
        checks.append(CellStateFrontierPolicyCheck(**body, content_address=content_hash(body)))

    for rule in selected_rules:
        if rule.rule_id == "scope-public-aggregate":
            add(rule, selected.evidence_boundary == CELL_STATE_FRONTIER_EVIDENCE_BOUNDARY, "public aggregate boundary")
        elif rule.rule_id == "context-exact":
            add(rule, selected.context_key == CELL_STATE_FRONTIER_CONTEXT_KEY and all(item.context_key == selected.context_key for item in selected.positive_records), "positive context is exact")
        elif rule.rule_id == "source-closure":
            add(rule, all(source_id in source_ids for item in selected.records for source_id in item.source_ids), "every record source resolves")
        elif rule.rule_id == "no-subject-identifiers":
            add(rule, not any(_contains_key(item.payload, {"patient", "subject", "donor", "participant"}) for item in selected.records), "payloads are aggregate scoped")
        elif rule.rule_id == "positive-state-floor":
            add(rule, report.accepted and all(item.adapter_state == "supported" for item in report.receipts if item.role.value == "positive"), "positive states are supported")
        elif rule.rule_id == "controls-visible":
            add(rule, all(item.adapter_state != "supported" for item in report.receipts if item.role.value == "control"), "control states remain visible")
        elif rule.rule_id == "parser-no-fetch":
            add(rule, all("input_text" not in item.summary for item in report.receipts), "summaries exclude raw input")
        elif rule.rule_id == "abundance-not-clinical":
            add(rule, all("clinical" not in str(item.summary).lower() for item in report.receipts if item.operation is CellStateFrontierOperation.ABUNDANCE_INTERVAL), "abundance remains descriptive")
        elif rule.rule_id == "mapping-not-diagnostic":
            add(rule, all("diagnostic" not in str(item.summary).lower() for item in report.receipts if item.operation is CellStateFrontierOperation.REFERENCE_MAPPING), "mapping remains descriptive")
        elif rule.rule_id == "ood-not-diagnosis":
            add(rule, all("diagnosis" not in str(item.summary).lower() for item in report.receipts if item.operation is CellStateFrontierOperation.OOD_DETECTION), "OOD remains bounded")
        elif rule.rule_id == "publisher-terms-visible":
            add(rule, all(item.summary.get("receipt_count") == 3 for item in report.receipts if item.operation is CellStateFrontierOperation.CONTEXT_PUBLICATION and item.adapter_state == "supported"), "publication retains three upstream terms")
        elif rule.rule_id == "missing-not-negative":
            add(rule, all(item.adapter_state != "supported" for item in report.receipts if item.role.value == "control"), "controls do not become negative claims")
        else:
            add(rule, False, "unknown policy rule")
    body = {"fixture_id": selected.fixture_id, "context_key": selected.context_key, "evidence_boundary": selected.evidence_boundary, "rules": selected_rules, "checks": checks}
    return CellStateFrontierPolicyReport(selected.fixture_id, selected.context_key, selected.evidence_boundary, selected_rules, tuple(checks), content_hash(body))


__all__ = [
    "CellStateFrontierPolicyCheck",
    "CellStateFrontierPolicyDisposition",
    "CellStateFrontierPolicyReport",
    "CellStateFrontierPolicyRule",
    "default_cell_state_frontier_policy_rules",
    "evaluate_cell_state_frontier_policy",
]
