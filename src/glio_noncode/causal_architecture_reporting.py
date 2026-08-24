"""D11 report projections."""

from __future__ import annotations

import json
from typing import Any

from .causal_architecture_contracts import CausalArchitectureRuntime, addressed
from .causal_architecture_depth import (
    assess_causal_architecture_depth,
    causal_architecture_depth_percent,
)
from .causal_architecture_lineage import build_causal_architecture_lineage
from .causal_architecture_metrics import causal_architecture_metrics
from .causal_architecture_review import causal_architecture_review_summary


def build_causal_architecture_report(runtime: CausalArchitectureRuntime) -> dict[str, Any]:
    depth = assess_causal_architecture_depth(runtime.fixture, runtime.evaluation)
    report = {
        "report_id": "d11-causal-architecture-report",
        "fixture": runtime.fixture.to_dict(include_payload=False),
        "release": runtime.release.to_dict(),
        "accepted": runtime.accepted,
        "metrics": causal_architecture_metrics(runtime.fixture, runtime.evaluation),
        "depth": depth.to_dict() | {"completion_percent": causal_architecture_depth_percent(depth)},
        "review": causal_architecture_review_summary(runtime.review_queue),
        "lineage": build_causal_architecture_lineage(runtime.fixture),
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
    }
    return report | {"content_address": addressed(report, "causal-report")}


def causal_architecture_report_json(runtime: CausalArchitectureRuntime) -> str:
    return (
        json.dumps(
            build_causal_architecture_report(runtime), ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    )


def causal_architecture_report_lines(runtime: CausalArchitectureRuntime) -> tuple[str, ...]:
    metrics = causal_architecture_metrics(runtime.fixture, runtime.evaluation)
    return (
        "D11 Causal Evidence Research Aggregate",
        f"fixture={runtime.fixture.fixture_id}",
        f"state={runtime.release.state.value} accepted={runtime.accepted}",
        (
            f"sources={metrics['source_count']} operations={metrics['operation_count']} "
            f"cases={metrics['case_count']}"
        ),
        f"checks={len(runtime.evaluation.checks)} stages={len(runtime.stages)}",
    )


__all__ = [
    "build_causal_architecture_report",
    "causal_architecture_report_json",
    "causal_architecture_report_lines",
]
