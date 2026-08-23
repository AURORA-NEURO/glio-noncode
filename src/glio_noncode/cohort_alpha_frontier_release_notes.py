"""Release-note entries documenting the C09-C12 depth tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseNote:
    note_id: str
    category: str
    text: str
    evidence_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseNotes:
    release_id: str
    notes: tuple[CohortAlphaFrontierReleaseNote, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_release_notes(manifest: CohortAlphaFrontierReleaseManifest) -> CohortAlphaFrontierReleaseNotes:
    raw = (("scope", "C09-C12 now has a bounded public aggregate fixture with positive and boundary paths."), ("governance", "Publication is limited to supported exact-context rows; partial and ambiguous paths remain in review."), ("traceability", "Source receipts, state reconciliation, replay, and content addresses are included in the package."), ("limitation", "The release remains descriptive and does not establish causation, prognosis, significance, or treatment recommendations."))
    notes = tuple(CohortAlphaFrontierReleaseNote(f"note-{category}", category, text, manifest.content_address, content_hash({"id": category, "category": category, "text": text, "evidence": manifest.content_address}, prefix="alpha-release-note")) for category, text in raw)
    return CohortAlphaFrontierReleaseNotes(manifest.release_id, notes, manifest.ready and len(notes) == 4, content_hash({"release": manifest.release_id, "notes": notes}, prefix="alpha-release-notes"))


__all__ = ["CohortAlphaFrontierReleaseNote", "CohortAlphaFrontierReleaseNotes", "build_cohort_alpha_frontier_release_notes"]
