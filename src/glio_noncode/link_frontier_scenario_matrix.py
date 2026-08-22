"""Adversarial scenario matrix for Domain 10 link evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from .link_frontier_fixture_eval import evaluate_link_frontier_fixture
from .link_frontier_public_data import (
    LinkFrontierFixture,
    LinkFrontierOperation,
    default_link_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierScenario:
    scenario_id: str
    title: str
    changed_fields: tuple[str, ...]
    expected_acceptance: bool
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierScenarioResult:
    scenario: LinkFrontierScenario
    accepted: bool
    passed_checks: int
    failed_check_ids: tuple[str, ...]
    evaluation_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"expected_match": self.accepted == self.scenario.expected_acceptance}


@dataclass(frozen=True, slots=True)
class LinkFrontierScenarioMatrix:
    fixture_id: str
    scenarios: tuple[LinkFrontierScenarioResult, ...]
    all_expectations_met: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"all_expectations_met": self.all_expectations_met}


def _scenario(scenario_id: str, title: str, changed_fields: tuple[str, ...], expected: bool, description: str) -> LinkFrontierScenario:
    body = {
        "scenario_id": scenario_id,
        "title": title,
        "changed_fields": changed_fields,
        "expected_acceptance": expected,
        "description": description,
    }
    return LinkFrontierScenario(**body, content_address=content_hash(body))


def _mutate_context(fixture: LinkFrontierFixture) -> LinkFrontierFixture:
    target = next(item for item in fixture.records if item.operation is LinkFrontierOperation.EVIDENCE_PUBLICATION and item.role.value == "positive")
    rows = [dict(row, context_key="other-context") for row in target.payload["input_records"]]
    payload = dict(target.payload, input_records=rows)
    changed = replace(target, payload=payload)
    records = tuple(changed if item.record_id == target.record_id else item for item in fixture.records)
    return replace(fixture, records=records, content_address=content_hash({"fixture": fixture.fixture_id, "scenario": "context"}))


def _mutate_uncertainty(fixture: LinkFrontierFixture) -> LinkFrontierFixture:
    target = next(item for item in fixture.records if item.operation is LinkFrontierOperation.CALIBRATION_ABSTENTION and item.role.value == "positive")
    payload = dict(target.payload, maximum_uncertainty=0.01)
    changed = replace(target, payload=payload)
    records = tuple(changed if item.record_id == target.record_id else item for item in fixture.records)
    return replace(fixture, records=records, content_address=content_hash({"fixture": fixture.fixture_id, "scenario": "uncertainty"}))


def _mutate_zero_support(fixture: LinkFrontierFixture) -> LinkFrontierFixture:
    target = next(item for item in fixture.records if item.operation is LinkFrontierOperation.DEPENDENCE_CORRECTION and item.role.value == "positive")
    rows = [dict(row, support=0.0) for row in target.payload["input_records"]]
    payload = dict(target.payload, input_records=rows)
    changed = replace(target, payload=payload)
    records = tuple(changed if item.record_id == target.record_id else item for item in fixture.records)
    return replace(fixture, records=records, content_address=content_hash({"fixture": fixture.fixture_id, "scenario": "zero"}))


def evaluate_link_frontier_scenarios(
    fixture: LinkFrontierFixture | None = None,
) -> LinkFrontierScenarioMatrix:
    fixture = fixture or default_link_frontier_fixture()
    cases: tuple[tuple[LinkFrontierScenario, Callable[[LinkFrontierFixture], LinkFrontierFixture]], ...] = (
        (_scenario("baseline", "unchanged public aggregate fixture", (), True, "baseline must pass"), lambda item: item),
        (_scenario("context-transport", "publication context transport is blocked", ("context_key",), False, "context mismatch must fail"), _mutate_context),
        (_scenario("uncertainty-threshold", "calibration threshold change forces review", ("maximum_uncertainty",), False, "tight threshold must expose abstention"), _mutate_uncertainty),
        (_scenario("zero-support", "dependence correction preserves zero-support review", ("support",), False, "zero support must not pass"), _mutate_zero_support),
    )
    results: list[LinkFrontierScenarioResult] = []
    for scenario, mutate in cases:
        evaluation = evaluate_link_frontier_fixture(mutate(fixture))
        body = {
            "scenario": scenario,
            "accepted": evaluation.accepted,
            "passed_checks": evaluation.passed_checks,
            "failed_check_ids": evaluation.failed_check_ids,
            "evaluation_address": evaluation.content_address,
        }
        results.append(LinkFrontierScenarioResult(**body, content_address=content_hash(body)))
    all_met = all(item.accepted == item.scenario.expected_acceptance for item in results)
    body = {"fixture_id": fixture.fixture_id, "scenarios": results, "all_expectations_met": all_met}
    return LinkFrontierScenarioMatrix(**body, content_address=content_hash(body))


__all__ = [
    "LinkFrontierScenario",
    "LinkFrontierScenarioMatrix",
    "LinkFrontierScenarioResult",
    "evaluate_link_frontier_scenarios",
]
