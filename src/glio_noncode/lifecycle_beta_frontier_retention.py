"""Retention requirements for source, execution, review, and release receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRetentionRule:
    rule_id: str
    artifact_class: str
    required: bool
    minimum_count: int
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRetentionReport:
    rules: tuple[LifecycleBetaFrontierRetentionRule, ...]
    observed_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_retention_report(fixture: LifecycleBetaFrontierFixture, runtime: LifecycleBetaFrontierRuntimeReport) -> LifecycleBetaFrontierRetentionReport:
    rules_data = (("sources", 9, "retain every public source receipt"), ("records", 32, "retain positive and control rows"), ("executions", 32, "retain every operation receipt"), ("stages", 25, "retain ordered runtime stages"), ("checks", 166, "retain evaluation assertions"))
    rules = []
    counts = {"sources": len(fixture.sources), "records": len(fixture.records), "executions": len(runtime.evaluation.executions), "stages": len(runtime.stages), "checks": len(runtime.evaluation.checks)}
    for artifact_class, minimum_count, rationale in rules_data:
        body = {"rule_id": f"retain:{artifact_class}", "artifact_class": artifact_class, "required": True, "minimum_count": minimum_count, "rationale": rationale}
        rules.append(LifecycleBetaFrontierRetentionRule(**body, content_address=content_hash(body)))
    accepted = all(counts[item.artifact_class] >= item.minimum_count for item in rules)
    return LifecycleBetaFrontierRetentionReport(tuple(rules), counts, accepted, content_hash({"rules": tuple(rules), "counts": counts, "accepted": accepted}))


__all__ = ["LifecycleBetaFrontierRetentionReport", "LifecycleBetaFrontierRetentionRule", "build_lifecycle_beta_frontier_retention_report"]
