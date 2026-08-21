"""Positive and review scenario matrix for C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_fixture_eval import (
    FrontierAtlasEvaluationReport,
    evaluate_frontier_atlas_fixture,
)
from .frontier_atlas_public_data import FrontierAtlasOperation, FrontierAtlasRole
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasScenario:
    scenario_id: str
    operation: FrontierAtlasOperation
    record_id: str
    role: FrontierAtlasRole
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    purpose: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("scenario_id", "record_id", "expected_state", "purpose"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasScenarioCheck:
    scenario_id: str
    passed: bool
    detail: str
    observed_state: str
    observed_issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasScenarioReport:
    fixture_id: str
    scenarios: tuple[FrontierAtlasScenario, ...]
    checks: tuple[FrontierAtlasScenarioCheck, ...]
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


def default_frontier_atlas_scenarios() -> tuple[FrontierAtlasScenario, ...]:
    definitions = (
        (
            "S-C13-accepted",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            "C13-POS-001",
            FrontierAtlasRole.POSITIVE,
            "accepted",
            (),
            "supported boundary",
        ),
        (
            "S-C13-low-support",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            "C13-CTRL-001",
            FrontierAtlasRole.CONTROL,
            "review",
            ("boundary_low_support",),
            "low boundary support",
        ),
        (
            "S-C13-invalid-interval",
            FrontierAtlasOperation.BOUNDARY_ATLAS,
            "C13-CTRL-002",
            FrontierAtlasRole.CONTROL,
            "review",
            ("invalid_boundary_interval",),
            "invalid boundary interval",
        ),
        (
            "S-C14-accepted",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            "C14-POS-001",
            FrontierAtlasRole.POSITIVE,
            "accepted",
            (),
            "independent concordant hotspot sources",
        ),
        (
            "S-C14-source-floor",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            "C14-CTRL-001",
            FrontierAtlasRole.CONTROL,
            "review",
            ("insufficient_hotspot_sources",),
            "insufficient source floor",
        ),
        (
            "S-C14-disagreement",
            FrontierAtlasOperation.HOTSPOT_ATLAS,
            "C14-CTRL-002",
            FrontierAtlasRole.CONTROL,
            "review",
            ("hotspot_direction_disagreement",),
            "direction disagreement",
        ),
        (
            "S-C15-high",
            FrontierAtlasOperation.EVIDENCE_TIER,
            "C15-POS-001",
            FrontierAtlasRole.POSITIVE,
            "accepted",
            (),
            "high evidence tier",
        ),
        (
            "S-C15-low",
            FrontierAtlasOperation.EVIDENCE_TIER,
            "C15-CTRL-001",
            FrontierAtlasRole.CONTROL,
            "review",
            ("low_evidence_tier",),
            "low evidence tier",
        ),
        (
            "S-C15-no-source",
            FrontierAtlasOperation.EVIDENCE_TIER,
            "C15-CTRL-002",
            FrontierAtlasRole.CONTROL,
            "review",
            ("no_evidence_sources",),
            "no evidence sources",
        ),
        (
            "S-C16-published",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            "C16-POS-001",
            FrontierAtlasRole.POSITIVE,
            "published",
            (),
            "published context-qualified snapshot",
        ),
        (
            "S-C16-empty",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            "C16-CTRL-001",
            FrontierAtlasRole.CONTROL,
            "abstained",
            ("empty_snapshot_records",),
            "empty snapshot abstention",
        ),
        (
            "S-C16-invalid-metadata",
            FrontierAtlasOperation.SNAPSHOT_PUBLISH,
            "C16-CTRL-003",
            FrontierAtlasRole.CONTROL,
            "invalid",
            ("snapshot_metadata_invalid",),
            "invalid snapshot metadata",
        ),
    )
    scenarios: list[FrontierAtlasScenario] = []
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
        scenarios.append(FrontierAtlasScenario(**body, content_address=content_hash(body)))
    return tuple(scenarios)


def evaluate_frontier_atlas_scenarios(
    evaluation: FrontierAtlasEvaluationReport | None = None,
) -> FrontierAtlasScenarioReport:
    current = evaluation or evaluate_frontier_atlas_fixture()
    receipt_map = {item.record_id: item for item in current.receipts}
    scenarios = default_frontier_atlas_scenarios()
    checks: list[FrontierAtlasScenarioCheck] = []
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
        checks.append(FrontierAtlasScenarioCheck(**body, content_address=content_hash(body)))
    body = {"fixture_id": current.fixture_id, "scenarios": scenarios, "checks": checks}
    return FrontierAtlasScenarioReport(
        current.fixture_id, scenarios, tuple(checks), content_hash(body)
    )


__all__ = [
    "FrontierAtlasScenario",
    "FrontierAtlasScenarioCheck",
    "FrontierAtlasScenarioReport",
    "default_frontier_atlas_scenarios",
    "evaluate_frontier_atlas_scenarios",
]
