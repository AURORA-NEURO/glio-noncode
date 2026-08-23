"""Retention rules for aggregate inputs, receipts, and review artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationRetentionRule:
    artifact_class: str
    retention_days: int | None
    storage_scope: str
    deletion_allowed: bool
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationRetentionReport:
    report_id: str
    rules: tuple[CohortFoundationRetentionRule, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_retention_report() -> CohortFoundationRetentionReport:
    definitions = (
        ("public-aggregate-fixture", None, "repository", False, "versioned evidence fixture remains reproducible"),
        ("execution-receipt", None, "release-bundle", False, "content receipt supports replay"),
        ("review-queue", 365, "review-store", True, "review process may expire after audit window"),
        ("quarantine-reference", 730, "quarantine-store", True, "foreign or malformed references are retained for audit"),
        ("export-manifest", None, "release-bundle", False, "released research manifest is immutable"),
    )
    rules = tuple(CohortFoundationRetentionRule(artifact_class, days, scope, deletion, rationale, content_hash((artifact_class, days, scope, deletion, rationale))) for artifact_class, days, scope, deletion, rationale in definitions)
    body = {"report_id": "cohort-foundation-frontier-retention", "rules": rules}
    return CohortFoundationRetentionReport(body["report_id"], rules, len(rules) == 5 and any(item.deletion_allowed for item in rules) and any(not item.deletion_allowed for item in rules), content_hash(body))


__all__ = ["CohortFoundationRetentionReport", "CohortFoundationRetentionRule", "default_cohort_foundation_frontier_retention_report"]
