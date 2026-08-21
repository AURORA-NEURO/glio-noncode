"""Independent positive/review scenario matrix for the Domain 01 fixture."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .variation_fixture_eval import VariationFixtureEvaluator
from .variation_public_data import (
    VariationDataState,
    VariationFixtureCatalog,
    VariationFixtureRecord,
    VariationRecordKind,
)


class VariationScenarioClass(StrEnum):
    """Whether a fixture scenario is a positive or review-boundary case."""

    POSITIVE = "positive"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class VariationScenario:
    """One operation payload and expected state transition."""

    scenario_id: str
    scenario_class: VariationScenarioClass
    record: VariationFixtureRecord
    expected_state: str
    required_issue_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.expected_state, "expected_state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationScenarioResult:
    """Observed operation state and structured reasons for one scenario."""

    scenario_id: str
    scenario_class: str
    expected_state: str
    observed_state: str
    required_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationScenarioMatrixReport:
    """Complete state-transition matrix verdict."""

    context_key: str
    results: tuple[VariationScenarioResult, ...]
    positive_scenario_ids: tuple[str, ...]
    review_scenario_ids: tuple[str, ...]
    failed_scenario_ids: tuple[str, ...]
    state: VariationDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == VariationDataState.ACCEPTED and not self.failed_scenario_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["scenario_count"] = len(self.results)
        return result


class VariationScenarioMatrix:
    """Derive and run five positive and five negative fixture scenarios."""

    def __init__(self, raw: Mapping[str, Any]) -> None:
        self.raw = raw
        self.catalog = VariationFixtureCatalog.from_fixture(raw)
        self.evaluator = VariationFixtureEvaluator()
        self.context = _context_mapping(raw.get("context"))

    @classmethod
    def from_file(cls, path: str | Path) -> VariationScenarioMatrix:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"variation scenario fixture is not valid JSON: {path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("variation scenario fixture must be an object")
        return cls(raw)

    def scenarios(self) -> tuple[VariationScenario, ...]:
        scenarios: list[VariationScenario] = []
        for record in self.catalog.records:
            scenarios.append(
                VariationScenario(
                    record.record_id,
                    VariationScenarioClass.POSITIVE,
                    record,
                    record.expected_state,
                )
            )
        controls = self.raw.get("negative_controls", ())
        if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
            raise ValidationError("variation negative_controls must be an array")
        for control in controls:
            if not isinstance(control, Mapping):
                raise ValidationError("variation negative control must be an object")
            control_id = require_non_empty(str(control.get("control_id", "")), "control_id")
            kind = VariationRecordKind(str(control.get("kind", "")))
            payload = control.get("payload")
            if not isinstance(payload, Mapping):
                raise ValidationError(f"{control_id} payload must be an object")
            record = VariationFixtureRecord(
                f"negative:{control_id}",
                kind,
                str(control.get("operation", kind.value)),
                str(control.get("source_id", "fixture-negative")),
                str(control.get("context_key", self.catalog.context_key)),
                payload,
                str(control.get("public_identifier", control_id)),
                str(control.get("expected_state", "")),
            )
            scenarios.append(
                VariationScenario(
                    f"negative:{control_id}",
                    VariationScenarioClass.REVIEW,
                    record,
                    record.expected_state,
                    tuple(str(item) for item in control.get("required_issue_codes", ())),
                )
            )
        return tuple(scenarios)

    def run(self) -> VariationScenarioMatrixReport:
        results: list[VariationScenarioResult] = []
        for scenario in self.scenarios():
            output = self.evaluator.run_record(
                scenario.record,
                self.context,
                self.catalog.context_key,
            )
            serialized = output.to_dict()
            observed_state = _state_value(output)
            observed_issue_codes = _issue_codes(serialized)
            state_ok = observed_state == scenario.expected_state
            reasons_ok = all(code in observed_issue_codes for code in scenario.required_issue_codes)
            passed = state_ok and reasons_ok
            results.append(
                VariationScenarioResult(
                    scenario.scenario_id,
                    scenario.scenario_class.value,
                    scenario.expected_state,
                    observed_state,
                    scenario.required_issue_codes,
                    observed_issue_codes,
                    passed,
                    content_hash(
                        {
                            "scenario": scenario,
                            "state": observed_state,
                            "issue_codes": observed_issue_codes,
                        }
                    ),
                )
            )
        positive_ids = tuple(
            result.scenario_id
            for result in results
            if result.scenario_class == VariationScenarioClass.POSITIVE.value
        )
        review_ids = tuple(
            result.scenario_id
            for result in results
            if result.scenario_class == VariationScenarioClass.REVIEW.value
        )
        failed_ids = tuple(result.scenario_id for result in results if not result.passed)
        state = VariationDataState.ACCEPTED if not failed_ids else VariationDataState.REVIEW
        return VariationScenarioMatrixReport(
            self.catalog.context_key,
            tuple(results),
            positive_ids,
            review_ids,
            failed_ids,
            state,
            content_hash({"context_key": self.catalog.context_key, "results": results}),
        )


def _context_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValidationError("variation scenario context must be an object")
    fields = (
        "genome_build",
        "disease_class",
        "age_group",
        "cell_state",
        "territory",
        "treatment_phase",
    )
    return {
        field: require_non_empty(str(value.get(field, "")), f"context.{field}")
        for field in fields
    }


def _state_value(value: Any) -> str:
    state = getattr(value, "state", "invalid")
    return str(getattr(state, "value", state))


def _issue_codes(value: Any) -> tuple[str, ...]:
    codes: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "code" and isinstance(child, str):
                codes.append(child)
            else:
                codes.extend(_issue_codes(child))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            codes.extend(_issue_codes(child))
    return tuple(sorted(set(codes)))


def evaluate_variation_scenarios(path: str | Path) -> VariationScenarioMatrixReport:
    """Run the independent variation state-transition matrix."""

    return VariationScenarioMatrix.from_file(path).run()


__all__ = [
    "VariationScenario",
    "VariationScenarioClass",
    "VariationScenarioMatrix",
    "VariationScenarioMatrixReport",
    "VariationScenarioResult",
    "evaluate_variation_scenarios",
]
