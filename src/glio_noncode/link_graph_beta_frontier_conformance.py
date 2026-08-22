"""Boundary conformance rules for C05-C08 public aggregate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LINK_GRAPH_BETA_FRONTIER_BOUNDARY, LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierConformanceRule:
    rule_id: str
    description: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierConformanceResult:
    rule_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierConformanceReport:
    fixture_id: str
    rules: tuple[LinkGraphBetaFrontierConformanceRule, ...]
    results: tuple[LinkGraphBetaFrontierConformanceResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_rules(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.results if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rules": [item.to_dict() for item in self.rules], "results": [item.to_dict() for item in self.results], "failed_rules": self.failed_rules, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_conformance(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierConformanceReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    rules = (LinkGraphBetaFrontierConformanceRule("boundary-public", "fixture uses the public aggregate boundary", "blocking"), LinkGraphBetaFrontierConformanceRule("receipts-complete", "all source IDs resolve", "blocking"), LinkGraphBetaFrontierConformanceRule("context-closed", "record context keys are declared", "blocking"), LinkGraphBetaFrontierConformanceRule("operation-closed", "four beta operations are balanced", "blocking"), LinkGraphBetaFrontierConformanceRule("replay-accepted", "replay agrees with declarations", "blocking"), LinkGraphBetaFrontierConformanceRule("source-addressed", "receipt checksums are content addressed", "blocking"))
    source_ids = {source.source_id for source in value.sources}
    checks: tuple[Callable[[], bool], ...] = (lambda: value.boundary == LINK_GRAPH_BETA_FRONTIER_BOUNDARY and all(source.public_aggregate for source in value.sources), lambda: all(set(record.source_ids) <= source_ids for record in value.records), lambda: all(record.context_key in {value.context_key, value.foreign_context_key} for record in value.records), lambda: len(value.records) == 16 and all(len(value.operation_records(operation)) == 4 for operation in LinkGraphBetaFrontierOperation), lambda: replay.accepted, lambda: all(source.checksum.startswith("sha256:") and source.uri.startswith("https://") for source in value.sources))
    results = tuple(LinkGraphBetaFrontierConformanceResult(rule.rule_id, check(), rule.description) for rule, check in zip(rules, checks))
    return LinkGraphBetaFrontierConformanceReport(value.fixture_id, rules, results, all(item.passed for item in results))


__all__ = ["LinkGraphBetaFrontierConformanceReport", "LinkGraphBetaFrontierConformanceResult", "LinkGraphBetaFrontierConformanceRule", "evaluate_link_graph_beta_frontier_conformance"]
