"""Machine-readable catalog of the C01-C04 foundation module surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierModuleEntry:
    module_id: str
    purpose: str
    layer: str
    public: bool
    test_file: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierModuleCatalog:
    version: str
    entries: tuple[LinkGraphFoundationFrontierModuleEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def layers(self) -> tuple[str, ...]:
        return tuple(sorted({item.layer for item in self.entries}))

    def by_layer(self, layer: str) -> tuple[LinkGraphFoundationFrontierModuleEntry, ...]:
        return tuple(item for item in self.entries if item.layer == layer)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"version": self.version, "entries": [item.to_dict() for item in self.entries], "layers": self.layers, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_module_catalog() -> LinkGraphFoundationFrontierModuleCatalog:
    groups = (("data", "public_data", "aggregate fixture and receipt boundary"), ("compute", "adapters", "operation primitive bindings"), ("replay", "fixture_eval", "deterministic fixture replay"), ("quality", "metrics", "metrics, evidence, and quality gates"), ("review", "projection", "review and export projections"), ("release", "release_readiness", "release readiness and risk controls"), ("operations", "workflow", "ordered repeatable verification workflow"))
    entries = tuple(LinkGraphFoundationFrontierModuleEntry(f"d10-c01-c04-{layer}", purpose, layer, True, "tests/test_link_graph_foundation_frontier.py") for layer, module, purpose in groups)
    return LinkGraphFoundationFrontierModuleCatalog("2026.08.catalog.v1", entries, bool(entries) and all(item.public and item.test_file for item in entries))


def module_catalog_summary(catalog: LinkGraphFoundationFrontierModuleCatalog) -> dict[str, Any]:
    return {"version": catalog.version, "module_count": len(catalog.entries), "layer_count": len(catalog.layers), "layers": catalog.layers, "accepted": catalog.accepted}


__all__ = ["LinkGraphFoundationFrontierModuleCatalog", "LinkGraphFoundationFrontierModuleEntry", "build_link_graph_foundation_frontier_module_catalog", "module_catalog_summary"]
