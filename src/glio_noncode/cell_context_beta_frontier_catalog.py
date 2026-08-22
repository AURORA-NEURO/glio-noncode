"""Capability catalog for the beta prior release surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_public_data import CellContextBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierCatalogEntry:
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
class CellContextBetaFrontierCatalog:
    entries: tuple[CellContextBetaFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: str) -> CellContextBetaFrontierCatalogEntry:
        return next(item for item in self.entries if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_catalog() -> CellContextBetaFrontierCatalog:
    entries = tuple(
        CellContextBetaFrontierCatalogEntry(
            f"GNC-D08-C0{index + 5}", operation.value, title, "verified", evidence, limits
        )
        for index, (operation, title, evidence, limits) in enumerate(
            (
                (
                    CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
                    "Developmental lineage prior",
                    ("adult/pediatric gate", "exact context", "candidate alternatives"),
                    ("not calibrated", "not diagnostic"),
                ),
                (
                    CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
                    "Glioblastoma malignant-state prior",
                    ("GBM disease gate", "state candidates", "contradiction"),
                    ("not a diagnosis", "not prognosis"),
                ),
                (
                    CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
                    "IDH-mutant lineage-state prior",
                    ("molecular gate", "source versions", "bounded score"),
                    ("wildtype refusal", "no treatment claim"),
                ),
                (
                    CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
                    "H3K27-altered developmental-state prior",
                    ("declared state gate", "ambiguity", "review limits"),
                    ("not developmental diagnosis", "no clinical inference"),
                ),
            )
        )
    )
    return CellContextBetaFrontierCatalog(entries, len(entries) == 4)


__all__ = [
    "CellContextBetaFrontierCatalog",
    "CellContextBetaFrontierCatalogEntry",
    "build_cell_context_beta_frontier_catalog",
]
