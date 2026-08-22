"""Source-level checks for versions, checksums, access, and scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierSourceCheckReport:
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


def run_link_graph_alpha_frontier_source_checks(fixture: LinkGraphAlphaFrontierFixture) -> LinkGraphAlphaFrontierSourceCheckReport:
    checks = (check("source_ids", len({item.source_id for item in fixture.sources}) == len(fixture.sources), "source identifiers are unique"), check("versions", all(item.source_version for item in fixture.sources), "source versions are declared"), check("checksums", all(item.checksum.startswith("sha256:") for item in fixture.sources), "source checksums are content hashes"), check("uris", all(item.uri.startswith("https://") for item in fixture.sources), "source URIs use HTTPS"), check("public_scope", all(item.public_aggregate for item in fixture.sources), "all sources are public aggregate receipts"))
    return LinkGraphAlphaFrontierSourceCheckReport(checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierSourceCheckReport", "run_link_graph_alpha_frontier_source_checks"]
