"""Combined quality gate for public aggregate Domain 01 variation evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .variation_contracts import default_variation_contract_registry
from .variation_fixture_eval import (
    VariationFixtureEvaluator,
)
from .variation_public_data import (
    VariationDataState,
    VariationFixtureCatalog,
    VariationRecordKind,
    audit_variation_fixture,
)
from .variation_replay import (
    VariationReplayExpectation,
    VariationReplayRunner,
)
from .variation_scenario_matrix import evaluate_variation_scenarios


@dataclass(frozen=True, slots=True)
class VariationQualityCheck:
    """One repository-level variation evidence assertion."""

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
class VariationQualityGateReport:
    """Reconciled evidence result for one variation fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    component_receipts: Mapping[str, Mapping[str, Any]]
    checks: tuple[VariationQualityCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    evidence_boundary: str
    state: VariationDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == VariationDataState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class VariationQualityGate:
    """Reconcile fixture evaluation, data audit, and replay integrity."""

    expected_record_count = 5
    expected_negative_control_count = 5
    expected_fixture_checks = 29
    expected_scenario_count = 10
    expected_contract_count = 5

    def __init__(
        self,
        *,
        evaluator: VariationFixtureEvaluator | None = None,
        replay_runner: VariationReplayRunner | None = None,
    ) -> None:
        self.evaluator = evaluator or VariationFixtureEvaluator()
        self.replay_runner = replay_runner or VariationReplayRunner(self.evaluator)

    def evaluate_file(self, path: str | Path) -> VariationQualityGateReport:
        raw = self.evaluator.load_file(path)
        fixture_report = self.evaluator.evaluate(raw)
        catalog = VariationFixtureCatalog.from_fixture(raw)
        data_report = audit_variation_fixture(path)
        expectation = VariationReplayExpectation(
            fixture_id=fixture_report.fixture_id,
            context_key=fixture_report.context_key,
            source_ids=fixture_report.source_ids,
            minimum_checks=self.expected_fixture_checks,
        )
        replay_report = self.replay_runner.replay(
            [path],
            expectations={str(path): expectation},
            required_context_key=fixture_report.context_key,
        )
        scenario_report = evaluate_variation_scenarios(path)
        contract_manifest = default_variation_contract_registry().manifest()
        repeated = self.evaluator.evaluate(raw)
        checks: list[VariationQualityCheck] = []
        self._add(
            checks,
            "fixture-evaluation",
            "variation fixture evaluation is accepted",
            {"state": fixture_report.state.value, "check_count": len(fixture_report.checks)},
            fixture_report.passed,
            "all five positive adapters and five negative controls were executed",
        )
        self._add(
            checks,
            "fixture-check-floor",
            f"at least {self.expected_fixture_checks} checks are present",
            len(fixture_report.checks),
            len(fixture_report.checks) >= self.expected_fixture_checks,
            "the evidence floor prevents a reduced fixture from passing silently",
        )
        self._add(
            checks,
            "public-data-audit",
            "public aggregate data audit is accepted",
            {"state": data_report.state.value, "issues": len(data_report.issues)},
            data_report.accepted,
            "source scope, exact context, duplicate identity, and sensitive paths are audited",
        )
        self._add(
            checks,
            "replay-integrity",
            "fixture identity, context, sources, and state replay cleanly",
            {"state": replay_report.state.value, "issues": replay_report.integrity_issues},
            replay_report.passed,
            "a checked-in fixture can be replayed with an exact expected contract",
        )
        self._add(
            checks,
            "record-count",
            f"exactly {self.expected_record_count} positive record kinds are present",
            {
                "count": len(catalog.records),
                "kinds": tuple(sorted(record.kind.value for record in catalog.records)),
            },
            len(catalog.records) == self.expected_record_count
            and {record.kind for record in catalog.records}
            == set(VariationRecordKind),
            "each D01 variation adapter has a dedicated public aggregate input",
        )
        self._add(
            checks,
            "negative-control-count",
            f"exactly {self.expected_negative_control_count} review controls are present",
            len(fixture_report.negative_reports),
            len(fixture_report.negative_reports) == self.expected_negative_control_count,
            "unsupported, ambiguous, and out-of-domain states remain explicit",
        )
        self._add(
            checks,
            "scenario-matrix",
            f"exactly {self.expected_scenario_count} positive/review scenarios pass",
            {
                "count": len(scenario_report.results),
                "state": scenario_report.state.value,
                "failed": scenario_report.failed_scenario_ids,
            },
            len(scenario_report.results) == self.expected_scenario_count
            and scenario_report.passed,
            "independent state-transition execution agrees with the fixture evaluator",
        )
        contract_operations = {
            contract["operation"] for contract in contract_manifest["contracts"]
        }
        fixture_operations = {record.operation for record in catalog.records}
        self._add(
            checks,
            "contract-inventory",
            (
                f"exactly {self.expected_contract_count} variation operation contracts "
                "cover the fixture"
            ),
            {
                "contract_count": contract_manifest["contract_count"],
                "missing_operations": tuple(sorted(contract_operations - fixture_operations)),
                "unexpected_operations": tuple(sorted(fixture_operations - contract_operations)),
            },
            contract_manifest["contract_count"] == self.expected_contract_count
            and contract_operations == fixture_operations,
            "each positive fixture record maps to one declarative operation contract",
        )
        self._add(
            checks,
            "context-consistency",
            "fixture, data, and replay receipts share the exact context key",
            {
                "fixture": fixture_report.context_key,
                "data": data_report.context_key,
                "replay": replay_report.context_keys,
            },
            (
                fixture_report.context_key == data_report.context_key
                and replay_report.context_keys == (fixture_report.context_key,)
            ),
            "variation results are not compared across different biological contexts",
        )
        self._add(
            checks,
            "source-consistency",
            "fixture, data, and replay receipts share the source set",
            {
                "fixture": fixture_report.source_ids,
                "data": data_report.source_ids,
                "replay": replay_report.source_ids,
            },
            (
                fixture_report.source_ids == data_report.source_ids
                and fixture_report.source_ids == replay_report.source_ids
            ),
            "source identity remains stable across all evidence components",
        )
        self._add(
            checks,
            "deterministic-evaluation",
            "repeated evaluation produces one fixture content address",
            {"first": fixture_report.content_address, "second": repeated.content_address},
            fixture_report.content_address == repeated.content_address,
            "content-addressed results are comparable between local runs and CI",
        )
        serialized = json.dumps(fixture_report.to_dict(), sort_keys=True).casefold()
        self._add(
            checks,
            "output-boundary",
            "serialized fixture output contains no restricted fields",
            {
                "restricted_output": any(
                    word in serialized for word in ("patient_id", "mrn", "secret")
                )
            },
            not any(word in serialized for word in ("patient_id", "mrn", "secret")),
            "public aggregate receipts do not copy restricted values into output",
        )
        passed_ids = tuple(check.check_id for check in checks if check.passed)
        failed_ids = tuple(check.check_id for check in checks if not check.passed)
        state = VariationDataState.ACCEPTED if not failed_ids else VariationDataState.REVIEW
        boundary = require_non_empty(fixture_report.evidence_boundary, "evidence_boundary")
        components = {
            "fixture": fixture_report.to_dict(),
            "data": data_report.to_dict(),
            "replay": replay_report.to_dict(),
            "scenarios": scenario_report.to_dict(),
            "contracts": contract_manifest,
        }
        return VariationQualityGateReport(
            fixture_report.fixture_id,
            fixture_report.fixture_version,
            fixture_report.context_key,
            fixture_report.source_ids,
            components,
            tuple(checks),
            passed_ids,
            failed_ids,
            boundary,
            state,
            content_hash({"components": components, "checks": checks}),
        )

    @staticmethod
    def _add(
        checks: list[VariationQualityCheck],
        check_id: str,
        requirement: str,
        observed: Any,
        passed: bool,
        detail: str,
    ) -> None:
        checks.append(VariationQualityCheck(check_id, requirement, observed, bool(passed), detail))


def evaluate_variation_quality_gate(path: str | Path) -> VariationQualityGateReport:
    """Convenience function for the CI-facing variation quality gate."""

    return VariationQualityGate().evaluate_file(path)


__all__ = [
    "VariationQualityCheck",
    "VariationQualityGate",
    "VariationQualityGateReport",
    "evaluate_variation_quality_gate",
]
