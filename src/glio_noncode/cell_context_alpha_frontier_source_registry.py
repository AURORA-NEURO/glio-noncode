"""Public source receipt registry for the alpha tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_public_data import (
    CellContextAlphaFrontierFixture,
    CellContextAlphaFrontierSourceReceipt,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierSourceEntry:
    receipt: CellContextAlphaFrontierSourceReceipt
    record_count: int
    operation_count: int
    usable: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierSourceRegistry:
    entries: tuple[CellContextAlphaFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("alpha source registry is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_source(self, source_id: str) -> CellContextAlphaFrontierSourceEntry:
        return next(item for item in self.entries if item.receipt.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_source_registry(
    fixture: CellContextAlphaFrontierFixture,
) -> CellContextAlphaFrontierSourceRegistry:
    entries = []
    for receipt in fixture.sources:
        records = tuple(item for item in fixture.records if receipt.source_id in item.source_ids)
        entries.append(
            CellContextAlphaFrontierSourceEntry(
                receipt,
                len(records),
                len({item.operation for item in records}),
                receipt.public_aggregate,
                "public aggregate receipt is declared for its operation",
            )
        )
    return CellContextAlphaFrontierSourceRegistry(
        tuple(entries), all(item.usable for item in entries)
    )


__all__ = [
    "CellContextAlphaFrontierSourceEntry",
    "CellContextAlphaFrontierSourceRegistry",
    "build_cell_context_alpha_frontier_source_registry",
]
