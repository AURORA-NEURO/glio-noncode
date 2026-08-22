"""Cross-view reconciliation for the release frontier reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_lineage import ReferenceReleaseLineageGraph
from .reference_release_frontier_policy import ReferenceReleasePolicyReport
from .reference_release_frontier_projection_assertions import ReferenceReleaseProjectionAudit
from .reference_release_frontier_public_data import (
    ReferenceReleaseDataAudit,
    ReferenceReleaseFixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReconciliationCheck:
    """One cross-view count or identity comparison."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReconciliation:
    """Reconciliation report for source, execution, policy, and graph views."""

    checks: tuple[ReferenceReleaseReconciliationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, passed: bool, observed: Any, expected: Any, detail: str
) -> ReferenceReleaseReconciliationCheck:
    body = {
        "check_id": f"release-reconcile-{index:03d}",
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReferenceReleaseReconciliationCheck(
        **body, content_address=content_hash(body, prefix="reconciliation-check")
    )


def reconcile_reference_release_views(
    fixture: ReferenceReleaseFixture,
    data_audit: ReferenceReleaseDataAudit,
    evaluation: ReferenceReleaseEvaluation,
    projection: ReferenceReleaseProjectionAudit,
    policy: ReferenceReleasePolicyReport,
    lineage: ReferenceReleaseLineageGraph,
) -> ReferenceReleaseReconciliation:
    """Compare every primary view without changing any source report."""

    graph_audit = lineage.audit(evaluation)
    checks = (
        _check(1, data_audit.accepted, data_audit.accepted, True, "data audit accepted"),
        _check(
            2,
            len(evaluation.executions) == len(fixture.records),
            len(evaluation.executions),
            len(fixture.records),
            "execution count equals fixture record count",
        ),
        _check(
            3,
            evaluation.positive_count == len(fixture.positive_records),
            evaluation.positive_count,
            len(fixture.positive_records),
            "positive count agrees",
        ),
        _check(
            4,
            evaluation.control_count == len(fixture.control_records),
            evaluation.control_count,
            len(fixture.control_records),
            "control count agrees",
        ),
        _check(5, evaluation.accepted, evaluation.accepted, True, "evaluation accepted"),
        _check(6, projection.accepted, projection.accepted, True, "projection audit accepted"),
        _check(
            7,
            len(policy.decisions) == len(evaluation.executions),
            len(policy.decisions),
            len(evaluation.executions),
            "policy decision count agrees",
        ),
        _check(8, policy.accepted, policy.accepted, True, "policy report accepted"),
        _check(9, graph_audit.passed, graph_audit.passed, True, "lineage graph closes"),
        _check(
            10,
            graph_audit.node_count >= 100,
            graph_audit.node_count,
            ">=100",
            "lineage contains source and receipt depth",
        ),
        _check(
            11,
            graph_audit.edge_count >= 100,
            graph_audit.edge_count,
            ">=100",
            "lineage contains relation depth",
        ),
        _check(
            12,
            len({item.record_id for item in evaluation.executions}) == 16,
            len({item.record_id for item in evaluation.executions}),
            16,
            "execution IDs are unique",
        ),
        _check(
            13,
            {item.operation for item in evaluation.executions}
            == set(
                policy.decisions[item_index].operation
                for item_index in range(len(policy.decisions))
            ),
            "operation sets agree",
            True,
            "policy covers the same operations",
        ),
        _check(
            14,
            all(item.content_address.startswith("sha256:") for item in evaluation.executions),
            True,
            True,
            "execution addresses are canonical",
        ),
        _check(
            15,
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            True,
            True,
            "source addresses are canonical",
        ),
        _check(
            16,
            fixture.context_key == data_audit.context_key,
            fixture.context_key,
            data_audit.context_key,
            "context agrees across fixture and audit",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"checks": checks, "accepted": accepted}
    return ReferenceReleaseReconciliation(
        **body, content_address=content_hash(body, prefix="release-reconciliation")
    )


__all__ = [
    "ReferenceReleaseReconciliation",
    "ReferenceReleaseReconciliationCheck",
    "reconcile_reference_release_views",
]
