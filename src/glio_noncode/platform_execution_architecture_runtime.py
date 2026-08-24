"""Twenty-four-stage D16 platform execution architecture runtime."""

from __future__ import annotations

from .platform_execution_architecture_artifacts import build_platform_execution_artifacts
from .platform_execution_architecture_compliance import assess_platform_execution_compliance
from .platform_execution_architecture_contracts import (
    PlatformExecutionFixture,
    PlatformExecutionRuntime,
    PlatformExecutionRuntimeStage,
    addressed,
)
from .platform_execution_architecture_depth import assess_platform_execution_depth
from .platform_execution_architecture_ledger import build_platform_execution_ledger
from .platform_execution_architecture_metrics import platform_execution_metrics
from .platform_execution_architecture_operations import evaluate_platform_execution_fixture
from .platform_execution_architecture_plan import build_platform_execution_plan
from .platform_execution_architecture_public_data import (
    audit_platform_execution_data,
    default_platform_execution_fixture,
)
from .platform_execution_architecture_quality import assess_platform_execution_quality
from .platform_execution_architecture_release import build_platform_execution_release
from .platform_execution_architecture_replay import replay_platform_execution_fixture
from .platform_execution_architecture_reporting import build_platform_execution_report
from .platform_execution_architecture_review import build_platform_execution_review_queue
from .platform_execution_architecture_schema import validate_platform_execution_fixture

PLATFORM_EXECUTION_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "platform-family-ready",
    "control-family-ready",
    "deployment-family-ready",
    "cross-plane-ready",
    "cases-executed",
    "review-routed",
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
    "coordination-closed",
    "report-materialized",
    "runtime-seeded",
    "runtime-finalized",
)


def _stage(
    stage_id: str,
    ordinal: int,
    state: str,
    inputs: tuple[str, ...],
    output: str,
    detail: str,
) -> PlatformExecutionRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": (f"runtime-stage:{ordinal:02d}",),
        "detail": detail,
    }
    return PlatformExecutionRuntimeStage(
        **body, content_address=addressed(body, "platform-execution-stage")
    )


def run_platform_execution_architecture(
    fixture: PlatformExecutionFixture | None = None,
) -> PlatformExecutionRuntime:
    selected = fixture or default_platform_execution_fixture()
    audit = audit_platform_execution_data(selected)
    validate_platform_execution_fixture(selected)
    plan = build_platform_execution_plan(selected)
    evaluation = evaluate_platform_execution_fixture(selected)
    review = build_platform_execution_review_queue(evaluation, selected)
    ledger = build_platform_execution_ledger(selected, evaluation)
    artifacts = build_platform_execution_artifacts(selected, audit, evaluation, review, ledger)
    release = build_platform_execution_release(selected, evaluation, artifacts)
    replay = replay_platform_execution_fixture(selected)
    depth = assess_platform_execution_depth(selected, evaluation)
    quality = assess_platform_execution_quality(
        selected, audit, plan, evaluation, replay, release, artifacts, ledger
    )
    compliance = assess_platform_execution_compliance(selected)
    metrics = platform_execution_metrics(selected, evaluation)
    report = build_platform_execution_report(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        addressed(selected.to_dict(include_payload=False), "platform-execution-schema"),
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        ledger.content_address,
        addressed(metrics, "platform-execution-metrics-stage"),
        replay.content_address,
        addressed(artifacts, "platform-execution-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "platform-execution-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        compliance.content_address,
        addressed({"control_count": len(review.items)}, "platform-execution-controls"),
        addressed(
            {"coordination": quality.checks[-2].content_address}, "platform-execution-coordination"
        ),
        addressed(report, "platform-execution-report-stage"),
        addressed({"fixture": selected.content_address}, "platform-execution-runtime-seed"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "platform-execution-runtime-final",
        ),
    )
    details = (
        "fixture assembled from three public aggregate execution families",
        "nineteen public source receipts audited",
        "typed D16 schema and source joins validated",
        "sixteen dependency-safe operation nodes compiled",
        "platform control C01-C04 family retained",
        "quality control C05-C12 family retained",
        "deployment C13-C16 family retained",
        "cross-plane family closure retained",
        "sixty-four delegate-backed cases executed with 458 checks",
        "held, denied, and unresolved paths routed to review",
        "eighty-event append-only ledger closed",
        "state, issue, family, operation, and scenario metrics materialized",
        "deterministic replay closed",
        "six public and review projection artifacts materialized",
        "bundle address closed",
        "publication state derived from evaluation and artifact closure",
        "quality gate evaluated eleven release and coordination checks",
        "depth report counted checks, states, issues, and addresses",
        "public-boundary compliance closed",
        "positive and control balance closed",
        "coordination cross-plane closure retained",
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
            zip(PLATFORM_EXECUTION_ARCHITECTURE_STAGE_IDS, details, strict=True), start=1
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
    return PlatformExecutionRuntime(
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
        addressed(body, "platform-execution-runtime"),
    )


__all__ = ["PLATFORM_EXECUTION_ARCHITECTURE_STAGE_IDS", "run_platform_execution_architecture"]
