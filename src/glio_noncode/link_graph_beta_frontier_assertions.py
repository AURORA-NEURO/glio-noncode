"""Explicit reusable assertions for the C05-C08 workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAssertion:
    assertion_id: str
    description: str
    passed: bool
    observed: Any
    expected: Any

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAssertionReport:
    fixture_id: str
    assertions: tuple[LinkGraphBetaFrontierAssertion, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_assertions(self) -> tuple[str, ...]:
        return tuple(item.assertion_id for item in self.assertions if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "assertions": [item.to_dict() for item in self.assertions], "failed_assertions": self.failed_assertions, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_assertions(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierAssertionReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    checks: tuple[tuple[str, str, Callable[[], bool], Any, Any], ...] = (("records", "sixteen records are present", lambda: len(value.records) == 16, len(value.records), 16), ("sources", "four receipts are present", lambda: len(value.sources) == 4, len(value.sources), 4), ("positives", "four positive rows are present", lambda: len(value.positive_records) == 4, len(value.positive_records), 4), ("controls", "twelve control rows are present", lambda: len(value.control_records) == 12, len(value.control_records), 12), ("state-replay", "state replay agrees", lambda: replay.state_match_count == len(replay.rows), replay.state_match_count, len(replay.rows)), ("issue-replay", "issue replay agrees", lambda: replay.issue_match_count == len(replay.rows), replay.issue_match_count, len(replay.rows)), ("accepted", "replay is accepted", lambda: replay.accepted, replay.accepted, True))
    assertions = tuple(LinkGraphBetaFrontierAssertion(assertion_id, description, check(), observed, expected) for assertion_id, description, check, observed, expected in checks)
    return LinkGraphBetaFrontierAssertionReport(value.fixture_id, assertions, all(item.passed for item in assertions))


def assertion_summary(report: LinkGraphBetaFrontierAssertionReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "assertion_count": len(report.assertions), "passed_count": sum(item.passed for item in report.assertions), "failed_count": len(report.failed_assertions), "accepted": report.accepted}


__all__ = ["LinkGraphBetaFrontierAssertion", "LinkGraphBetaFrontierAssertionReport", "assertion_summary", "evaluate_link_graph_beta_frontier_assertions"]
