"""Scenario matrix for C09-C12 positive and review behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import (
    AtlasAlphaEvidenceEvaluationReport,
    evaluate_atlas_alpha_evidence_fixture,
)
from .atlas_alpha_evidence_public_data import (
    AtlasAlphaEvidenceOperation,
    AtlasAlphaEvidenceRole,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceScenario:
    scenario_id: str
    operation: AtlasAlphaEvidenceOperation
    record_id: str
    role: AtlasAlphaEvidenceRole
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    purpose: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.expected_state, "expected_state")
        require_non_empty(self.purpose, "purpose")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceScenarioCheck:
    scenario_id: str
    passed: bool
    detail: str
    observed_state: str
    observed_issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceScenarioReport:
    fixture_id: str
    scenarios: tuple[AtlasAlphaEvidenceScenario, ...]
    checks: tuple[AtlasAlphaEvidenceScenarioCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_scenarios(self) -> tuple[str, ...]:
        return tuple(check.scenario_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_scenarios": list(self.failed_scenarios),
        }


def default_atlas_alpha_evidence_scenarios() -> tuple[AtlasAlphaEvidenceScenario, ...]:
    """Return the explicit path/control matrix used in review."""

    definitions = (
        (
            "S-C09-supported",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            "C09-POS-001",
            AtlasAlphaEvidenceRole.POSITIVE,
            "supported",
            (),
            "concordant accessibility replicates",
        ),
        (
            "S-C09-invalid",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            "C09-CTRL-001",
            AtlasAlphaEvidenceRole.CONTROL,
            "partial",
            ("invalid_open_chromatin_row",),
            "missing signal remains an input issue",
        ),
        (
            "S-C09-ambiguous",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            "C09-CTRL-002",
            AtlasAlphaEvidenceRole.CONTROL,
            "ambiguous",
            ("open_chromatin_signal_disagreement",),
            "replicate signal disagreement",
        ),
        (
            "S-C10-supported",
            AtlasAlphaEvidenceOperation.METHYLATION,
            "C10-POS-001",
            AtlasAlphaEvidenceRole.POSITIVE,
            "supported",
            (),
            "covered methylation replicates",
        ),
        (
            "S-C10-zero-coverage",
            AtlasAlphaEvidenceOperation.METHYLATION,
            "C10-CTRL-001",
            AtlasAlphaEvidenceRole.CONTROL,
            "partial",
            ("methylation_zero_coverage",),
            "zero coverage is not unmethylated",
        ),
        (
            "S-C11-supported",
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            "C11-POS-001",
            AtlasAlphaEvidenceRole.POSITIVE,
            "supported",
            (),
            "complete role channels",
        ),
        (
            "S-C11-multi-role",
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            "C11-CTRL-002",
            AtlasAlphaEvidenceRole.CONTROL,
            "ambiguous",
            ("regulatory_role_ambiguity",),
            "multi-role classification",
        ),
        (
            "S-C12-supported",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            "C12-POS-001",
            AtlasAlphaEvidenceRole.POSITIVE,
            "supported",
            (),
            "ranked candidate with activity",
        ),
        (
            "S-C12-abstained",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            "C12-CTRL-001",
            AtlasAlphaEvidenceRole.CONTROL,
            "abstained",
            ("no_super_enhancer_candidate",),
            "constituent floor not met",
        ),
        (
            "S-C12-partial",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            "C12-CTRL-002",
            AtlasAlphaEvidenceRole.CONTROL,
            "partial",
            ("super_enhancer_partial_activity",),
            "candidate without declared activity",
        ),
    )
    result: list[AtlasAlphaEvidenceScenario] = []
    for scenario_id, operation, record_id, role, state, issues, purpose in definitions:
        body = {
            "scenario_id": scenario_id,
            "operation": operation,
            "record_id": record_id,
            "role": role,
            "expected_state": state,
            "expected_issue_codes": issues,
            "purpose": purpose,
        }
        result.append(AtlasAlphaEvidenceScenario(**body, content_address=content_hash(body)))
    return tuple(result)


def evaluate_atlas_alpha_evidence_scenarios(
    evaluation: AtlasAlphaEvidenceEvaluationReport | None = None,
) -> AtlasAlphaEvidenceScenarioReport:
    """Compare selected scenarios with a deterministic fixture evaluation."""

    current = evaluation or evaluate_atlas_alpha_evidence_fixture()
    receipt_map = {receipt.record_id: receipt for receipt in current.receipts}
    scenarios = default_atlas_alpha_evidence_scenarios()
    checks: list[AtlasAlphaEvidenceScenarioCheck] = []
    for scenario in scenarios:
        receipt = receipt_map.get(scenario.record_id)
        observed_state = receipt.adapter_state if receipt else "missing"
        observed_issues = receipt.observed_issue_codes if receipt else ("missing_receipt",)
        passed = (
            bool(receipt)
            and receipt.operation is scenario.operation
            and receipt.role is scenario.role
            and observed_state == scenario.expected_state
            and not set(scenario.expected_issue_codes) - set(observed_issues)
        )
        body = {
            "scenario_id": scenario.scenario_id,
            "passed": passed,
            "detail": scenario.purpose,
            "observed_state": observed_state,
            "observed_issue_codes": observed_issues,
        }
        checks.append(AtlasAlphaEvidenceScenarioCheck(**body, content_address=content_hash(body)))
    body = {"fixture_id": current.fixture_id, "scenarios": scenarios, "checks": checks}
    return AtlasAlphaEvidenceScenarioReport(
        current.fixture_id, scenarios, tuple(checks), content_hash(body)
    )


__all__ = [
    "AtlasAlphaEvidenceScenario",
    "AtlasAlphaEvidenceScenarioCheck",
    "AtlasAlphaEvidenceScenarioReport",
    "default_atlas_alpha_evidence_scenarios",
    "evaluate_atlas_alpha_evidence_scenarios",
]
