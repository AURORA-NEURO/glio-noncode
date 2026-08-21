"""Combined quality gate for the Domain 01 identity evidence stack."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identity_contracts import default_identity_contract_registry
from .identity_fixture_eval import IdentityFixtureEvaluator
from .identity_public_data import IdentityDataState, IdentityFixtureCatalog
from .identity_replay import IdentityReplayExpectation, IdentityReplayRunner
from .identity_scenario_matrix import IdentityScenarioMatrix
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class IdentityQualityCheck:
    """One combined-gate assertion with an addressable receipt."""

    check_id: str
    expected: Any
    observed: Any
    passed: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "identity quality check_id")
        require_non_empty(self.detail, "identity quality detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityQualityGateReport:
    """Evidence gate joining data, operation, replay, scenario, and contracts."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    checks: tuple[IdentityQualityCheck, ...]
    component_receipts: Mapping[str, Mapping[str, Any]]
    failed_check_ids: tuple[str, ...]
    state: IdentityDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IdentityDataState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = sum(check.passed for check in self.checks)
        return result


class IdentityQualityGate:
    """Run every declared boundary for a public aggregate identity fixture."""

    expected_record_count = 4
    expected_negative_control_count = 8
    expected_fixture_checks = 37
    expected_scenario_count = 12
    expected_contract_count = 4

    def __init__(self, evaluator: IdentityFixtureEvaluator | None = None) -> None:
        self.evaluator = evaluator or IdentityFixtureEvaluator()

    def evaluate_file(self, path: str | Path) -> IdentityQualityGateReport:
        raw = self.evaluator.load_file(path)
        catalog = IdentityFixtureCatalog.from_fixture(raw)
        fixture_report = self.evaluator.evaluate(raw)
        data_report = catalog.audit()
        replay = IdentityReplayRunner(self.evaluator).replay(
            (path,),
            expectation=IdentityReplayExpectation(
                fixture_id=catalog.fixture_id,
                context_key=catalog.context_key,
                source_ids=tuple(sorted(source.source_id for source in catalog.sources)),
                min_check_count=self.expected_fixture_checks,
                min_positive_count=self.expected_record_count,
                min_negative_control_count=self.expected_negative_control_count,
            ),
        )
        scenarios = IdentityScenarioMatrix(raw, evaluator=self.evaluator).run()
        contracts = default_identity_contract_registry().manifest()
        checks: list[IdentityQualityCheck] = []
        self._append_check(
            checks,
            "fixture-evaluation",
            True,
            fixture_report.passed,
            "identity fixture evaluation passes all declared operation checks",
            fixture_report.to_dict(),
        )
        self._append_check(
            checks,
            "fixture-check-floor",
            self.expected_fixture_checks,
            len(fixture_report.checks),
            "fixture evaluator exposes the expected detailed check inventory",
            {"check_count": len(fixture_report.checks)},
        )
        self._append_check(
            checks,
            "public-data-audit",
            True,
            data_report.accepted,
            "fixture is public aggregate data with exact source and context receipts",
            data_report.to_dict(),
        )
        self._append_check(
            checks,
            "replay-integrity",
            True,
            replay.passed,
            "fixture replays with the expected identity, context, source set, and count floors",
            replay.to_dict(),
        )
        self._append_check(
            checks,
            "record-count",
            self.expected_record_count,
            len(catalog.records),
            "all four identity operation families are represented",
            {"record_ids": tuple(record.record_id for record in catalog.records)},
        )
        self._append_check(
            checks,
            "negative-control-count",
            self.expected_negative_control_count,
            len(catalog.controls),
            "all identity review and abstention controls are represented",
            {"control_ids": tuple(control.control_id for control in catalog.controls)},
        )
        self._append_check(
            checks,
            "scenario-matrix",
            self.expected_scenario_count,
            len(scenarios.results),
            "positive and review scenarios execute through the same operation path",
            scenarios.to_dict(),
        )
        self._append_check(
            checks,
            "contract-inventory",
            self.expected_contract_count,
            contracts["contract_count"],
            "one contract is published for each C09-C12 operation family",
            contracts,
        )
        self._append_check(
            checks,
            "context-consistency",
            catalog.context_key,
            fixture_report.context_key,
            "fixture and evaluator retain one exact context key",
            {"fixture": catalog.context_key, "evaluation": fixture_report.context_key},
        )
        self._append_check(
            checks,
            "source-consistency",
            tuple(sorted(source.source_id for source in catalog.sources)),
            fixture_report.source_ids,
            "operation receipts retain the complete sorted source receipt set",
            {"fixture": catalog.sources, "evaluation": fixture_report.source_ids},
        )
        repeated = self.evaluator.evaluate(raw)
        self._append_check(
            checks,
            "deterministic-evaluation",
            fixture_report.content_address,
            repeated.content_address,
            "repeated fixture evaluation has one content address",
            {"first": fixture_report.content_address, "second": repeated.content_address},
        )
        serialized_receipts = jsonable(
            {
                "fixture": fixture_report.to_dict(),
                "replay": replay.to_dict(),
                "scenarios": scenarios.to_dict(),
            }
        )
        serialized_text = str(serialized_receipts).casefold()
        self._append_check(
            checks,
            "output-boundary",
            False,
            any(
                fragment in serialized_text
                for fragment in ("patient_id", "medical_record", "mrn", "password", "secret")
            ),
            "combined receipts do not expose restricted data field names",
            {"restricted_output": serialized_text},
        )
        failed = tuple(check.check_id for check in checks if not check.passed)
        state = IdentityDataState.ACCEPTED if not failed else IdentityDataState.REVIEW
        components = {
            "data": data_report.to_dict(),
            "fixture": fixture_report.to_dict(),
            "replay": replay.to_dict(),
            "scenarios": scenarios.to_dict(),
            "contracts": contracts,
        }
        body = {
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.fixture_version,
            "context_key": catalog.context_key,
            "source_ids": tuple(sorted(source.source_id for source in catalog.sources)),
            "checks": checks,
            "components": components,
        }
        return IdentityQualityGateReport(
            catalog.fixture_id,
            catalog.fixture_version,
            catalog.context_key,
            tuple(sorted(source.source_id for source in catalog.sources)),
            tuple(checks),
            components,
            failed,
            state,
            content_hash(body),
        )

    @staticmethod
    def _append_check(
        checks: list[IdentityQualityCheck],
        check_id: str,
        expected: Any,
        observed: Any,
        detail: str,
        receipt: Any,
    ) -> None:
        checks.append(
            IdentityQualityCheck(
                check_id,
                expected,
                observed,
                observed == expected,
                detail,
                content_hash(receipt),
            )
        )


def evaluate_identity_quality_gate(path: str | Path) -> IdentityQualityGateReport:
    """Convenience function for the complete identity quality gate."""

    return IdentityQualityGate().evaluate_file(path)


__all__ = [
    "IdentityQualityCheck",
    "IdentityQualityGate",
    "IdentityQualityGateReport",
    "evaluate_identity_quality_gate",
]
