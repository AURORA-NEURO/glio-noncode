"""Positive and review scenario execution for Domain 01 identity fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .identity_fixture_eval import IdentityFixtureEvaluator
from .identity_public_data import (
    IdentityDataState,
    IdentityFixtureCatalog,
)
from .serialization import content_hash, jsonable, require_non_empty


class IdentityScenarioClass(StrEnum):
    """Scenario intent used by the matrix and release gate."""

    POSITIVE = "positive"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class IdentityScenario:
    """One fixture-derived scenario with an exact expected state."""

    scenario_id: str
    scenario_class: IdentityScenarioClass
    kind: str
    public_identifier: str
    expected_state: str
    expected_signals: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.kind, "scenario kind")
        require_non_empty(self.public_identifier, "scenario public_identifier")
        require_non_empty(self.expected_state, "scenario expected_state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityScenarioResult:
    """Observed result and stable receipt for one identity scenario."""

    scenario: IdentityScenario
    observed_state: str
    observed_signals: tuple[str, ...]
    passed: bool
    content_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityScenarioMatrixReport:
    """Complete positive/review scenario matrix result."""

    fixture_id: str
    context_key: str
    results: tuple[IdentityScenarioResult, ...]
    failed_scenario_ids: tuple[str, ...]
    state: IdentityDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IdentityDataState.ACCEPTED and not self.failed_scenario_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["scenario_count"] = len(self.results)
        result["passed_count"] = sum(item.passed for item in self.results)
        return result


class IdentityScenarioMatrix:
    """Derive and execute all positive and review controls from a fixture."""

    def __init__(
        self,
        raw: Mapping[str, Any],
        evaluator: IdentityFixtureEvaluator | None = None,
    ) -> None:
        self.catalog = IdentityFixtureCatalog.from_fixture(raw)
        self.evaluator = evaluator or IdentityFixtureEvaluator()

    def scenarios(self) -> tuple[IdentityScenario, ...]:
        positive = tuple(
            IdentityScenario(
                record.record_id,
                IdentityScenarioClass.POSITIVE,
                record.kind.value,
                record.public_identifier,
                record.expected_state,
                record.expected_signals,
            )
            for record in self.catalog.records
        )
        review = tuple(
            IdentityScenario(
                f"negative:{control.control_id}",
                IdentityScenarioClass.REVIEW,
                control.kind.value,
                control.public_identifier,
                control.expected_state,
                control.expected_signals,
            )
            for control in self.catalog.controls
        )
        return positive + review

    def run(self) -> IdentityScenarioMatrixReport:
        record_by_id = {record.record_id: record for record in self.catalog.records}
        control_by_id = {control.control_id: control for control in self.catalog.controls}
        results: list[IdentityScenarioResult] = []
        for scenario in self.scenarios():
            if scenario.scenario_class == IdentityScenarioClass.POSITIVE:
                record = record_by_id[scenario.scenario_id]
                output = self.evaluator.run_record(record, self.catalog.context_key)
            else:
                control = control_by_id[scenario.scenario_id.removeprefix("negative:")]
                output = self.evaluator.run_control(control, self.catalog.context_key)
            serialized = _serialize_output(output)
            observed_state = _state_value(output)
            observed_signals = _observed_signals(serialized)
            signals_pass = all(signal in observed_signals for signal in scenario.expected_signals)
            passed = observed_state == scenario.expected_state and signals_pass
            detail = (
                "state and required signals match the fixture declaration"
                if passed
                else "state or required signals differ from the fixture declaration"
            )
            results.append(
                IdentityScenarioResult(
                    scenario,
                    observed_state,
                    observed_signals,
                    passed,
                    _content_address(serialized),
                    detail,
                )
            )
        failed = tuple(result.scenario.scenario_id for result in results if not result.passed)
        state = IdentityDataState.ACCEPTED if not failed else IdentityDataState.REVIEW
        body = {
            "fixture_id": self.catalog.fixture_id,
            "context_key": self.catalog.context_key,
            "results": results,
            "failed_scenario_ids": failed,
        }
        return IdentityScenarioMatrixReport(
            self.catalog.fixture_id,
            self.catalog.context_key,
            tuple(results),
            failed,
            state,
            content_hash(body),
        )


def _state_value(value: Any) -> str:
    if isinstance(value, Mapping):
        state = value.get("state", "invalid")
        return str(getattr(state, "value", state))
    state = getattr(value, "state", "invalid")
    return str(getattr(state, "value", state))


def _serialize_output(value: Any) -> dict[str, Any]:
    result = value.to_dict()
    if not isinstance(result, Mapping):
        raise TypeError("identity scenario operation must serialize to an object")
    return dict(result)


def _content_address(value: Mapping[str, Any]) -> str:
    address = value.get("content_address")
    if isinstance(address, str) and address.startswith("sha256:"):
        return address
    return content_hash(value)


def _observed_signals(value: Any) -> tuple[str, ...]:
    signals: set[str] = set()
    state = _state_value(value)
    if state != "invalid":
        signals.add(state)
    _collect_signals(value, signals)
    return tuple(sorted(signals))


def _collect_signals(value: Any, signals: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"code", "error_code"} and isinstance(child, str):
                signals.add(child)
            if key in {
                "duplicate_record_ids",
                "ambiguous_aliases",
                "missing_observation_ids",
                "ungrouped_record_ids",
            } and child:
                signals.add(key)
            _collect_signals(child, signals)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _collect_signals(child, signals)


def evaluate_identity_scenarios(path: str) -> IdentityScenarioMatrixReport:
    """Load and execute one identity scenario matrix."""

    import json
    from pathlib import Path

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TypeError("identity scenario fixture must be an object")
    return IdentityScenarioMatrix(raw).run()


__all__ = [
    "IdentityScenario",
    "IdentityScenarioClass",
    "IdentityScenarioMatrix",
    "IdentityScenarioMatrixReport",
    "IdentityScenarioResult",
    "evaluate_identity_scenarios",
]
