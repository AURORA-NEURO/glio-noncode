"""Combined quality gate for the Domain 01 intake evidence stack."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .intake_contracts import default_intake_contract_registry
from .intake_fixture_eval import IntakeFixtureEvaluator
from .intake_public_data import (
    IntakeDataState,
    IntakeFixtureCatalog,
    IntakeRecordKind,
    audit_intake_fixture,
)
from .intake_replay import IntakeReplayExpectation, IntakeReplayRunner
from .intake_scenario_matrix import evaluate_intake_scenarios
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class IntakeQualityCheck:
    """One repository-level intake evidence assertion."""

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
class IntakeQualityGateReport:
    """Reconciled data, operation, replay, scenario, and contract verdict."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    component_receipts: Mapping[str, Mapping[str, Any]]
    checks: tuple[IntakeQualityCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    evidence_boundary: str
    state: IntakeDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IntakeDataState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class IntakeQualityGate:
    """Reconcile all evidence components with explicit floors and invariants."""

    expected_record_count = 4
    expected_negative_control_count = 8
    expected_fixture_checks = 33
    expected_scenario_count = 12
    expected_contract_count = 4

    def __init__(
        self,
        *,
        evaluator: IntakeFixtureEvaluator | None = None,
        replay_runner: IntakeReplayRunner | None = None,
    ) -> None:
        self.evaluator = evaluator or IntakeFixtureEvaluator()
        self.replay_runner = replay_runner or IntakeReplayRunner(self.evaluator)

    def evaluate_file(self, path: str | Path) -> IntakeQualityGateReport:
        raw = self.evaluator.load_file(path)
        fixture_report = self.evaluator.evaluate(raw)
        catalog = IntakeFixtureCatalog.from_fixture(raw)
        data_report = audit_intake_fixture(path)
        expectation = IntakeReplayExpectation(
            fixture_id=fixture_report.fixture_id,
            context_key=fixture_report.context_key,
            source_ids=fixture_report.source_ids,
            minimum_checks=self.expected_fixture_checks,
            minimum_positive_records=self.expected_record_count,
            minimum_negative_controls=self.expected_negative_control_count,
        )
        replay_report = self.replay_runner.replay(
            [path],
            expectation=expectation,
            required_context_key=fixture_report.context_key,
        )
        scenario_report = evaluate_intake_scenarios(path)
        contract_manifest = default_intake_contract_registry().manifest()
        repeated = self.evaluator.evaluate(raw)
        checks: list[IntakeQualityCheck] = []
        self._add(
            checks,
            "fixture-evaluation",
            "intake fixture evaluation is accepted",
            {"state": fixture_report.state.value, "check_count": len(fixture_report.checks)},
            fixture_report.passed,
            "all four positive adapters and every negative control executed",
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
            "public policy and aggregate data audit is accepted",
            {"state": data_report.state.value, "issues": len(data_report.issues)},
            data_report.accepted,
            "source scope, exact context, duplicate identity, and sensitive paths are audited",
        )
        self._add(
            checks,
            "replay-integrity",
            "fixture identity, context, sources, and floors replay cleanly",
            {"state": replay_report.state.value, "issues": replay_report.integrity_issues},
            replay_report.passed,
            "the checked-in fixture can be replayed with an exact evidence expectation",
        )
        self._add(
            checks,
            "positive-record-count",
            f"exactly {self.expected_record_count} positive operation records are present",
            {
                "count": len(catalog.records),
                "kinds": tuple(sorted(record.kind.value for record in catalog.records)),
            },
            len(catalog.records) == self.expected_record_count
            and {record.kind for record in catalog.records} == set(IntakeRecordKind),
            "each C13-C16 adapter has a dedicated public input envelope",
        )
        self._add(
            checks,
            "negative-control-count",
            f"exactly {self.expected_negative_control_count} review controls are present",
            len(catalog.controls),
            len(catalog.controls) == self.expected_negative_control_count,
            "consent, anomaly, completeness, and export boundaries all have controls",
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
            "independent state-transition execution agrees with fixture evaluation",
        )
        contract_operations = {
            contract["operation"] for contract in contract_manifest["contracts"]
        }
        fixture_operations = {record.operation for record in catalog.records}
        self._add(
            checks,
            "contract-inventory",
            f"exactly {self.expected_contract_count} intake operation contracts are covered",
            {
                "contract_count": contract_manifest["contract_count"],
                "missing_operations": tuple(sorted(contract_operations - fixture_operations)),
                "unexpected_operations": tuple(sorted(fixture_operations - contract_operations)),
            },
            contract_manifest["contract_count"] == self.expected_contract_count
            and contract_operations == fixture_operations,
            "every positive fixture maps to one declarative capability contract",
        )
        contract_fields_ok = True
        missing_contract_fields: dict[str, tuple[str, ...]] = {}
        registry = default_intake_contract_registry()
        for record in catalog.records:
            missing = registry.contract_for_kind(record.kind).missing_fields(record.payload)
            if missing:
                contract_fields_ok = False
                missing_contract_fields[record.record_id] = missing
        self._add(
            checks,
            "contract-payload-fields",
            "positive payloads contain every declared contract field",
            missing_contract_fields,
            contract_fields_ok,
            "fixture execution is checked against required input fields rather than only names",
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
            fixture_report.context_key == data_report.context_key
            and replay_report.context_keys == (fixture_report.context_key,),
            "intake records are not compared across incompatible biological contexts",
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
            fixture_report.source_ids == data_report.source_ids
            and fixture_report.source_ids == replay_report.source_ids,
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
        public_ids = [record.public_identifier for record in catalog.records]
        self._add(
            checks,
            "public-identity-uniqueness",
            "positive public identifiers are unique",
            public_ids,
            len(public_ids) == len(set(public_ids)),
            "trace identifiers cannot silently alias two intake operation inputs",
        )
        serialized = json.dumps(fixture_report.to_dict(), sort_keys=True).casefold()
        self._add(
            checks,
            "output-boundary",
            "operation outputs contain no restricted field names",
            any(
                fragment in serialized
                for fragment in ("patient_id", "medical_record", "mrn", "password", "secret")
            ),
            not any(
                fragment in serialized
                for fragment in ("patient_id", "medical_record", "mrn", "password", "secret")
            ),
            "operation receipts remain safe for a public aggregate evidence bundle",
        )
        passed_ids = tuple(check.check_id for check in checks if check.passed)
        failed_ids = tuple(check.check_id for check in checks if not check.passed)
        body = {
            "fixture": fixture_report,
            "data": data_report,
            "replay": replay_report,
            "scenarios": scenario_report,
            "contracts": contract_manifest,
            "checks": checks,
        }
        boundary = require_non_empty(
            str(catalog.provenance.get("evidence_boundary", "")),
            "provenance.evidence_boundary",
        )
        return IntakeQualityGateReport(
            fixture_report.fixture_id,
            fixture_report.fixture_version,
            fixture_report.context_key,
            fixture_report.source_ids,
            {
                "fixture": fixture_report.to_dict(),
                "data": data_report.to_dict(),
                "replay": replay_report.to_dict(),
                "scenarios": scenario_report.to_dict(),
                "contracts": contract_manifest,
            },
            tuple(checks),
            passed_ids,
            failed_ids,
            boundary,
            IntakeDataState.ACCEPTED if not failed_ids else IntakeDataState.REVIEW,
            content_hash(body),
        )

    @staticmethod
    def _add(
        checks: list[IntakeQualityCheck],
        check_id: str,
        requirement: str,
        observed: Any,
        passed: bool,
        detail: str,
    ) -> None:
        checks.append(IntakeQualityCheck(check_id, requirement, observed, bool(passed), detail))


def evaluate_intake_quality_gate(path: str | Path) -> IntakeQualityGateReport:
    """Evaluate the combined Domain 01 intake quality gate."""

    return IntakeQualityGate().evaluate_file(path)


__all__ = [
    "IntakeQualityCheck",
    "IntakeQualityGate",
    "IntakeQualityGateReport",
    "evaluate_intake_quality_gate",
]
