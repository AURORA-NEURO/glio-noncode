"""Accessibility checks for aggregate source receipts and review exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAccessibilityReport:
    source_urls: tuple[str, ...]
    checks: tuple[Any, ...]
    boundary: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"source_urls": self.source_urls, "checks": [item.to_dict() for item in self.checks], "boundary": self.boundary, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_foundation_frontier_accessibility(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierAccessibilityReport:
    urls = tuple(sorted(item.uri for item in fixture.sources))
    checks = (check("urls", len(urls) == len(fixture.sources), "every receipt has a source URL"), check("https", all(item.startswith("https://") for item in urls), "source URLs use HTTPS"), check("versions", all(item.source_version for item in fixture.sources), "versions are visible"), check("rows", evaluation is None or len(evaluation.rows) == len(fixture.records), "review rows align"))
    return LinkGraphFoundationFrontierAccessibilityReport(urls, checks, fixture.boundary, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierAccessibilityReport", "evaluate_link_graph_foundation_frontier_accessibility"]
