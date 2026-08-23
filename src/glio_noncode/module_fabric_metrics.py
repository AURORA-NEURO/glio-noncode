"""Conserved metrics for module-fabric evaluations."""

from __future__ import annotations

from collections import Counter, defaultdict

from .module_fabric_contracts import FabricEvaluation, FabricFixture, FabricMetrics, FabricReferenceState, FabricRole, FabricState
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import content_hash


def measure_module_fabric(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> FabricMetrics:
    value = fixture or default_module_fabric_fixture()
    if evaluation is None:
        from .module_fabric_fixture_eval import evaluate_module_fabric_fixture

        evaluation = evaluate_module_fabric_fixture(value)
    states = Counter(item.observed_state.value for item in evaluation.executions)
    by_domain: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "positive": 0, "control": 0, "accepted": 0, "review": 0, "references": 0, "failed_references": 0})
    implementation_count = 0
    test_count = 0
    resolved_count = 0
    failed_count = 0
    for execution in evaluation.executions:
        row = by_domain[execution.domain_id]
        row["records"] += 1
        row[execution.role.value] += 1
        row[execution.observed_state.value] = row.get(execution.observed_state.value, 0) + 1
        references = (*execution.implementation_receipts, *execution.test_receipts)
        row["references"] += len(references)
        row["failed_references"] += sum(item.state is FabricReferenceState.FAILED for item in references)
        implementation_count += len(execution.implementation_receipts)
        test_count += len(execution.test_receipts)
        resolved_count += sum(item.state is FabricReferenceState.RESOLVED for item in references)
        failed_count += sum(item.state is FabricReferenceState.FAILED for item in references)
    body = {
        "fixture_id": value.fixture_id,
        "record_count": len(value.records),
        "domain_count": len(by_domain),
        "positive_count": sum(item.role is FabricRole.POSITIVE for item in value.records),
        "control_count": sum(item.role is FabricRole.CONTROL for item in value.records),
        "accepted_count": states[FabricState.ACCEPTED.value],
        "review_count": states[FabricState.REVIEW.value],
        "abstained_count": states[FabricState.ABSTAINED.value],
        "rejected_count": states[FabricState.REJECTED.value],
        "implementation_reference_count": implementation_count,
        "test_reference_count": test_count,
        "resolved_reference_count": resolved_count,
        "failed_reference_count": failed_count,
        "by_domain": dict(sorted(by_domain.items())),
    }
    return FabricMetrics(**body, content_address=content_hash(body, prefix="module-fabric-metrics"))


def module_fabric_state_counts(metrics: FabricMetrics) -> dict[str, int]:
    return {
        FabricState.ACCEPTED.value: metrics.accepted_count,
        FabricState.REVIEW.value: metrics.review_count,
        FabricState.ABSTAINED.value: metrics.abstained_count,
        FabricState.REJECTED.value: metrics.rejected_count,
    }


def module_fabric_domain_counts(metrics: FabricMetrics) -> dict[str, int]:
    return {domain: int(values.get("records", 0)) for domain, values in metrics.by_domain.items()}


def module_fabric_reference_rate(metrics: FabricMetrics) -> float:
    total = metrics.implementation_reference_count + metrics.test_reference_count
    return round(metrics.resolved_reference_count / max(1, total), 6)


__all__ = [
    "measure_module_fabric",
    "module_fabric_domain_counts",
    "module_fabric_reference_rate",
    "module_fabric_state_counts",
]
