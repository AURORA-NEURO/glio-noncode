"""Source version, checksum, URL, and scope checks."""

from __future__ import annotations

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_support import LinkGraphFoundationFrontierReport, check, report


def run_link_graph_foundation_frontier_source_checks(fixture: LinkGraphFoundationFrontierFixture) -> LinkGraphFoundationFrontierReport:
    checks = (check("ids", len({item.source_id for item in fixture.sources}) == len(fixture.sources), "source IDs are unique"), check("versions", all(item.source_version for item in fixture.sources), "source versions are declared"), check("checksums", all(item.checksum.startswith("sha256:") for item in fixture.sources), "source checksums are content hashes"), check("uris", all(item.uri.startswith("https://") for item in fixture.sources), "URLs use HTTPS"), check("scope", all(item.public_aggregate for item in fixture.sources), "all sources are public aggregate"))
    return report("link-graph-foundation-frontier-source-checks", checks)


__all__ = ["run_link_graph_foundation_frontier_source_checks"]
