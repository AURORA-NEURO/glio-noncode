"""Handoff checklist for another consumer of the bounded release package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReleaseManifest
from .cohort_alpha_frontier_package_validation import CohortAlphaFrontierPackageValidationReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierHandoffItem:
    item_id: str
    instruction: str
    evidence_address: str
    acknowledged: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierHandoff:
    items: tuple[CohortAlphaFrontierHandoffItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_handoff(manifest: CohortAlphaFrontierReleaseManifest, package: CohortAlphaFrontierPackageValidationReport) -> CohortAlphaFrontierHandoff:
    raw = (
        ("scope", "Read the context and claim ceiling before using any row."),
        ("publish", "Use only rows with publish disposition."),
        ("review", "Resolve review queue evidence before promoting a row."),
        ("quarantine", "Do not merge foreign or abstained rows into the target context."),
        ("replay", "Retain the replay receipt and package content address."),
    )
    items = tuple(CohortAlphaFrontierHandoffItem(item_id, instruction, manifest.content_address if item_id != "package" else package.content_address, True, content_hash({"id": item_id, "instruction": instruction, "acknowledged": True}, prefix="alpha-handoff")) for item_id, instruction in raw)
    return CohortAlphaFrontierHandoff(items, manifest.ready and package.accepted and len(items) == 5, content_hash(items, prefix="alpha-handoff-report"))


__all__ = ["CohortAlphaFrontierHandoff", "CohortAlphaFrontierHandoffItem", "build_cohort_alpha_frontier_handoff"]
