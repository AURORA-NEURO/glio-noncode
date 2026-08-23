"""Weighted completeness scoring with explicit missing-field explanations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureCase, IntakeArchitectureState, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitectureCompletenessScore:
    case_id: str
    score: float
    required_weight: float
    present_weight: float
    missing_fields: tuple[str, ...]
    state: IntakeArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "score": self.score,
            "required_weight": self.required_weight,
            "present_weight": self.present_weight,
            "missing_fields": list(self.missing_fields),
            "state": self.state.value,
            "content_address": self.content_address,
        }


def score_intake_completeness(case: IntakeArchitectureCase) -> IntakeArchitectureCompletenessScore:
    payload = case.payload
    fields = payload.get("required_fields", ("operation_id", "capability_id", "context_key", "source_record", "variant"))
    weights = payload.get("weights", {})
    if not isinstance(fields, (list, tuple)):
        fields = ()
    total = 0.0
    present = 0.0
    missing: list[str] = []
    for name in fields:
        key = str(name)
        weight = float(weights.get(key, 1.0)) if isinstance(weights, Mapping) else 1.0
        total += weight
        value = payload.get(key)
        if value not in (None, "", (), [], {}):
            present += weight
        else:
            missing.append(key)
    score = round(present / total, 4) if total else 0.0
    state = IntakeArchitectureState.ACCEPTED if score >= 0.999 and not missing else IntakeArchitectureState.REVIEW
    body = {"case_id": case.case_id, "score": score, "required_weight": total, "present_weight": present, "missing_fields": tuple(missing), "state": state}
    return IntakeArchitectureCompletenessScore(**body, content_address=addressed(body, "intake-completeness"))


__all__ = ["IntakeArchitectureCompletenessScore", "score_intake_completeness"]
