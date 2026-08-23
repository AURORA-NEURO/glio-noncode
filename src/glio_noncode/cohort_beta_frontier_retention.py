"""Retention schedule for public aggregate receipts and review records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRetentionRule:
    artifact_kind: str
    retention_days: int
    deletion_policy: str
    legal_hold: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRetentionReport:
    rules: tuple[CohortBetaFrontierRetentionRule, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_retention_report() -> CohortBetaFrontierRetentionReport:
    raw = (("public_fixture", 3650, "retain immutable receipt", True), ("evaluation", 3650, "retain immutable receipt", True), ("review_queue", 730, "retain until disposition", False), ("transcript", 3650, "retain immutable receipt", True))
    values = tuple(CohortBetaFrontierRetentionRule(kind, days, policy, hold, content_hash({"kind": kind, "days": days, "policy": policy}, prefix="retention")) for kind, days, policy, hold in raw)
    return CohortBetaFrontierRetentionReport(values, all(item.retention_days > 0 for item in values), content_hash(values, prefix="retention-report"))


__all__ = ["CohortBetaFrontierRetentionReport", "CohortBetaFrontierRetentionRule", "default_cohort_beta_frontier_retention_report"]
