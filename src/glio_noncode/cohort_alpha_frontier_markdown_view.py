"""Markdown projection with explicit limitations and review counts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierMarkdownView:
    title: str
    text: str
    section_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_markdown_view(metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierMarkdownView:
    title = "# GLIO non-code cohort alpha frontier"
    sections = (f"Rows: {metrics.total_rows}", f"Supported: {metrics.supported_rows}", f"Publish: {policy.publishable_count}", f"Review: {policy.review_count}", f"Quarantine: {policy.quarantine_count}", "Claim ceiling: descriptive aggregate evidence only")
    text = title + "\n\n" + "\n".join(f"- {section}" for section in sections) + "\n"
    return CohortAlphaFrontierMarkdownView(title, text, len(sections) + 1, len(sections) == 6 and "Claim ceiling" in text, content_hash({"title": title, "sections": sections}, prefix="alpha-markdown-view"))


__all__ = ["CohortAlphaFrontierMarkdownView", "build_cohort_alpha_frontier_markdown_view"]
