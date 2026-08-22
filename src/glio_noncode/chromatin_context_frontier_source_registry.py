"""Source receipt registry and scope checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_public_data import (
    ChromatinContextFrontierFixture,
    ChromatinContextFrontierSourceReceipt,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierSourceEntry:
    receipt: ChromatinContextFrontierSourceReceipt
    operation_count: int
    contexts: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.operation_count < 0 or not self.contexts:
            raise ValidationError("source entry is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierSourceRegistry:
    entries: tuple[ChromatinContextFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.entries) != 5:
            raise ValidationError("source registry requires five entries")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, source_id: str) -> ChromatinContextFrontierSourceEntry:
        for item in self.entries:
            if item.receipt.source_id == source_id:
                return item
        raise KeyError(source_id)

    def for_operation_count(self, minimum: int) -> tuple[ChromatinContextFrontierSourceEntry, ...]:
        return tuple(item for item in self.entries if item.operation_count >= minimum)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_source_registry(
    fixture: ChromatinContextFrontierFixture,
) -> ChromatinContextFrontierSourceRegistry:
    counts = {source.source_id: 0 for source in fixture.sources}
    for record in fixture.records:
        for source_id in record.source_ids:
            counts[source_id] += 1
    entries = tuple(
        ChromatinContextFrontierSourceEntry(
            source,
            counts[source.source_id],
            (fixture.context_key,),
            source.public_aggregate and source.context_key == fixture.context_key,
        )
        for source in fixture.sources
    )
    return ChromatinContextFrontierSourceRegistry(entries, all(item.accepted for item in entries))


__all__ = [
    "ChromatinContextFrontierSourceEntry",
    "ChromatinContextFrontierSourceRegistry",
    "build_chromatin_context_frontier_source_registry",
]
