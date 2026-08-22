"""Depth audit for the Domain 15 C01–C04 workspace frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_metrics import WorkspaceFrontierMetricsReport
from .workspace_frontier_public_data import WorkspaceFrontierFixture
from .workspace_frontier_reconciliation import WorkspaceFrontierReconciliation
from .workspace_frontier_runtime import WorkspaceFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierDepthAudit:
    fixture_id: str
    checks: tuple[WorkspaceFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count, "failed_check_ids": list(self.failed_check_ids)}


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> WorkspaceFrontierDepthCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return WorkspaceFrontierDepthCheck(**body, content_address=content_hash(body))


def audit_workspace_frontier_depth(fixture: WorkspaceFrontierFixture | None = None, evaluation: WorkspaceFrontierEvaluation | None = None, metrics: WorkspaceFrontierMetricsReport | None = None, reconciliation: WorkspaceFrontierReconciliation | None = None, runtime: WorkspaceFrontierRuntimeReport | None = None) -> WorkspaceFrontierDepthAudit:
    if runtime is not None:
        fixture = fixture or __import__("glio_noncode.workspace_frontier_public_data", fromlist=["default_workspace_frontier_fixture"]).default_workspace_frontier_fixture()
        evaluation = evaluation or runtime.evaluation
        metrics = metrics or runtime.metrics
        reconciliation = reconciliation or runtime.reconciliation
    if fixture is None or evaluation is None or metrics is None or reconciliation is None:
        from .workspace_frontier_runtime import run_workspace_frontier_runtime

        runtime = runtime or run_workspace_frontier_runtime()
        fixture = fixture or __import__("glio_noncode.workspace_frontier_public_data", fromlist=["default_workspace_frontier_fixture"]).default_workspace_frontier_fixture()
        evaluation = evaluation or runtime.evaluation
        metrics = metrics or runtime.metrics
        reconciliation = reconciliation or runtime.reconciliation
    checks = (
        _check("fixture-records", len(fixture.records) == 16, len(fixture.records), 16, "sixteen fixture records"),
        _check("fixture-positives", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "four positive records"),
        _check("fixture-controls", len(fixture.control_records) == 12, len(fixture.control_records), 12, "twelve controls"),
        _check("operation-case", sum(item.operation.value == "case_workspace" for item in fixture.records) == 4, 4, 4, "case surface coverage"),
        _check("operation-cohort", sum(item.operation.value == "cohort_workspace" for item in fixture.records) == 4, 4, 4, "cohort surface coverage"),
        _check("operation-variant", sum(item.operation.value == "variant_explorer" for item in fixture.records) == 4, 4, 4, "variant surface coverage"),
        _check("operation-track", sum(item.operation.value == "regulatory_track_browser" for item in fixture.records) == 4, 4, 4, "track surface coverage"),
        _check("evaluation-checks", len(evaluation.checks) == 120, len(evaluation.checks), 120, "record and global checks"),
        _check("evaluation-pass", evaluation.accepted, evaluation.accepted, True, "fixture evaluation accepted"),
        _check("metrics-count", len(metrics.metrics) == 13, len(metrics.metrics), 13, "descriptive metric inventory"),
        _check("reconciliation-count", len(reconciliation.items) == 16, len(reconciliation.items), 16, "reconciliation inventory"),
        _check("reconciliation-pass", reconciliation.reconciled, reconciliation.reconciled, True, "reconciliation accepted"),
        _check("source-addresses", all(item.content_address.startswith("sha256:") for item in fixture.sources), True, True, "source receipts addressed"),
        _check("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, True, "fixture records addressed"),
        _check("execution-addresses", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, True, "executions addressed"),
        _check("context-boundary", all(item.context_key == fixture.context_key for item in fixture.records), True, True, "context is exact"),
        _check("state-diversity", len({item.state for item in evaluation.executions}) >= 4, len({item.state for item in evaluation.executions}), ">=4", "positive and control states remain distinct"),
        _check("issue-diversity", len({code for item in evaluation.executions for code in item.issue_codes}) >= 5, len({code for item in evaluation.executions for code in item.issue_codes}), ">=5", "failure modes remain distinct"),
        _check("output-retention", all(item.output for item in evaluation.executions), True, True, "every execution retains output"),
        _check("metric-addresses", all(item.content_address.startswith("sha256:") for item in metrics.metrics), True, True, "metrics addressed"),
        _check("reconciliation-addresses", all(item.content_address.startswith("sha256:") for item in reconciliation.items), True, True, "reconciliation rows addressed"),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": all(item.passed for item in checks)}
    return WorkspaceFrontierDepthAudit(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierDepthAudit", "WorkspaceFrontierDepthCheck", "audit_workspace_frontier_depth"]
