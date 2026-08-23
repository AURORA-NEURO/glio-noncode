"""Scenario reconciliation over all expected states."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseScenarioMatrix:
    cells: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_scenarios(evaluation: Any) -> EvidenceReleaseScenarioMatrix:
    cells = tuple({"record_id": item.record_id, "expected": item.expected_state.value, "observed": item.observed_state.value, "passed": item.expected_state == item.observed_state} for item in evaluation.executions)
    body = {"cells": cells, "accepted": all(item["passed"] for item in cells)}
    return EvidenceReleaseScenarioMatrix(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseScenarioMatrix", "evaluate_evidence_release_scenarios"]
