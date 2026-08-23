"""Retention and deletion boundaries for release artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_package import CohortAlphaFrontierPackageManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRetentionRule:
    artifact_class: str
    minimum_days: int
    immutable: bool
    deletion_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRetentionPlan:
    rules: tuple[CohortAlphaFrontierRetentionRule, ...]
    package_id: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_retention_plan(package: CohortAlphaFrontierPackageManifest) -> CohortAlphaFrontierRetentionPlan:
    raw = (("source_receipt", 3650, True, "never while release is referenced"), ("fixture", 3650, True, "only after superseding release and audit closure"), ("evaluation", 3650, True, "only after superseding release and audit closure"), ("review_queue", 730, False, "after all review items are resolved"), ("transient_export", 30, False, "after package verification"))
    rules = tuple(CohortAlphaFrontierRetentionRule(artifact_class, days, immutable, deletion, content_hash({"class": artifact_class, "days": days, "immutable": immutable, "deletion": deletion}, prefix="alpha-retention")) for artifact_class, days, immutable, deletion in raw)
    return CohortAlphaFrontierRetentionPlan(rules, package.package_id, package.accepted and len(rules) == 5 and all(item.minimum_days > 0 for item in rules), content_hash({"rules": rules, "package": package.package_id}, prefix="alpha-retention-plan"))


__all__ = ["CohortAlphaFrontierRetentionPlan", "CohortAlphaFrontierRetentionRule", "build_cohort_alpha_frontier_retention_plan"]
