"""Repository-level quality gate for the checked-in frontier evidence slice.

The operation registry, public-data audit, fixture evaluator, replay runner,
and scenario matrix each answer a different question. This module composes
their receipts into one verdict without hiding the individual boundaries. A
quality-gate report is intentionally summary-shaped: it carries enough detail
to diagnose a failed build while never copying fixture secrets into output.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .frontier_contracts import default_frontier_contract_registry
from .frontier_fixture_eval import FrontierFixtureEvaluator
from .frontier_public_data import audit_public_fixture
from .frontier_replay import FrontierReplayRunner, ReplayExpectation
from .frontier_scenario_matrix import evaluate_frontier_scenarios
from .serialization import content_hash, jsonable, require_non_empty


class QualityGateState(StrEnum):
    """Top-level quality-gate states."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class QualityGateCheck:
    """One independently inspectable repository quality assertion."""

    check_id: str
    requirement: str
    observed: Any
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.requirement, "requirement")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierQualityGateReport:
    """Combined evidence verdict for one public frontier fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    component_receipts: Mapping[str, Mapping[str, Any]]
    checks: tuple[QualityGateCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    evidence_boundary: str
    state: QualityGateState
    content_address: str

    @property
    def passed(self) -> bool:
        """Return whether every required quality assertion passed."""

        return self.state == QualityGateState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class FrontierQualityGate:
    """Run and reconcile all repository-level frontier evidence receipts."""

    expected_contract_count = 79
    expected_capability_count = 16
    expected_fixture_checks = 49
    expected_review_scenarios = 4

    def __init__(
        self,
        *,
        evaluator: FrontierFixtureEvaluator | None = None,
        replay_runner: FrontierReplayRunner | None = None,
    ) -> None:
        self.evaluator = evaluator or FrontierFixtureEvaluator()
        self.replay_runner = replay_runner or FrontierReplayRunner(self.evaluator)

    @staticmethod
    def _fixture_metadata(fixture: Mapping[str, Any]) -> tuple[str, str, str]:
        fixture_id_value = fixture.get("fixture_id")
        fixture_version_value = fixture.get("fixture_version")
        if not isinstance(fixture_id_value, str) or not isinstance(fixture_version_value, str):
            raise ValidationError("fixture_id and fixture_version must be strings")
        fixture_id = require_non_empty(fixture_id_value, "fixture_id")
        fixture_version = require_non_empty(fixture_version_value, "fixture_version")
        context = fixture.get("context")
        if not isinstance(context, Mapping):
            raise ValidationError("quality-gate fixture context must be an object")
        fields = (
            "genome_build",
            "disease_class",
            "age_group",
            "cell_state",
            "territory",
            "treatment_phase",
        )
        values = tuple(
            require_non_empty(str(context.get(field, "")), f"context.{field}")
            for field in fields
        )
        return fixture_id, fixture_version, "|".join(values)

    @staticmethod
    def _add_check(
        checks: list[QualityGateCheck],
        check_id: str,
        requirement: str,
        observed: Any,
        passed: bool,
        detail: str,
    ) -> None:
        checks.append(QualityGateCheck(check_id, requirement, observed, bool(passed), detail))

    def evaluate_file(self, path: str | Path) -> FrontierQualityGateReport:
        """Evaluate a UTF-8 JSON fixture and reconcile all component receipts."""

        fixture = self.evaluator.load_file(path)
        return self.evaluate(fixture, fixture_path=path)

    def evaluate(
        self,
        fixture: Mapping[str, Any],
        *,
        fixture_path: str | Path | None = None,
    ) -> FrontierQualityGateReport:
        """Evaluate an already loaded fixture without emitting raw input data."""

        fixture_id, fixture_version, context_key = self._fixture_metadata(fixture)
        fixture_report = self.evaluator.evaluate(fixture)
        data_report = (
            audit_public_fixture(fixture_path)
            if fixture_path
            else self._audit_fixture(fixture)
        )
        replay_expectation = ReplayExpectation(
            fixture_id=fixture_id,
            context_key=context_key,
            source_ids=fixture_report.source_ids,
            minimum_checks=self.expected_fixture_checks,
        )
        if fixture_path is None:
            with tempfile.TemporaryDirectory(prefix="glio-frontier-gate-") as directory:
                temporary_path = Path(directory) / "fixture.json"
                temporary_path.write_text(json.dumps(fixture), encoding="utf-8")
                replay_report = self.replay_runner.replay(
                    [temporary_path],
                    expectations={str(temporary_path): replay_expectation},
                    required_context_key=context_key,
                )
        else:
            replay_report = self.replay_runner.replay(
                [fixture_path],
                expectations={str(fixture_path): replay_expectation},
                required_context_key=context_key,
            )
        scenario_report = (
            evaluate_frontier_scenarios(fixture_path)
            if fixture_path
            else self._evaluate_scenarios_in_memory(fixture)
        )
        contracts = default_frontier_contract_registry().manifest()
        checks: list[QualityGateCheck] = []
        self._add_check(
            checks,
            "fixture-evaluation",
            "all declared fixture checks pass",
            {"state": fixture_report.state.value, "check_count": len(fixture_report.checks)},
            fixture_report.passed,
            "positive operations, hardening operations, and negative controls were evaluated",
        )
        self._add_check(
            checks,
            "fixture-check-floor",
            f"at least {self.expected_fixture_checks} fixture checks are present",
            len(fixture_report.checks),
            len(fixture_report.checks) >= self.expected_fixture_checks,
            "the evidence floor prevents an accidentally reduced fixture from passing",
        )
        self._add_check(
            checks,
            "public-data-audit",
            "public fixture records have accepted quality state",
            {"state": data_report.state.value, "record_count": data_report.record_count},
            data_report.accepted,
            "identifiers, source receipts, exact context, and sensitive paths were audited",
        )
        self._add_check(
            checks,
            "replay-integrity",
            "fixture replay matches identity, context, sources, and evidence floor",
            {"state": replay_report.state.value, "issues": replay_report.integrity_issues},
            replay_report.passed,
            "the checked-in fixture can be replayed with a stable expected contract",
        )
        self._add_check(
            checks,
            "scenario-matrix",
            "all positive and negative state transitions pass",
            {
                "state": scenario_report.state.value,
                "scenario_count": len(scenario_report.results),
                "failed": scenario_report.failed_scenario_ids,
            },
            scenario_report.passed,
            "accepted pipelines and review controls retain their declared boundaries",
        )
        self._add_check(
            checks,
            "scenario-review-floor",
            f"exactly {self.expected_review_scenarios} declared review scenarios are present",
            len(scenario_report.review_scenario_ids),
            len(scenario_report.review_scenario_ids) == self.expected_review_scenarios,
            "negative controls remain visible instead of being silently discarded",
        )
        self._add_check(
            checks,
            "contract-count",
            f"exactly {self.expected_contract_count} operation contracts are registered",
            contracts["contract_count"],
            contracts["contract_count"] == self.expected_contract_count,
            "the operation inventory is complete for the current frontier slice",
        )
        self._add_check(
            checks,
            "capability-count",
            f"exactly {self.expected_capability_count} release capability IDs are mapped",
            len(contracts["capability_ids"]),
            len(contracts["capability_ids"]) == self.expected_capability_count,
            "release operation adapters map to the sixteen capability receipts",
        )
        self._add_check(
            checks,
            "context-consistency",
            "all component receipts use one exact context key",
            {
                "fixture": fixture_report.context_key,
                "data": data_report.context_key,
                "replay": replay_report.context_keys,
                "scenario": scenario_report.context_key,
            },
            (
                fixture_report.context_key == context_key
                and data_report.context_key == context_key
                and replay_report.context_keys == (context_key,)
                and scenario_report.context_key == context_key
            ),
            "context drift would invalidate comparisons across component receipts",
        )
        self._add_check(
            checks,
            "source-consistency",
            "all component receipts use the fixture source set",
            {
                "fixture": fixture_report.source_ids,
                "data": data_report.source_ids,
                "replay": replay_report.source_ids,
            },
            (
                fixture_report.source_ids == data_report.source_ids
                and replay_report.source_ids == fixture_report.source_ids
            ),
            "source receipts must remain stable across evaluation, audit, and replay",
        )
        repeated = self.evaluator.evaluate(fixture)
        self._add_check(
            checks,
            "deterministic-evaluation",
            "repeated fixture evaluation produces one content address",
            {"first": fixture_report.content_address, "second": repeated.content_address},
            fixture_report.content_address == repeated.content_address,
            "content-addressed receipts make local and CI results comparable",
        )
        serialized = json.dumps(fixture_report.to_dict(), sort_keys=True)
        self._add_check(
            checks,
            "secret-output-boundary",
            "evaluation output does not expose the fixture signing secret",
            {"contains_secret": "fixture-signing-secret-v1" in serialized},
            "fixture-signing-secret-v1" not in serialized,
            "cryptographic test material remains an input-only concern",
        )
        passed_ids = tuple(check.check_id for check in checks if check.passed)
        failed_ids = tuple(check.check_id for check in checks if not check.passed)
        state = QualityGateState.ACCEPTED if not failed_ids else QualityGateState.REVIEW
        boundary = require_non_empty(fixture_report.evidence_boundary, "evidence_boundary")
        components = {
            "fixture": {
                "state": fixture_report.state.value,
                "passed": fixture_report.passed,
                "check_count": len(fixture_report.checks),
                "content_address": fixture_report.content_address,
            },
            "data": data_report.to_dict(),
            "replay": replay_report.to_dict(),
            "scenarios": scenario_report.to_dict(),
            "contracts": {
                "contract_count": contracts["contract_count"],
                "family_counts": contracts["family_counts"],
                "capability_ids": contracts["capability_ids"],
                "manifest_address": contracts["manifest_address"],
            },
        }
        address = content_hash(
            {
                "fixture_id": fixture_id,
                "fixture_version": fixture_version,
                "context_key": context_key,
                "source_ids": fixture_report.source_ids,
                "components": components,
                "checks": checks,
            }
        )
        return FrontierQualityGateReport(
            fixture_id,
            fixture_version,
            context_key,
            fixture_report.source_ids,
            components,
            tuple(checks),
            passed_ids,
            failed_ids,
            boundary,
            state,
            address,
        )

    @staticmethod
    def _audit_fixture(fixture: Mapping[str, Any]):
        from .frontier_public_data import PublicFixtureCatalog

        return PublicFixtureCatalog.from_fixture(fixture).audit()

    def _evaluate_scenarios_in_memory(self, fixture: Mapping[str, Any]):
        return evaluate_frontier_scenarios_from_mapping(fixture)


def evaluate_frontier_scenarios_from_mapping(fixture: Mapping[str, Any]):
    """Evaluate scenarios without requiring a temporary fixture file."""

    from .frontier_scenario_matrix import FrontierScenarioMatrix

    return FrontierScenarioMatrix(fixture).run()


def evaluate_frontier_quality_gate(path: str | Path) -> FrontierQualityGateReport:
    """Convenience function for the repository quality-gate command."""

    return FrontierQualityGate().evaluate_file(path)


__all__ = [
    "FrontierQualityGate",
    "FrontierQualityGateReport",
    "QualityGateCheck",
    "QualityGateState",
    "evaluate_frontier_quality_gate",
    "evaluate_frontier_scenarios_from_mapping",
]
