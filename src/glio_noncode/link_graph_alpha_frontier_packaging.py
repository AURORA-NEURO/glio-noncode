"""Package manifest describing release members and review formats."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_bundle import LinkGraphAlphaFrontierBundle
from .link_graph_alpha_frontier_exports import export_link_graph_alpha_frontier_payload
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierPackageManifest:
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


def build_link_graph_alpha_frontier_package_manifest(bundle: LinkGraphAlphaFrontierBundle) -> LinkGraphAlphaFrontierPackageManifest:
    formats = ("json", "csv", "markdown")
    return LinkGraphAlphaFrontierPackageManifest("link-graph-alpha-frontier-package", bundle.content_address, formats, tuple(item.member_id for item in bundle.members), bundle.accepted and len(formats) == 3)


def serialize_link_graph_alpha_frontier_package_manifest(manifest: LinkGraphAlphaFrontierPackageManifest) -> str:
    return export_link_graph_alpha_frontier_payload(manifest)


__all__ = ["LinkGraphAlphaFrontierPackageManifest", "build_link_graph_alpha_frontier_package_manifest", "serialize_link_graph_alpha_frontier_package_manifest"]
