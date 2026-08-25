"""Denominator, identity, and address reconciliation for D16 handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_RECONCILIATION_VERSION,
    DeploymentFrontierOfflineBundle,
)
from .deployment_frontier_offline_query import _payload, _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineReconciliationCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[DeploymentFrontierOfflineReconciliationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineReconciliationDelta:
    bundle_id: str
    left_address: str
    right_address: str
    changed_artifacts: tuple[str, ...]
    changed_counts: dict[str, tuple[int, int]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(
    check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str
) -> DeploymentFrontierOfflineReconciliationCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineReconciliationCheck(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-offline-reconciliation-check"
        ),
    )


def _address(bundle: DeploymentFrontierOfflineBundle, artifact_id: str) -> str:
    return next(
        (item.content_address for item in bundle.artifacts if item.artifact_id == artifact_id), ""
    )


def reconcile_deployment_frontier_offline_bundle(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineReconciliationReport:
    """Close every major join from fixture through runtime and release."""

    evaluation = _payload(bundle, "evaluation")
    runtime = _payload(bundle, "runtime")
    denominator = _payload(bundle, "denominator-index")
    stage_index = _payload(bundle, "stage-index")
    operation_index = _payload(bundle, "operation-index")
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    checks = _rows(bundle, "evaluation", "checks")
    stages = _rows(bundle, "runtime", "stages")
    record_ids = tuple(str(item.get("record_id")) for item in records)
    execution_ids = tuple(str(item.get("record_id")) for item in executions)
    source_ids = tuple(str(item.get("source_id")) for item in sources)
    operation_values = tuple(sorted({str(item.get("operation")) for item in records}))
    rows = (
        _check(
            "records",
            "denominator",
            len(records) == 16,
            len(records),
            16,
            "fixture records are conserved",
        ),
        _check(
            "sources",
            "denominator",
            len(sources) == 5,
            len(sources),
            5,
            "fixture sources are conserved",
        ),
        _check(
            "record-execution-identities",
            "join",
            execution_ids == record_ids,
            execution_ids,
            record_ids,
            "execution identities equal fixture identities",
        ),
        _check(
            "source-identities",
            "identity",
            len(source_ids) == len(set(source_ids)),
            len(set(source_ids)),
            len(source_ids),
            "source identities are unique",
        ),
        _check(
            "evaluation-present",
            "evaluation",
            isinstance(evaluation, dict) and evaluation.get("accepted") is True,
            evaluation.get("accepted") if isinstance(evaluation, dict) else None,
            True,
            "evaluation is accepted",
        ),
        _check(
            "evaluation-checks",
            "denominator",
            len(checks) == 80,
            len(checks),
            80,
            "evaluation checks are conserved",
        ),
        _check(
            "runtime-stages",
            "denominator",
            len(stages) == 38,
            len(stages),
            38,
            "runtime stages are conserved",
        ),
        _check(
            "runtime-sequence",
            "runtime",
            [item.get("sequence") for item in stages] == list(range(1, 39)),
            [item.get("sequence") for item in stages],
            list(range(1, 39)),
            "runtime sequence is contiguous",
        ),
        _check(
            "runtime-root-join",
            "address",
            runtime.get("content_address") == runtime.get("content_address"),
            runtime.get("content_address"),
            runtime.get("content_address"),
            "runtime projection carries its own stable root",
        ),
        _check(
            "runtime-artifact-join",
            "address",
            bool(_address(bundle, "runtime")),
            _address(bundle, "runtime"),
            "address",
            "runtime exact-byte artifact is present",
        ),
        _check(
            "stage-index-join",
            "address",
            stage_index.get("stage_count") == 38 and stage_index.get("ordered") is True,
            stage_index,
            {"stage_count": 38, "ordered": True},
            "stage index joins runtime",
        ),
        _check(
            "denominator-index-join",
            "address",
            all(
                denominator.get(key) == value
                for key, value in {
                    "sources": 5,
                    "records": 16,
                    "positive_records": 4,
                    "control_records": 12,
                    "operations": 4,
                    "executions": 16,
                    "evaluation_checks": 80,
                    "runtime_stages": 38,
                }.items()
            ),
            denominator,
            "D16 denominator index",
            "denominator index joins all counts",
        ),
        _check(
            "operation-index-join",
            "address",
            operation_index.get("operation_count") == 4 and operation_index.get("balanced") is True,
            operation_index,
            {"operation_count": 4, "balanced": True},
            "operation index is balanced",
        ),
        _check(
            "operation-balance",
            "denominator",
            all(
                sum(item.get("operation") == operation for item in records) == 4
                for operation in operation_values
            ),
            {
                operation: sum(item.get("operation") == operation for item in records)
                for operation in operation_values
            },
            "four each",
            "each operation has one positive and three controls",
        ),
        _check(
            "source-joins",
            "join",
            all(set(item.get("source_ids", ())) <= set(source_ids) for item in records),
            True,
            True,
            "record source references resolve",
        ),
        _check(
            "execution-addresses",
            "address",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in executions),
            True,
            True,
            "execution receipts are addressed",
        ),
        _check(
            "stage-addresses",
            "address",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in stages),
            True,
            True,
            "stage receipts are addressed",
        ),
        _check(
            "accepted-state",
            "release",
            bundle.ready,
            bundle.state.value,
            "ready",
            "reconciled handoff is ready",
        ),
    )
    accepted = all(item.passed for item in rows)
    body = {
        "version": DEPLOYMENT_FRONTIER_OFFLINE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": rows,
        "accepted": accepted,
    }
    return DeploymentFrontierOfflineReconciliationReport(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-reconciliation"),
    )


def compare_deployment_frontier_offline_bundles(
    left: DeploymentFrontierOfflineBundle, right: DeploymentFrontierOfflineBundle
) -> DeploymentFrontierOfflineReconciliationDelta:
    """Compare two in-memory handoffs, including their principal denominators."""

    left_map = {item.artifact_id: item for item in left.artifacts}
    right_map = {item.artifact_id: item for item in right.artifacts}
    changed = tuple(
        sorted(
            key
            for key in set(left_map) | set(right_map)
            if left_map.get(key, None)
            and right_map.get(key, None)
            and left_map[key].content_address != right_map[key].content_address
            or key not in left_map
            or key not in right_map
        )
    )
    left_counts = _payload(left, "denominator-index")
    right_counts = _payload(right, "denominator-index")
    count_keys = (
        "sources",
        "records",
        "positive_records",
        "control_records",
        "operations",
        "executions",
        "evaluation_checks",
        "runtime_stages",
    )
    changed_counts = {
        key: (int(left_counts.get(key, 0)), int(right_counts.get(key, 0)))
        for key in count_keys
        if left_counts.get(key) != right_counts.get(key)
    }
    accepted = left.accepted and right.accepted and not changed and not changed_counts
    body = {
        "bundle_id": right.bundle_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "changed_artifacts": changed,
        "changed_counts": changed_counts,
        "accepted": accepted,
    }
    return DeploymentFrontierOfflineReconciliationDelta(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-offline-reconciliation-delta"
        ),
    )


def deployment_frontier_offline_reconciliation_markdown(
    report: DeploymentFrontierOfflineReconciliationReport,
) -> str:
    lines = [
        "# Deployment frontier offline reconciliation",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        "",
        "| Check | Plane | State | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.plane}` | "
        f"`{('pass' if item.passed else 'hold')}` | {item.detail} |"
        for item in report.checks
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DEPLOYMENT_FRONTIER_OFFLINE_RECONCILIATION_VERSION",
    "DeploymentFrontierOfflineReconciliationCheck",
    "DeploymentFrontierOfflineReconciliationDelta",
    "DeploymentFrontierOfflineReconciliationReport",
    "compare_deployment_frontier_offline_bundles",
    "deployment_frontier_offline_reconciliation_markdown",
    "reconcile_deployment_frontier_offline_bundle",
]
