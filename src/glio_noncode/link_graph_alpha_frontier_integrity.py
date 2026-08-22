"""Content and row integrity checks for the closed fixture boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierIntegrityReport:
    checks: tuple[Any, ...]
    content_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "content_addresses": self.content_addresses, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_alpha_frontier_integrity(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierIntegrityReport:
    addresses = tuple(item.content_address for item in fixture.records) + tuple(item.adapter.content_address for item in evaluation.rows)
    checks = (
        check("record_addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), "all records are content addressed"),
        check("result_addresses", all(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), "all results are content addressed"),
        check("unique_record_addresses", len({item.content_address for item in fixture.records}) == len(fixture.records), "record addresses are unique"),
        check("fixture_address", fixture.content_address == content_hash({"fixture_id": fixture.fixture_id, "version": fixture.version, "sources": fixture.sources, "records": fixture.records}), "fixture address is reproducible"),
    )
    return LinkGraphAlphaFrontierIntegrityReport(checks, addresses, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierIntegrityReport", "evaluate_link_graph_alpha_frontier_integrity"]
