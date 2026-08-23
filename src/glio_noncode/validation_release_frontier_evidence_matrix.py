"""Evidence-plane matrix joining source, operation, state, and review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture

VALIDATION_RELEASE_EVIDENCE_PLANES = ("source", "input", "execution", "state", "review", "release")


@dataclass(frozen=True, slots=True)
class ValidationReleaseEvidenceCell:
    record_id: str
    plane: str
    address: str
    present: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseEvidenceMatrix:
    cells: tuple[ValidationReleaseEvidenceCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_evidence_matrix(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseEvidenceMatrix:
    source_map = {item.record_id: item.source_ids for item in fixture.records}
    cells = []
    for execution in evaluation.executions:
        values = {"source": content_hash(source_map[execution.record_id]), "input": content_hash(next(item.payload for item in fixture.records if item.record_id == execution.record_id)), "execution": execution.content_address, "state": content_hash(execution.observed_state.value), "review": content_hash(execution.issue_codes), "release": content_hash(fixture.fixture_id)}
        for plane in VALIDATION_RELEASE_EVIDENCE_PLANES:
            body = {"record_id": execution.record_id, "plane": plane, "address": values[plane], "present": values[plane].startswith("sha256:")}
            cells.append(ValidationReleaseEvidenceCell(**body, content_address=content_hash(body)))
    return ValidationReleaseEvidenceMatrix(tuple(cells), all(item.present for item in cells), content_hash(tuple(cells)))


__all__ = ["VALIDATION_RELEASE_EVIDENCE_PLANES", "ValidationReleaseEvidenceCell", "ValidationReleaseEvidenceMatrix", "build_validation_release_evidence_matrix"]
