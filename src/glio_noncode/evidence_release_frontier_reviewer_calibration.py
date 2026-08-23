"""Reviewer calibration checks for tier and state vocabulary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReviewerCalibration:
    reviewer_count: int
    decisions: tuple[str, ...]
    vocabulary_valid: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def calibrate_evidence_release_reviewers(reviewer_ids: Iterable[str], decisions: Iterable[str]) -> EvidenceReleaseReviewerCalibration:
    reviewers = tuple(sorted({str(item) for item in reviewer_ids if str(item)}))
    chosen = tuple(str(item) for item in decisions)
    allowed = {"accept", "hold", "reject", "abstain"}
    body = {"reviewer_count": len(reviewers), "decisions": chosen, "vocabulary_valid": bool(chosen) and all(item in allowed for item in chosen)}
    return EvidenceReleaseReviewerCalibration(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseReviewerCalibration", "calibrate_evidence_release_reviewers"]
