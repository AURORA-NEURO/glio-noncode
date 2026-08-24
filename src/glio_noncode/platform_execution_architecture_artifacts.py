"""Six review-safe projections for D16."""

from __future__ import annotations

from .platform_execution_architecture_contracts import (
    PlatformExecutionArtifact,
    PlatformExecutionDataAudit,
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    PlatformExecutionLedger,
    PlatformExecutionReviewQueue,
    addressed,
)
from .platform_execution_architecture_ledger import platform_execution_ledger_is_closed
from .platform_execution_architecture_metrics import platform_execution_metrics
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def build_platform_execution_artifacts(
    fixture: PlatformExecutionFixture | None = None,
    audit: PlatformExecutionDataAudit | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
    review_queue: PlatformExecutionReviewQueue | None = None,
    ledger: PlatformExecutionLedger | None = None,
) -> tuple[PlatformExecutionArtifact, ...]:
    selected = fixture or default_platform_execution_fixture()
    if audit is None:
        from .platform_execution_architecture_public_data import audit_platform_execution_data

        audit = audit_platform_execution_data(selected)
    if evaluation is None:
        from .platform_execution_architecture_operations import evaluate_platform_execution_fixture

        evaluation = evaluate_platform_execution_fixture(selected)
    if review_queue is None:
        from .platform_execution_architecture_review import build_platform_execution_review_queue

        review_queue = build_platform_execution_review_queue(evaluation, selected)
    if ledger is None:
        from .platform_execution_architecture_ledger import build_platform_execution_ledger

        ledger = build_platform_execution_ledger(selected, evaluation)
    metrics = platform_execution_metrics(selected, evaluation)
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
            "metrics",
            "metrics_projection",
            len(metrics),
            (addressed(metrics, "platform-execution-metrics"),),
        ),
        ("ledger", "ledger_projection", len(ledger.events), (ledger.content_address,)),
    )
    artifacts = []
    for artifact_id, artifact_type, record_count, sources in projections:
        body = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "visibility": "public_aggregate",
            "source_addresses": sources,
            "record_count": record_count,
            "review_safe": audit.accepted
            and platform_execution_ledger_is_closed(ledger)
            and all(sources),
        }
        artifacts.append(
            PlatformExecutionArtifact(
                artifact_id,
                artifact_type,
                "public_aggregate",
                addressed(body, "platform-execution-artifact"),
                tuple(sources),
                record_count,
                bool(body["review_safe"]),
            )
        )
    return tuple(artifacts)


def platform_execution_artifacts_are_safe(artifacts: tuple[PlatformExecutionArtifact, ...]) -> bool:
    return (
        len(artifacts) == 6
        and len({item.artifact_id for item in artifacts}) == 6
        and all(
            item.visibility == "public_aggregate" and item.review_safe and item.content_address
            for item in artifacts
        )
    )


__all__ = ["build_platform_execution_artifacts", "platform_execution_artifacts_are_safe"]
