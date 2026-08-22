"""Content-address and identity integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierIntegrityReport:
    fixture_id: str
    fixture_address_valid: bool
    record_address_count: int
    result_address_count: int
    unique_addresses: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "fixture_address_valid": self.fixture_address_valid, "record_address_count": self.record_address_count, "result_address_count": self.result_address_count, "unique_addresses": self.unique_addresses, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_integrity(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierIntegrityReport:
    addresses = [fixture.content_address, *(record.content_address for record in fixture.records), *(row.adapter.content_address for row in evaluation.rows)]
    unique = len(addresses) == len(set(addresses))
    return LinkGraphBetaFrontierIntegrityReport(fixture.fixture_id, fixture.content_address.startswith("sha256:"), len(fixture.records), len(evaluation.rows), unique, bool(addresses) and all(address.startswith("sha256:") for address in addresses) and len(fixture.records) == len(evaluation.rows))


__all__ = ["LinkGraphBetaFrontierIntegrityReport", "evaluate_link_graph_beta_frontier_integrity"]
