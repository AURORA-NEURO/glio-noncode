"""D09 runtime report and operation register rendering."""

from __future__ import annotations

import json
from typing import Any

from .topology_architecture_contracts import TopologyArchitectureRuntime, addressed
from .topology_architecture_depth import (
    assess_topology_architecture_depth,
    topology_architecture_depth_percent,
)
from .topology_architecture_lineage import build_topology_architecture_lineage
from .topology_architecture_metrics import topology_architecture_metrics
from .topology_architecture_review import topology_architecture_review_summary


def build_topology_architecture_report(runtime: TopologyArchitectureRuntime) -> dict[str, Any]:
    depth = assess_topology_architecture_depth(runtime.fixture, runtime.evaluation)
    report = {
        "report_id": "d09-topology-architecture-report",
        "fixture": runtime.fixture.to_dict(include_payload=False),
        "release": runtime.release.to_dict(),
        "accepted": runtime.accepted,
        "metrics": topology_architecture_metrics(runtime.fixture, runtime.evaluation),
        "depth": depth.to_dict()
        | {"completion_percent": topology_architecture_depth_percent(depth)},
        "review": topology_architecture_review_summary(runtime.review_queue),
        "lineage": build_topology_architecture_lineage(runtime.fixture),
        "stage_count": len(runtime.stages),
        "operations": [
            {
                "operation_id": item.operation_id,
                "operation": item.operation.value,
                "family": item.family.value,
                "plane": item.plane.value,
            }
            for item in runtime.fixture.operations
        ],
    }
    return report | {"content_address": addressed(report, "topology-report")}


def topology_architecture_report_json(runtime: TopologyArchitectureRuntime) -> str:
    return (
        json.dumps(
            build_topology_architecture_report(runtime),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def topology_architecture_report_lines(runtime: TopologyArchitectureRuntime) -> tuple[str, ...]:
    metrics = topology_architecture_metrics(runtime.fixture, runtime.evaluation)
    return (
        "D09 3D Genome & Regulatory Topology",
        f"fixture={runtime.fixture.fixture_id}",
        f"state={runtime.release.state.value} accepted={runtime.accepted}",
        f"sources={metrics['source_count']} operations={metrics['operation_count']} "
        f"cases={metrics['case_count']}",
        f"checks={len(runtime.evaluation.checks)} stages={len(runtime.stages)}",
    )


__all__ = [
    "build_topology_architecture_report",
    "topology_architecture_report_json",
    "topology_architecture_report_lines",
]
