"""Source receipt index with covered-context and release checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_public_data import (
    CellContextBetaFrontierFixture,
    CellContextBetaFrontierSourceReceipt,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierSourceEntry:
    receipt: CellContextBetaFrontierSourceReceipt
    record_count: int
    operation_count: int
    usable: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.record_count < 0 or self.operation_count < 0 or not self.detail:
            raise ValidationError("beta source entry is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierSourceRegistry:
    entries: tuple[CellContextBetaFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValidationError("beta source registry is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_source(self, source_id: str) -> CellContextBetaFrontierSourceEntry:
        return next(item for item in self.entries if item.receipt.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_source_registry(
    fixture: CellContextBetaFrontierFixture,
) -> CellContextBetaFrontierSourceRegistry:
    entries = []
    for receipt in fixture.sources:
        records = tuple(item for item in fixture.records if receipt.source_id in item.source_ids)
        entries.append(
            CellContextBetaFrontierSourceEntry(
                receipt,
                len(records),
                len({item.operation for item in records}),
                bool(receipt.public_aggregate),
                "public aggregate receipt is declared for the covered context set",
            )
        )
    return CellContextBetaFrontierSourceRegistry(
        tuple(entries), all(item.usable for item in entries)
    )


__all__ = [
    "CellContextBetaFrontierSourceEntry",
    "CellContextBetaFrontierSourceRegistry",
    "build_cell_context_beta_frontier_source_registry",
]
