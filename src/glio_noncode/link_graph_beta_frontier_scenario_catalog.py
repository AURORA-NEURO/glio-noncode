"""Named scenario catalog for beta positive, control, and boundary rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierScenarioDefinition:
    scenario_id: str
    operation: str
    role: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    record_ids: tuple[str, ...]
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierScenarioOutcome:
    scenario_id: str
    observed_states: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool

    @property
    def accepted(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierScenarioCatalog:
    fixture_id: str
    definitions: tuple[LinkGraphBetaFrontierScenarioDefinition, ...]
    outcomes: tuple[LinkGraphBetaFrontierScenarioOutcome, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.outcomes if not item.accepted)

    def outcome(self, scenario_id: str) -> LinkGraphBetaFrontierScenarioOutcome:
        return next(item for item in self.outcomes if item.scenario_id == scenario_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "definitions": [item.to_dict() for item in self.definitions], "outcomes": [item.to_dict() for item in self.outcomes], "failed_scenarios": self.failed_scenarios, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_scenario_catalog(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierScenarioCatalog:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    definitions = tuple(LinkGraphBetaFrontierScenarioDefinition(f"scenario-{row.record_id.lower()}", row.operation, row.role, row.expected_state, row.expected_issue_codes, (row.record_id,), "locks one declared fixture outcome") for row in replay.rows)
    outcomes = tuple(LinkGraphBetaFrontierScenarioOutcome(definition.scenario_id, tuple(row.observed_state for row in replay.rows if row.record_id in definition.record_ids), tuple(sorted({issue for row in replay.rows if row.record_id in definition.record_ids for issue in row.observed_issue_codes})), all(row.state_match for row in replay.rows if row.record_id in definition.record_ids), all(row.issue_match for row in replay.rows if row.record_id in definition.record_ids)) for definition in definitions)
    return LinkGraphBetaFrontierScenarioCatalog(value.fixture_id, definitions, outcomes, bool(outcomes) and all(item.accepted for item in outcomes))


def scenario_catalog_summary(catalog: LinkGraphBetaFrontierScenarioCatalog) -> dict[str, Any]:
    return {"fixture_id": catalog.fixture_id, "definition_count": len(catalog.definitions), "outcome_count": len(catalog.outcomes), "positive_count": sum(item.role == "positive" for item in catalog.definitions), "control_count": sum(item.role == "control" for item in catalog.definitions), "accepted": catalog.accepted}


__all__ = ["LinkGraphBetaFrontierScenarioCatalog", "LinkGraphBetaFrontierScenarioDefinition", "LinkGraphBetaFrontierScenarioOutcome", "build_link_graph_beta_frontier_scenario_catalog", "scenario_catalog_summary"]
