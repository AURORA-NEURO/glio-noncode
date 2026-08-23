"""Diagnostic counters for fast review of a runtime report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDiagnostic:
    diagnostic_id: str
    category: str
    value: Any
    threshold: Any
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDiagnostics:
    run_id: str
    rows: tuple[LifecycleBetaFrontierDiagnostic, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diagnose_lifecycle_beta_frontier(runtime: LifecycleBetaFrontierRuntimeReport) -> LifecycleBetaFrontierDiagnostics:
    rows = (
        ("stage-count", "runtime", len(runtime.stages), 25, len(runtime.stages) == 25, "ordered runtime exposes all stages"),
        ("record-count", "data", len(runtime.evaluation.executions), 32, len(runtime.evaluation.executions) == 32, "all aggregate rows execute"),
        ("accepted-positive-count", "evaluation", runtime.metrics.accepted_count, 8, runtime.metrics.accepted_count == 8, "one positive row per operation"),
        ("threshold-probe-count", "depth", runtime.thresholds.probe_count, 40, runtime.thresholds.probe_count == 40, "five threshold probes per operation"),
        ("validation-cell-count", "depth", runtime.validation_matrix.cell_count, 32, runtime.validation_matrix.cell_count == 32, "one validation cell per row"),
    )
    diagnostics = []
    for diagnostic_id, category, value, threshold, passed, detail in rows:
        body = {"diagnostic_id": diagnostic_id, "category": category, "value": value, "threshold": threshold, "passed": passed, "detail": detail}
        diagnostics.append(LifecycleBetaFrontierDiagnostic(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierDiagnostics(runtime.run_id, tuple(diagnostics), all(item.passed for item in diagnostics), content_hash({"rows": tuple(diagnostics)}))


__all__ = ["LifecycleBetaFrontierDiagnostic", "LifecycleBetaFrontierDiagnostics", "diagnose_lifecycle_beta_frontier"]
