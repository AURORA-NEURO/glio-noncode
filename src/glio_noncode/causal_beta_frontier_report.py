"""Human-readable reports for the C05-C08 frontier release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_assurance import CausalBetaFrontierAssurance
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics
from .causal_beta_frontier_operational import CausalBetaFrontierOperationalMatrix
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReport:
    report_id: str
    fixture_id: str
    title: str
    sections: tuple[tuple[str, str], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"report_id": self.report_id, "fixture_id": self.fixture_id, "title": self.title, "sections": self.sections, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"Fixture: `{self.fixture_id}`", ""]
        for heading, body in self.sections:
            lines.extend([f"## {heading}", "", body, ""])
        return "\n".join(lines)


def build_causal_beta_frontier_report(fixture: CausalBetaFrontierFixture, metrics: CausalBetaFrontierMetrics, review: CausalBetaFrontierReviewQueue, operational: CausalBetaFrontierOperationalMatrix, assurance: CausalBetaFrontierAssurance) -> CausalBetaFrontierReport:
    state_summary = ", ".join(f"{key}={value}" for key, value in sorted(metrics.state_counts.items()))
    issue_summary = ", ".join(f"{key}={value}" for key, value in sorted(metrics.issue_counts.items()))
    sections = (
        ("Scope", "Four causal operations are evaluated over a public aggregate fixture with explicit positive, incomplete, conflicting, and foreign-context controls."),
        ("Observed states", state_summary),
        ("Issue coverage", issue_summary),
        ("Disposition", f"retained={review.retained_count}; review={review.review_count}; blocked={review.blocked_count}; allowed operational cells={operational.allowed_count}"),
        ("Boundary", assurance.headline + " " + " ".join(assurance.limitations)),
    )
    return CausalBetaFrontierReport("causal-beta-frontier-report", fixture.fixture_id, "C05-C08 Causal Beta Frontier Report", sections, assurance.accepted)


__all__ = ["CausalBetaFrontierReport", "build_causal_beta_frontier_report"]
