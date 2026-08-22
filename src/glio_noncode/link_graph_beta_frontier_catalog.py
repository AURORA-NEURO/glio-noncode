"""Layered module catalog for the C05-C08 beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierModuleEntry:
    module_id: str
    purpose: str
    layer: str
    public: bool
    test_file: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierModuleCatalog:
    version: str
    entries: tuple[LinkGraphBetaFrontierModuleEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def layers(self) -> tuple[str, ...]:
        return tuple(sorted({item.layer for item in self.entries}))

    def by_layer(self, layer: str) -> tuple[LinkGraphBetaFrontierModuleEntry, ...]:
        return tuple(item for item in self.entries if item.layer == layer)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"version": self.version, "entries": [item.to_dict() for item in self.entries], "layers": self.layers, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_module_catalog() -> LinkGraphBetaFrontierModuleCatalog:
    groups = (("data", "public_data", "public aggregate fixture and receipts"), ("compute", "adapters", "beta primitive bindings"), ("replay", "fixture_eval", "deterministic replay"), ("quality", "metrics", "quality and reconciliation"), ("review", "projection", "stable review exports"), ("release", "release_readiness", "release and risk controls"), ("operations", "workflow", "ordered verification workflow"))
    entries = tuple(LinkGraphBetaFrontierModuleEntry(f"d10-c05-c08-{layer}", purpose, layer, True, "tests/test_link_graph_beta_frontier_depth.py") for layer, module, purpose in groups)
    return LinkGraphBetaFrontierModuleCatalog("2026.08.beta-catalog.v1", entries, bool(entries) and all(item.public and item.test_file for item in entries))


def module_catalog_summary(catalog: LinkGraphBetaFrontierModuleCatalog) -> dict[str, Any]:
    return {"version": catalog.version, "module_count": len(catalog.entries), "layer_count": len(catalog.layers), "layers": catalog.layers, "accepted": catalog.accepted}


__all__ = ["LinkGraphBetaFrontierModuleCatalog", "LinkGraphBetaFrontierModuleEntry", "build_link_graph_beta_frontier_module_catalog", "module_catalog_summary"]
