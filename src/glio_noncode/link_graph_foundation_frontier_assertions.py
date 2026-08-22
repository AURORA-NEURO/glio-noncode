"""Reusable assertions for fixture, replay, and release verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAssertion:
    assertion_id: str
    description: str
    passed: bool
    observed: Any
    expected: Any

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAssertionReport:
    fixture_id: str
    assertions: tuple[LinkGraphFoundationFrontierAssertion, ...]
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


def _make_assertions(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> tuple[LinkGraphFoundationFrontierAssertion, ...]:
    checks: tuple[tuple[str, str, Callable[[], bool], Any, Any], ...] = (("records", "sixteen records are present", lambda: len(fixture.records) == 16, len(fixture.records), 16), ("sources", "five receipts are present", lambda: len(fixture.sources) == 5, len(fixture.sources), 5), ("positives", "four positive rows are present", lambda: len(fixture.positive_records) == 4, len(fixture.positive_records), 4), ("controls", "twelve control rows are present", lambda: len(fixture.control_records) == 12, len(fixture.control_records), 12), ("state-replay", "state replay agrees", lambda: evaluation.state_match_count == len(evaluation.rows), evaluation.state_match_count, len(evaluation.rows)), ("issue-replay", "issue replay agrees", lambda: evaluation.issue_match_count == len(evaluation.rows), evaluation.issue_match_count, len(evaluation.rows)), ("fixture-accepted", "fixture replay is accepted", lambda: evaluation.accepted, evaluation.accepted, True))
    return tuple(LinkGraphFoundationFrontierAssertion(assertion_id, description, check(), observed, expected) for assertion_id, description, check, observed, expected in checks)


def evaluate_link_graph_foundation_frontier_assertions(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierAssertionReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    assertions = _make_assertions(value, replay)
    return LinkGraphFoundationFrontierAssertionReport(value.fixture_id, assertions, all(item.passed for item in assertions))


def assertion_summary(report: LinkGraphFoundationFrontierAssertionReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "assertion_count": len(report.assertions), "passed_count": sum(item.passed for item in report.assertions), "failed_count": len(report.failed_assertions), "accepted": report.accepted}


__all__ = ["LinkGraphFoundationFrontierAssertion", "LinkGraphFoundationFrontierAssertionReport", "assertion_summary", "evaluate_link_graph_foundation_frontier_assertions"]
