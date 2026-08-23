"""Structured issue diagnostics with stable row references."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseDiagnostics:
    findings: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def diagnose_evidence_release(evaluation: Any) -> EvidenceReleaseDiagnostics:
    findings = tuple({"record_id": row.record_id, "severity": "high" if row.observed_state.value == "blocked" else "medium" if row.observed_state.value in {"review", "rejected"} else "info", "issues": row.issue_codes} for row in evaluation.executions)
    body = {"findings": findings, "accepted": all("record_id" in item for item in findings)}
    return EvidenceReleaseDiagnostics(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseDiagnostics", "diagnose_evidence_release"]
