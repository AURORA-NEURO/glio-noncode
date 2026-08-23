"""Source registry and citation closure for module-fabric receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_contracts import FabricFixture, FabricSourceReceipt
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricSourceEntry:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    receipt_address: str
    record_count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricSourceRegistry:
    entries: tuple[FabricSourceEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_module_fabric_source_registry(
    fixture: FabricFixture | None = None,
) -> FabricSourceRegistry:
    value = fixture or default_module_fabric_fixture()
    entries = []
    for source in value.sources:
        body = {
            "source_id": source.source_id,
            "title": source.title,
            "uri": source.uri,
            "scope": source.scope,
            "version": source.version,
            "receipt_address": source.content_address,
            "record_count": sum(source.source_id in record.source_ids for record in value.records),
        }
        entries.append(FabricSourceEntry(**body))
    accepted = bool(entries) and all(item.scope == "public_aggregate" and item.uri.startswith("https://") and item.record_count >= 0 for item in entries)
    body = {"entries": entries, "accepted": accepted}
    return FabricSourceRegistry(tuple(entries), accepted, content_hash(body, prefix="module-fabric-source-registry"))


def source_registry_for(source_id: str, registry: FabricSourceRegistry | None = None) -> FabricSourceEntry | None:
    value = registry or build_module_fabric_source_registry()
    return next((item for item in value.entries if item.source_id == source_id), None)


__all__ = ["FabricSourceEntry", "FabricSourceRegistry", "build_module_fabric_source_registry", "source_registry_for"]
