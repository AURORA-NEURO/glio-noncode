"""Blocking quality gate for the evidence-release frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseQualityReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_evidence_release_quality_gate(audit: Any, evaluation: Any, adapters: Any, schema: Any, reconciliation: Any) -> EvidenceReleaseQualityReport:
    checks = ({"check_id": "data", "passed": audit.accepted}, {"check_id": "fixture", "passed": evaluation.accepted}, {"check_id": "adapter-count", "passed": len(adapters.adapters) == 4}, {"check_id": "schema-version", "passed": schema.version == "evidence-release-schema-v1"}, {"check_id": "reconciliation", "passed": reconciliation.accepted})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return EvidenceReleaseQualityReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseQualityReport", "run_evidence_release_quality_gate"]
