"""D12 report projections."""

from __future__ import annotations

import json
from typing import Any

from .cohort_architecture_contracts import CohortArchitectureRuntime, addressed
from .cohort_architecture_depth import (
    assess_cohort_architecture_depth,
    cohort_architecture_depth_percent,
)
from .cohort_architecture_lineage import build_cohort_architecture_lineage
from .cohort_architecture_metrics import cohort_architecture_metrics
from .cohort_architecture_review import cohort_architecture_review_summary


def build_cohort_architecture_report(runtime: CohortArchitectureRuntime) -> dict[str, Any]:
    depth = assess_cohort_architecture_depth(runtime.fixture, runtime.evaluation)
    report = {
        "report_id": "d12-cohort-architecture-report",
        "fixture": runtime.fixture.to_dict(include_payload=False),
        "release": runtime.release.to_dict(),
        "accepted": runtime.accepted,
        "metrics": cohort_architecture_metrics(runtime.fixture, runtime.evaluation),
        "depth": depth.to_dict() | {"completion_percent": cohort_architecture_depth_percent(depth)},
        "review": cohort_architecture_review_summary(runtime.review_queue),
        "lineage": build_cohort_architecture_lineage(runtime.fixture),
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
        "family_contexts": dict(runtime.fixture.family_contexts),
    }
    return report | {"content_address": addressed(report, "cohort-report")}


def cohort_architecture_report_json(runtime: CohortArchitectureRuntime) -> str:
    return (
        json.dumps(
            build_cohort_architecture_report(runtime), ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    )


def cohort_architecture_report_lines(runtime: CohortArchitectureRuntime) -> tuple[str, ...]:
    metrics = cohort_architecture_metrics(runtime.fixture, runtime.evaluation)
    return (
        "D12 Cohort Discovery and Longitudinal Aggregate",
        f"fixture={runtime.fixture.fixture_id}",
        f"state={runtime.release.state.value} accepted={runtime.accepted}",
        (
            f"sources={metrics['source_count']} operations={metrics['operation_count']} "
            f"cases={metrics['case_count']}"
        ),
        f"checks={len(runtime.evaluation.checks)} stages={len(runtime.stages)}",
    )


__all__ = [
    "build_cohort_architecture_report",
    "cohort_architecture_report_json",
    "cohort_architecture_report_lines",
]
