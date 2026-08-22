"""Accessibility checks for aggregate sources, receipts, and review outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAccessibilityReport:
    checks: tuple[Any, ...]
    source_urls: tuple[str, ...]
    download_boundary: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "source_urls": self.source_urls, "download_boundary": self.download_boundary, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_alpha_frontier_accessibility(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation | None = None) -> LinkGraphAlphaFrontierAccessibilityReport:
    urls = tuple(sorted(source.uri for source in fixture.sources))
    checks = (
        check("urls_present", len(urls) == len(fixture.sources), "every source receipt has a discoverable URI"),
        check("aggregate_label", fixture.boundary == "public_aggregate_non_patient", "download boundary is aggregate"),
        check("source_versions", all(source.source_version for source in fixture.sources), "source versions are visible"),
        check("evaluation_link", evaluation is None or len(evaluation.rows) == len(fixture.records), "review output maps to fixture rows"),
    )
    return LinkGraphAlphaFrontierAccessibilityReport(checks, urls, fixture.boundary, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierAccessibilityReport", "evaluate_link_graph_alpha_frontier_accessibility"]
