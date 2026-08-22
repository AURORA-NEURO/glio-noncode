"""Source receipt checks for beta frontier data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierSourceCheckReport:
    fixture_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": self.checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_beta_frontier_source_checks(fixture: LinkGraphBetaFrontierFixture) -> LinkGraphBetaFrontierSourceCheckReport:
    checks = tuple({"check_id": source.source_id, "passed": source.public_aggregate and source.uri.startswith("https://") and source.checksum.startswith("sha256:"), "detail": source.source_kind} for source in fixture.sources)
    return LinkGraphBetaFrontierSourceCheckReport(fixture.fixture_id, checks, all(item["passed"] for item in checks))


__all__ = ["LinkGraphBetaFrontierSourceCheckReport", "run_link_graph_beta_frontier_source_checks"]
