"""Source receipt registry for the context fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_public_data import (
    CellContextFrontierFixture,
    CellContextFrontierSourceReceipt,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierSourceEntry:
    receipt: CellContextFrontierSourceReceipt
    operation_count: int
    contexts: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.operation_count < 0 or not self.contexts:
            raise ValidationError("cell source entry is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierSourceRegistry:
    entries: tuple[CellContextFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.entries) != 5:
            raise ValidationError("cell source registry requires five entries")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, source_id: str) -> CellContextFrontierSourceEntry:
        for item in self.entries:
            if item.receipt.source_id == source_id:
                return item
        raise KeyError(source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_source_registry(
    fixture: CellContextFrontierFixture,
) -> CellContextFrontierSourceRegistry:
    counts = {item.source_id: 0 for item in fixture.sources}
    for record in fixture.records:
        for source_id in record.source_ids:
            counts[source_id] += 1
    entries = tuple(
        CellContextFrontierSourceEntry(
            item,
            counts[item.source_id],
            (fixture.context_key,),
            item.public_aggregate and item.context_key == fixture.context_key,
        )
        for item in fixture.sources
    )
    return CellContextFrontierSourceRegistry(entries, all(item.accepted for item in entries))


__all__ = [
    "CellContextFrontierSourceEntry",
    "CellContextFrontierSourceRegistry",
    "build_cell_context_frontier_source_registry",
]
