"""Review-safe projections materialized from the D15 evaluation."""

from __future__ import annotations

from .workbench_architecture_contracts import (
    WorkbenchArchitectureArtifact,
    WorkbenchArchitectureDataAudit,
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureLedger,
    WorkbenchArchitectureReviewQueue,
    addressed,
)
from .workbench_architecture_lineage import workbench_architecture_lineage_rows
from .workbench_architecture_metrics import workbench_architecture_metrics
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def build_workbench_architecture_artifacts(
    fixture: WorkbenchArchitectureFixture | None = None,
    audit: WorkbenchArchitectureDataAudit | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
    review_queue: WorkbenchArchitectureReviewQueue | None = None,
    ledger: WorkbenchArchitectureLedger | None = None,
) -> tuple[WorkbenchArchitectureArtifact, ...]:
    selected = fixture or default_workbench_architecture_fixture()
    if audit is None:
        from .workbench_architecture_public_data import audit_workbench_architecture_data

        audit = audit_workbench_architecture_data(selected)
    if evaluation is None:
        from .workbench_architecture_operations import evaluate_workbench_architecture_fixture

        evaluation = evaluate_workbench_architecture_fixture(selected)
    if review_queue is None:
        from .workbench_architecture_review import build_workbench_architecture_review_queue

        review_queue = build_workbench_architecture_review_queue(evaluation, selected)
    if ledger is None:
        from .workbench_architecture_ledger import build_workbench_architecture_ledger

        ledger = build_workbench_architecture_ledger(selected, evaluation)
    metrics = workbench_architecture_metrics(selected, evaluation)
    projections = (
        ("fixture", "public_fixture", len(selected.cases), (selected.content_address,)),
        (
            "source-register",
            "source_register",
            len(selected.sources),
            tuple(item.content_address for item in selected.sources),
        ),
        (
            "evaluation",
            "evaluation_receipts",
            len(evaluation.receipts),
            (evaluation.content_address,),
        ),
        (
            "review-queue",
            "review_projection",
            len(review_queue.items),
            (review_queue.content_address,),
        ),
        (
            "lineage",
            "lineage_projection",
            len(workbench_architecture_lineage_rows(selected)),
            (selected.content_address,),
        ),
        (
            "metrics-ledger",
            "metrics_and_ledger",
            len(ledger.events),
            (addressed(metrics, "workbench-architecture-metrics"), ledger.content_address),
        ),
    )
    artifacts = []
    for artifact_id, artifact_type, record_count, sources in projections:
        body = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "visibility": "public_aggregate",
            "source_addresses": sources,
            "record_count": record_count,
            "review_safe": audit.accepted and all(sources),
        }
        artifacts.append(
            WorkbenchArchitectureArtifact(
                artifact_id,
                artifact_type,
                "public_aggregate",
                addressed(body, "workbench-architecture-artifact"),
                tuple(sources),
                record_count,
                bool(body["review_safe"]),
            )
        )
    return tuple(artifacts)


def workbench_architecture_artifacts_are_safe(
    artifacts: tuple[WorkbenchArchitectureArtifact, ...],
) -> bool:
    return (
        len(artifacts) == 6
        and len({item.artifact_id for item in artifacts}) == len(artifacts)
        and all(
            item.visibility == "public_aggregate" and item.review_safe and item.content_address
            for item in artifacts
        )
    )


def workbench_architecture_artifact_summary(
    artifacts: tuple[WorkbenchArchitectureArtifact, ...],
) -> dict[str, object]:
    return {
        "artifact_count": len(artifacts),
        "safe": workbench_architecture_artifacts_are_safe(artifacts),
        "record_count": sum(item.record_count for item in artifacts),
        "types": sorted(item.artifact_type for item in artifacts),
    }


__all__ = [
    "build_workbench_architecture_artifacts",
    "workbench_architecture_artifact_summary",
    "workbench_architecture_artifacts_are_safe",
]
