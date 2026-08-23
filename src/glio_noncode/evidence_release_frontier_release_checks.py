"""Independent release checks over quality, integrity, and compatibility."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseCheckReport:
    checks: tuple[dict[str, Any], ...]
    passed: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_checks(quality: Any, integrity: Any, compatibility: Any) -> EvidenceReleaseCheckReport:
    checks = ({"check_id": "quality", "passed": quality.accepted}, {"check_id": "integrity", "passed": integrity.accepted}, {"check_id": "compatibility", "passed": compatibility.accepted})
    body = {"checks": checks, "passed": all(item["passed"] for item in checks)}
    return EvidenceReleaseCheckReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseCheckReport", "evaluate_evidence_release_checks"]
