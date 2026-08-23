"""Quarantine ledger for malformed guide and oligo rows."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class GuideQuarantineRow:
    row_number: int
    issue_code: str
    row_address: str
    remediation: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def quarantine_guide_row(row_number: int, issue_code: str, row_address: str) -> GuideQuarantineRow:
    remediation = "repair required identity or sequence fields and rerun adaptation"
    body = {"row_number": row_number, "issue_code": issue_code, "row_address": row_address, "remediation": remediation}
    return GuideQuarantineRow(**body, content_address=content_hash(body, prefix="guide-quarantine"))

__all__ = ["GuideQuarantineRow", "quarantine_guide_row"]
