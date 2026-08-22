"""Conformance checks for the public aggregate boundary and its receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY, LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierConformanceRule:
    rule_id: str
    description: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierConformanceResult:
    rule_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierConformanceReport:
    fixture_id: str
    rules: tuple[LinkGraphFoundationFrontierConformanceRule, ...]
    results: tuple[LinkGraphFoundationFrontierConformanceResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_rules(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.results if not item.passed)

    def result(self, rule_id: str) -> LinkGraphFoundationFrontierConformanceResult:
        return next(item for item in self.results if item.rule_id == rule_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rules": [item.to_dict() for item in self.rules], "results": [item.to_dict() for item in self.results], "failed_rules": self.failed_rules, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _rules() -> tuple[LinkGraphFoundationFrontierConformanceRule, ...]:
    return (LinkGraphFoundationFrontierConformanceRule("boundary-public", "fixture stays within the public aggregate boundary", "blocking"), LinkGraphFoundationFrontierConformanceRule("receipts-complete", "every record resolves to a declared receipt", "blocking"), LinkGraphFoundationFrontierConformanceRule("context-closed", "record contexts stay within declared contexts", "blocking"), LinkGraphFoundationFrontierConformanceRule("operation-closed", "all supported operations have balanced records", "blocking"), LinkGraphFoundationFrontierConformanceRule("replay-accepted", "deterministic replay agrees with declarations", "blocking"), LinkGraphFoundationFrontierConformanceRule("source-addressed", "sources carry stable addresses", "blocking"))


def _check_boundary(fixture: LinkGraphFoundationFrontierFixture, _: LinkGraphFoundationFrontierEvaluation) -> bool:
    return fixture.boundary == LINK_GRAPH_FOUNDATION_FRONTIER_BOUNDARY and all(source.public_aggregate for source in fixture.sources)


def _check_receipts(fixture: LinkGraphFoundationFrontierFixture, _: LinkGraphFoundationFrontierEvaluation) -> bool:
    source_ids = {source.source_id for source in fixture.sources}
    return all(record.source_ids and set(record.source_ids) <= source_ids for record in fixture.records)


def _check_context(fixture: LinkGraphFoundationFrontierFixture, _: LinkGraphFoundationFrontierEvaluation) -> bool:
    allowed = {fixture.context_key, fixture.foreign_context_key}
    return all(record.context_key in allowed and record.payload.get("variant", record.payload).get("context_key", record.context_key) in allowed for record in fixture.records)


def _check_operations(fixture: LinkGraphFoundationFrontierFixture, _: LinkGraphFoundationFrontierEvaluation) -> bool:
    return len(fixture.records) == 16 and all(len(fixture.operation_records(operation)) == 4 for operation in ("coordinate_overlap", "nearest_gene", "ccre_assignment", "enhancer_gene_consensus"))


def _check_replay(_: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> bool:
    return evaluation.accepted


def _check_sources(fixture: LinkGraphFoundationFrontierFixture, _: LinkGraphFoundationFrontierEvaluation) -> bool:
    return all(source.checksum.startswith("sha256:") and len(source.checksum) >= 71 and source.uri.startswith("https://") for source in fixture.sources)


def evaluate_link_graph_foundation_frontier_conformance(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierConformanceReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    checks: tuple[Callable[[LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierEvaluation], bool], ...] = (_check_boundary, _check_receipts, _check_context, _check_operations, _check_replay, _check_sources)
    rules = _rules()
    results = tuple(LinkGraphFoundationFrontierConformanceResult(rule.rule_id, check(value, replay), rule.description) for rule, check in zip(rules, checks))
    return LinkGraphFoundationFrontierConformanceReport(value.fixture_id, rules, results, all(item.passed for item in results))


__all__ = ["LinkGraphFoundationFrontierConformanceReport", "LinkGraphFoundationFrontierConformanceResult", "LinkGraphFoundationFrontierConformanceRule", "evaluate_link_graph_foundation_frontier_conformance"]
