"""D10 report projections."""

from __future__ import annotations

import json
from typing import Any

from .link_graph_architecture_contracts import LinkGraphArchitectureRuntime, addressed
from .link_graph_architecture_depth import (
    assess_link_graph_architecture_depth,
    link_graph_architecture_depth_percent,
)
from .link_graph_architecture_lineage import build_link_graph_architecture_lineage
from .link_graph_architecture_metrics import link_graph_architecture_metrics
from .link_graph_architecture_review import link_graph_architecture_review_summary


def build_link_graph_architecture_report(runtime: LinkGraphArchitectureRuntime) -> dict[str, Any]:
    depth = assess_link_graph_architecture_depth(runtime.fixture, runtime.evaluation)
    report = {
        "report_id": "d10-link-graph-architecture-report",
        "fixture": runtime.fixture.to_dict(include_payload=False),
        "release": runtime.release.to_dict(),
        "accepted": runtime.accepted,
        "metrics": link_graph_architecture_metrics(runtime.fixture, runtime.evaluation),
        "depth": depth.to_dict()
        | {"completion_percent": link_graph_architecture_depth_percent(depth)},
        "review": link_graph_architecture_review_summary(runtime.review_queue),
        "lineage": build_link_graph_architecture_lineage(runtime.fixture),
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
    }
    return report | {"content_address": addressed(report, "link-report")}


def link_graph_architecture_report_json(runtime: LinkGraphArchitectureRuntime) -> str:
    return (
        json.dumps(
            build_link_graph_architecture_report(runtime),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def link_graph_architecture_report_lines(runtime: LinkGraphArchitectureRuntime) -> tuple[str, ...]:
    metrics = link_graph_architecture_metrics(runtime.fixture, runtime.evaluation)
    return (
        "D10 Regulatory Link Graph & Target Association",
        f"fixture={runtime.fixture.fixture_id}",
        f"state={runtime.release.state.value} accepted={runtime.accepted}",
        f"sources={metrics['source_count']} operations={metrics['operation_count']} "
        f"cases={metrics['case_count']}",
        f"checks={len(runtime.evaluation.checks)} stages={len(runtime.stages)}",
    )


__all__ = [
    "build_link_graph_architecture_report",
    "link_graph_architecture_report_json",
    "link_graph_architecture_report_lines",
]
