"""Regression assertions over the stable fixture contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierRegressionReport:
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_alpha_frontier_regression(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierRegressionReport:
    checks = (check("fixture_size", len(fixture.records) == 16, "fixture size remains stable"), check("source_size", len(fixture.sources) == 5, "source count remains stable"), check("operation_balance", all(len(fixture.operation_records(item)) == 4 for item in fixture.__class__.__annotations__ and __import__("glio_noncode.link_graph_alpha_frontier_public_data", fromlist=["LinkGraphAlphaFrontierOperation"]).LinkGraphAlphaFrontierOperation), "operation balance remains stable"), check("replay_acceptance", evaluation.accepted, "replay remains accepted"))
    return LinkGraphAlphaFrontierRegressionReport(checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierRegressionReport", "run_link_graph_alpha_frontier_regression"]
