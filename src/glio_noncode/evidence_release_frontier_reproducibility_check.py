"""Independent reproducibility check for fixture reload and evaluation replay."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReproducibilityCheck:
    fixture_address: str
    first_evaluation_address: str
    second_evaluation_address: str
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def check_evidence_release_reproducibility(fixture: Any) -> EvidenceReleaseReproducibilityCheck:
    first = evaluate_evidence_release_fixture(fixture)
    second = evaluate_evidence_release_fixture(fixture)
    body = {"fixture_address": fixture.content_address, "first_evaluation_address": first.content_address, "second_evaluation_address": second.content_address, "passed": first.content_address == second.content_address}
    return EvidenceReleaseReproducibilityCheck(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseReproducibilityCheck", "check_evidence_release_reproducibility"]
