"""Deterministic replay comparison for the public planning fixture."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .validation_design_frontier_fixture_eval import evaluate_validation_design_fixture

@dataclass(frozen=True, slots=True)
class ValidationDesignReplayReport:
    first_address: str
    second_address: str
    row_addresses: tuple[str, ...]
    deterministic: bool
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def replay_validation_design_evaluation(fixture: Any, evaluation: Any) -> ValidationDesignReplayReport:
    second = evaluate_validation_design_fixture(fixture)
    rows = tuple(item.content_address for item in second.executions)
    deterministic = evaluation.content_address == second.content_address and all(item.startswith("sha256:") for item in rows)
    body = {"first_address": evaluation.content_address, "second_address": second.content_address, "row_addresses": rows, "deterministic": deterministic, "accepted": deterministic}
    return ValidationDesignReplayReport(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReplayReport", "replay_validation_design_evaluation"]
