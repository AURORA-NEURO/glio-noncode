"""Human-readable and machine-readable D08 runtime reporting."""

from __future__ import annotations

import json
from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureRuntime, addressed
from .cell_state_architecture_data_dictionary import cell_state_architecture_data_dictionary
from .cell_state_architecture_depth import assess_cell_state_architecture_depth, depth_percent
from .cell_state_architecture_lineage import build_cell_state_architecture_lineage
from .cell_state_architecture_metrics import cell_state_architecture_metrics
from .cell_state_architecture_observability import (
    cell_state_architecture_events,
    observability_summary,
)
from .cell_state_architecture_quality import quality_summary
from .cell_state_architecture_scenarios import cell_state_architecture_scenario_matrix
from .cell_state_architecture_source_registry import build_cell_state_architecture_source_registry


def build_cell_state_architecture_report(runtime: CellStateArchitectureRuntime) -> dict[str, Any]:
    depth = assess_cell_state_architecture_depth(runtime.fixture, runtime.evaluation)
    events = cell_state_architecture_events(runtime.fixture, runtime.evaluation)
    report = {
        "report_id": "d08-cell-state-architecture-report",
        "fixture": runtime.fixture.to_dict(include_payload=False),
        "release": runtime.release.to_dict(),
        "quality": quality_summary(runtime.quality)
        | {
            "runtime_accepted": runtime.accepted,
            "evaluation_failed_check_ids": [
                item.check_id for item in runtime.evaluation.checks if not item.passed
            ],
        },
        "metrics": cell_state_architecture_metrics(runtime.fixture, runtime.evaluation),
        "depth": depth.to_dict() | {"completion_percent": depth_percent(depth)},
        "source_registry": build_cell_state_architecture_source_registry(runtime.fixture),
        "lineage": build_cell_state_architecture_lineage(runtime.fixture),
        "scenario_matrix": cell_state_architecture_scenario_matrix(runtime.fixture),
        "observability": observability_summary(events),
        "data_dictionary": cell_state_architecture_data_dictionary(),
        "stage_count": len(runtime.stages),
    }
    return report | {"content_address": addressed(report, "cell-state-report")}


def cell_state_architecture_report_json(runtime: CellStateArchitectureRuntime) -> str:
    return (
        json.dumps(
            build_cell_state_architecture_report(runtime),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def cell_state_architecture_report_lines(runtime: CellStateArchitectureRuntime) -> tuple[str, ...]:
    report = build_cell_state_architecture_report(runtime)
    metrics = report["metrics"]
    depth = report["depth"]
    return (
        "D08 Cell State, Disease Class & Territory",
        f"fixture={runtime.fixture.fixture_id}",
        f"state={runtime.release.state.value} accepted={runtime.accepted}",
        f"sources={metrics['source_count']} operations={metrics['operation_count']} "
        f"cases={metrics['case_count']}",
        f"positive={metrics['positive_count']} controls={metrics['control_count']} "
        f"checks={len(runtime.evaluation.checks)}",
        f"stages={len(runtime.stages)} depth={depth['completion_percent']}% "
        f"address={report['content_address']}",
    )


__all__ = [
    "build_cell_state_architecture_report",
    "cell_state_architecture_report_json",
    "cell_state_architecture_report_lines",
]
