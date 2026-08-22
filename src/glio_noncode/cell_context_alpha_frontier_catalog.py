"""Machine-readable capability catalog for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierCatalogEntry:
    capability_id: str
    operation: str
    title: str
    state: str
    evidence: tuple[str, ...]
    limits: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierCatalog:
    entries: tuple[CellContextAlphaFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: str) -> CellContextAlphaFrontierCatalogEntry:
        return next(item for item in self.entries if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_catalog() -> CellContextAlphaFrontierCatalog:
    definitions = (
        (
            CellContextAlphaFrontierOperation.SPATIAL_NICHE,
            "Spatial niche prior",
            ("niche rank", "support spread", "sample aggregation"),
            ("not cell-state truth", "not localization"),
        ),
        (
            CellContextAlphaFrontierOperation.CORE_MARGIN,
            "Core and margin territory prior",
            ("core score", "margin score", "mixed label"),
            ("not invasive localization", "one-sided remains partial"),
        ),
        (
            CellContextAlphaFrontierOperation.RECURRENCE_STATE,
            "Recurrence state prior",
            ("phase rank", "phase margin", "context"),
            ("not prognosis", "not response"),
        ),
        (
            CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
            "Treatment-induced state prior",
            ("baseline/post", "delta", "induced stable reduced"),
            ("not resistance", "not recommendation"),
        ),
    )
    entries = tuple(
        CellContextAlphaFrontierCatalogEntry(
            f"GNC-D08-C{index + 9:02d}", operation.value, title, "verified", evidence, limits
        )
        for index, (operation, title, evidence, limits) in enumerate(definitions)
    )
    return CellContextAlphaFrontierCatalog(entries, len(entries) == 4)


__all__ = [
    "CellContextAlphaFrontierCatalog",
    "CellContextAlphaFrontierCatalogEntry",
    "build_cell_context_alpha_frontier_catalog",
]
