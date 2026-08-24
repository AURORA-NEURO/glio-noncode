"""Review-safe projections materialized from the D14 evaluation."""

from __future__ import annotations

from .evidence_architecture_contracts import (
    EvidenceArchitectureArtifact,
    EvidenceArchitectureDataAudit,
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    EvidenceArchitectureLedger,
    EvidenceArchitectureReviewQueue,
    addressed,
)
from .evidence_architecture_lineage import evidence_architecture_lineage_rows
from .evidence_architecture_metrics import evidence_architecture_metrics
from .evidence_architecture_public_data import default_evidence_architecture_fixture


def build_evidence_architecture_artifacts(
    fixture: EvidenceArchitectureFixture | None = None,
    audit: EvidenceArchitectureDataAudit | None = None,
    evaluation: EvidenceArchitectureEvaluation | None = None,
    review_queue: EvidenceArchitectureReviewQueue | None = None,
    ledger: EvidenceArchitectureLedger | None = None,
) -> tuple[EvidenceArchitectureArtifact, ...]:
    selected = fixture or default_evidence_architecture_fixture()
    if audit is None:
        from .evidence_architecture_public_data import audit_evidence_architecture_data

        audit = audit_evidence_architecture_data(selected)
    if evaluation is None:
        from .evidence_architecture_operations import evaluate_evidence_architecture_fixture

        evaluation = evaluate_evidence_architecture_fixture(selected)
    if review_queue is None:
        from .evidence_architecture_review import build_evidence_architecture_review_queue

        review_queue = build_evidence_architecture_review_queue(evaluation, selected)
    if ledger is None:
        from .evidence_architecture_ledger import build_evidence_architecture_ledger

        ledger = build_evidence_architecture_ledger(selected, evaluation)
    metrics = evidence_architecture_metrics(selected, evaluation)
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
            len(evidence_architecture_lineage_rows(selected)),
            (selected.content_address,),
        ),
        (
            "metrics-ledger",
            "metrics_and_ledger",
            len(ledger.events),
            (addressed(metrics, "evidence-architecture-metrics"), ledger.content_address),
        ),
    )
    artifacts: list[EvidenceArchitectureArtifact] = []
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
            EvidenceArchitectureArtifact(
                artifact_id,
                artifact_type,
                "public_aggregate",
                addressed(body, "evidence-architecture-artifact"),
                tuple(sources),
                record_count,
                bool(body["review_safe"]),
            )
        )
    return tuple(artifacts)


def evidence_architecture_artifacts_are_safe(
    artifacts: tuple[EvidenceArchitectureArtifact, ...],
) -> bool:
    return (
        len(artifacts) == 6
        and len({item.artifact_id for item in artifacts}) == len(artifacts)
        and all(
            item.visibility == "public_aggregate" and item.review_safe and item.content_address
            for item in artifacts
        )
    )


def evidence_architecture_artifact_summary(
    artifacts: tuple[EvidenceArchitectureArtifact, ...],
) -> dict[str, object]:
    return {
        "artifact_count": len(artifacts),
        "safe": evidence_architecture_artifacts_are_safe(artifacts),
        "record_count": sum(item.record_count for item in artifacts),
        "types": sorted(item.artifact_type for item in artifacts),
    }


__all__ = [
    "build_evidence_architecture_artifacts",
    "evidence_architecture_artifact_summary",
    "evidence_architecture_artifacts_are_safe",
]
