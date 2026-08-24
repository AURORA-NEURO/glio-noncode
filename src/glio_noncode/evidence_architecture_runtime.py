"""Twenty-four-stage D14 evidence architecture runtime."""

from __future__ import annotations

from .evidence_architecture_artifacts import build_evidence_architecture_artifacts
from .evidence_architecture_compliance import assess_evidence_architecture_compliance
from .evidence_architecture_contracts import (
    EvidenceArchitectureFixture,
    EvidenceArchitectureRuntime,
    EvidenceArchitectureRuntimeStage,
    addressed,
)
from .evidence_architecture_depth import assess_evidence_architecture_depth
from .evidence_architecture_ledger import build_evidence_architecture_ledger
from .evidence_architecture_metrics import evidence_architecture_metrics
from .evidence_architecture_operations import evaluate_evidence_architecture_fixture
from .evidence_architecture_plan import build_evidence_architecture_plan
from .evidence_architecture_public_data import (
    audit_evidence_architecture_data,
    default_evidence_architecture_fixture,
)
from .evidence_architecture_quality import assess_evidence_architecture_quality
from .evidence_architecture_release import build_evidence_architecture_release
from .evidence_architecture_replay import replay_evidence_architecture_fixture
from .evidence_architecture_reporting import build_evidence_architecture_report
from .evidence_architecture_review import build_evidence_architecture_review_queue
from .evidence_architecture_schema import validate_evidence_architecture_fixture

EVIDENCE_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "foundation-family-ready",
    "beta-foundation-ready",
    "beta-adjudication-ready",
    "release-family-ready",
    "cases-executed",
    "review-routed",
    "lineage-linked",
    "ledger-closed",
    "metrics-materialized",
    "replay-closed",
    "artifacts-materialized",
    "bundle-closed",
    "release-built",
    "quality-gated",
    "depth-accounted",
    "compliance-closed",
    "controls-closed",
    "report-materialized",
    "runtime-seeded",
    "runtime-finalized",
)


def _stage(
    stage_id: str, ordinal: int, state: str, inputs: tuple[str, ...], output: str, detail: str
) -> EvidenceArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": (f"runtime-stage:{ordinal:02d}",),
        "detail": detail,
    }
    return EvidenceArchitectureRuntimeStage(
        **body, content_address=addressed(body, "evidence-architecture-stage")
    )


def run_evidence_architecture(
    fixture: EvidenceArchitectureFixture | None = None,
) -> EvidenceArchitectureRuntime:
    selected = fixture or default_evidence_architecture_fixture()
    audit = audit_evidence_architecture_data(selected)
    validate_evidence_architecture_fixture(selected)
    plan = build_evidence_architecture_plan(selected)
    evaluation = evaluate_evidence_architecture_fixture(selected)
    review = build_evidence_architecture_review_queue(evaluation, selected)
    ledger = build_evidence_architecture_ledger(selected, evaluation)
    artifacts = build_evidence_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_evidence_architecture_release(selected, evaluation, artifacts)
    replay = replay_evidence_architecture_fixture(selected)
    depth = assess_evidence_architecture_depth(selected, evaluation)
    quality = assess_evidence_architecture_quality(
        selected, audit, plan, evaluation, replay, release, artifacts, ledger
    )
    compliance = assess_evidence_architecture_compliance(selected)
    metrics = evidence_architecture_metrics(selected, evaluation)
    report = build_evidence_architecture_report(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        addressed(selected.to_dict(include_payload=False), "evidence-architecture-schema"),
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        addressed(selected.cases, "evidence-architecture-lineage"),
        ledger.content_address,
        addressed(metrics, "evidence-architecture-metrics-stage"),
        replay.content_address,
        addressed(artifacts, "evidence-architecture-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "evidence-architecture-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        compliance.content_address,
        addressed({"control_count": len(review.items)}, "evidence-architecture-controls"),
        addressed(report, "evidence-architecture-report-stage"),
        addressed({"fixture": selected.content_address}, "evidence-architecture-runtime-seed"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "evidence-architecture-runtime-final",
        ),
    )
    details = (
        "fixture assembled from three public aggregate delegate families",
        "nineteen public source receipts audited",
        "typed D14 schema and source joins validated",
        "sixteen dependency-safe operation nodes compiled",
        "foundation C01-C04 family retained",
        "beta foundation C05-C08 family retained",
        "beta adjudication C09-C12 family retained",
        "release C13-C16 family retained",
        "sixty-four delegate-backed cases executed with 458 checks",
        "held controls and unresolved positives routed to review",
        "case-to-source lineage materialized",
        "eighty-event append-only ledger closed",
        "state, issue, family, operation, and scenario metrics materialized",
        "deterministic replay closed",
        "six public and review projection artifacts materialized",
        "bundle address closed",
        "publication state derived from evaluation and artifact closure",
        "quality gate evaluated ten release checks",
        "depth report counted checks, states, issues, and addresses",
        "public-boundary compliance closed",
        "positive and control balance closed",
        "report projection materialized",
        "runtime seed addressed",
        "runtime final address closed",
    )
    stages = tuple(
        _stage(
            stage_id,
            ordinal,
            "accepted",
            (outputs[ordinal - 2],) if ordinal > 1 else (),
            outputs[ordinal - 1],
            detail,
        )
        for ordinal, (stage_id, detail) in enumerate(
            zip(EVIDENCE_ARCHITECTURE_STAGE_IDS, details, strict=True), start=1
        )
    )
    accepted = (
        audit.accepted
        and plan.accepted
        and evaluation.accepted
        and review.accepted
        and replay.accepted
        and quality.accepted
        and compliance.accepted
        and release.state.value == "published"
    )
    body = {
        "fixture": selected.content_address,
        "evaluation": evaluation.content_address,
        "release": release.content_address,
        "quality": quality.content_address,
        "depth": depth.content_address,
        "stages": stages,
        "accepted": accepted,
    }
    return EvidenceArchitectureRuntime(
        selected,
        audit,
        plan,
        evaluation,
        review,
        ledger,
        artifacts,
        release,
        depth,
        quality,
        stages,
        accepted,
        addressed(body, "evidence-architecture-runtime"),
    )


__all__ = ["EVIDENCE_ARCHITECTURE_STAGE_IDS", "run_evidence_architecture"]
