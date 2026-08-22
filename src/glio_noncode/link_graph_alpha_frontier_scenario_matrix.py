"""Named scenarios proving positive, weak, contradictory, and foreign behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierScenario:
    scenario_id: str
    name: str
    record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    required_issue_codes: tuple[str, ...]
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierScenarioMatrix:
    scenarios: tuple[LinkGraphAlphaFrontierScenario, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_name(self, name: str) -> LinkGraphAlphaFrontierScenario:
        for item in self.scenarios:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scenarios": [item.to_dict() for item in self.scenarios], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_scenarios() -> tuple[LinkGraphAlphaFrontierScenario, ...]:
    return (
        LinkGraphAlphaFrontierScenario("positive-path", "clean positive paths", tuple(f"D10-C{number:02d}-P" for number in (9, 10, 11, 12)), ("partial", "partial", "supported", "supported"), (), "prove each primitive can produce a bounded candidate"),
        LinkGraphAlphaFrontierScenario("weak-path", "weak signal controls", ("D10-C09-C1", "D10-C10-C1", "D10-C12-C1"), ("partial", "partial", "partial"), ("low_support", "weak_contact", "single_evidence"), "prove weak paths remain visible"),
        LinkGraphAlphaFrontierScenario("ambiguity-path", "ambiguity controls", ("D10-C10-C2", "D10-C11-C2"), ("partial", "ambiguous"), ("alternative_gene", "tethering_ambiguity"), "prove alternatives and ties are not silently selected"),
        LinkGraphAlphaFrontierScenario("boundary-path", "context boundary controls", ("D10-C09-C3", "D10-C10-C3", "D10-C11-C3", "D10-C12-C3"), ("out_of_domain",) * 4, ("context_mismatch",), "prove transport is gated"),
        LinkGraphAlphaFrontierScenario("contradiction-path", "contradictory evidence controls", ("D10-C09-C2", "D10-C12-C2"), ("contradictory",) * 2, ("direction_disagreement", "contradictory_evidence"), "prove disagreement remains explicit"),
    )


def build_link_graph_alpha_frontier_scenario_matrix(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierScenarioMatrix:
    scenarios = default_link_graph_alpha_frontier_scenarios()
    rows = {item.record_id: item for item in evaluation.rows}
    checks = []
    for scenario in scenarios:
        selected = [rows[item] for item in scenario.record_ids if item in rows]
        observed_states = tuple(item.observed_state for item in selected)
        issues = {code for item in selected for code in item.observed_issue_codes}
        checks.append(check(scenario.scenario_id, len(selected) == len(scenario.record_ids) and observed_states == scenario.expected_states and set(scenario.required_issue_codes) <= issues, f"scenario {scenario.name} replays as declared", evidence=scenario.record_ids))
    return LinkGraphAlphaFrontierScenarioMatrix(scenarios, tuple(checks), all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierScenario", "LinkGraphAlphaFrontierScenarioMatrix", "build_link_graph_alpha_frontier_scenario_matrix", "default_link_graph_alpha_frontier_scenarios"]
