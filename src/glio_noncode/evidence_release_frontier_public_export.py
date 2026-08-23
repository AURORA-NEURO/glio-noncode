"""Public export projection that is safe to publish as an aggregate artifact."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleasePublicExport:
    fixture_id: str
    row_count: int
    source_count: int
    review_count: int
    blocked_count: int
    records: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_public_export(fixture: Any, evaluation: Any) -> EvidenceReleasePublicExport:
    records = tuple({"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.observed_state.value, "issue_codes": item.issue_codes, "content_address": item.content_address} for item in evaluation.executions)
    body = {"fixture_id": fixture.fixture_id, "row_count": len(records), "source_count": len(fixture.sources), "review_count": sum(item["state"] == "review" for item in records), "blocked_count": sum(item["state"] == "blocked" for item in records), "records": records}
    return EvidenceReleasePublicExport(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleasePublicExport", "build_evidence_release_public_export"]
