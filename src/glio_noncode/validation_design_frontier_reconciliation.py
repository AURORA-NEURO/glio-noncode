"""Expected-versus-observed reconciliation for every planning row."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReconciliation:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    mismatch_count: int
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def reconcile_validation_design(fixture: Any, evaluation: Any) -> ValidationDesignReconciliation:
    rows = tuple({"record_id": record.record_id, "expected_state": record.expected_state.value, "observed_state": execution.observed_state.value, "expected_issues": record.expected_issue_codes, "observed_issues": execution.issue_codes, "state_match": record.expected_state == execution.observed_state, "issue_match": set(record.expected_issue_codes) <= set(execution.issue_codes)} for record, execution in zip(fixture.records, evaluation.executions, strict=True))
    mismatches = sum(not (row["state_match"] and row["issue_match"]) for row in rows)
    body = {"rows": rows, "accepted": mismatches == 0, "mismatch_count": mismatches}
    return ValidationDesignReconciliation(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReconciliation", "reconcile_validation_design"]
