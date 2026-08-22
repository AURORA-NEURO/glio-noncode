"""Package formats and member manifest for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_bundle import LinkGraphFoundationFrontierBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierPackageManifest:
    package_id: str
    bundle_address: str
    formats: tuple[str, ...]
    members: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"package_id": self.package_id, "bundle_address": self.bundle_address, "formats": self.formats, "members": self.members, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_package_manifest(bundle: LinkGraphFoundationFrontierBundle) -> LinkGraphFoundationFrontierPackageManifest:
    formats = ("json", "csv", "markdown")
    return LinkGraphFoundationFrontierPackageManifest("link-graph-foundation-frontier-package", bundle.content_address, formats, tuple(item.member_id for item in bundle.members), bundle.accepted)


__all__ = ["LinkGraphFoundationFrontierPackageManifest", "build_link_graph_foundation_frontier_package_manifest"]
