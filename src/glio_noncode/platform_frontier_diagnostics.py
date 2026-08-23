"""Diagnostic summaries for platform runtime failures and counts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .platform_frontier_depth import PlatformFrontierDepthAudit
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierDiagnostic:
    diagnostic_id: str
    severity: str
    category: str
    message: str
    record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierDiagnostics:
    fixture_id: str
    diagnostics: tuple[PlatformFrontierDiagnostic, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diagnose_platform_frontier(evaluation: PlatformFrontierEvaluation, depth: PlatformFrontierDepthAudit | None = None) -> PlatformFrontierDiagnostics:
    diagnostics = []
    for row in evaluation.executions:
        if row.issue_codes:
            body = {"diagnostic_id": f"issue:{row.record_id}", "severity": "review", "category": row.operation.value, "message": ";".join(row.issue_codes), "record_ids": (row.record_id,)}
            diagnostics.append(PlatformFrontierDiagnostic(**body, content_address=content_hash(body)))
    if depth is not None and not depth.accepted:
        failed = tuple(item.check_id for item in depth.checks if not item.passed)
        body = {"diagnostic_id": "depth:failed", "severity": "blocker", "category": "depth", "message": "depth audit failed", "record_ids": failed}
        diagnostics.append(PlatformFrontierDiagnostic(**body, content_address=content_hash(body)))
    return PlatformFrontierDiagnostics(evaluation.fixture_id, tuple(diagnostics), all(item.content_address.startswith("sha256:") for item in diagnostics), content_hash(tuple(diagnostics)))


__all__ = ["PlatformFrontierDiagnostic", "PlatformFrontierDiagnostics", "diagnose_platform_frontier"]
