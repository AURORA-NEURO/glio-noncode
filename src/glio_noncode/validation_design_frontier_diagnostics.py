"""Severity and operator diagnosis for issue-bearing planning rows."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignDiagnostics:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def diagnose_validation_design(evaluation: Any) -> ValidationDesignDiagnostics:
    high = {"context_mismatch", "invalid_payload", "schema_invalid", "constructs_missing"}
    rows = tuple({"record_id": item.record_id, "issue_codes": item.issue_codes, "severity": "high" if any(code in high for code in item.issue_codes) else "normal" if item.issue_codes else "none", "action": "quarantine" if item.observed_state.value == "blocked" else "review" if item.issue_codes else "retain"} for item in evaluation.executions)
    body = {"rows": rows, "accepted": len(rows) == len(evaluation.executions) and all(row["action"] for row in rows)}
    return ValidationDesignDiagnostics(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignDiagnostics", "diagnose_validation_design"]
