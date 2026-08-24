"""Twenty-four-stage D13 planning architecture runtime."""

from __future__ import annotations

from .planning_architecture_artifacts import build_planning_architecture_artifacts
from .planning_architecture_compliance import assess_planning_architecture_compliance
from .planning_architecture_contracts import (
    PlanningArchitectureFixture,
    PlanningArchitectureRuntime,
    PlanningArchitectureRuntimeStage,
    addressed,
)
from .planning_architecture_depth import assess_planning_architecture_depth
from .planning_architecture_ledger import build_planning_architecture_ledger
from .planning_architecture_metrics import planning_architecture_metrics
from .planning_architecture_operations import evaluate_planning_architecture_fixture
from .planning_architecture_plan import build_planning_architecture_plan
from .planning_architecture_public_data import (
    audit_planning_architecture_data,
    default_planning_architecture_fixture,
)
from .planning_architecture_quality import assess_planning_architecture_quality
from .planning_architecture_release import build_planning_architecture_release
from .planning_architecture_replay import replay_planning_architecture_fixture
from .planning_architecture_reporting import build_planning_architecture_report
from .planning_architecture_review import build_planning_architecture_review_queue
from .planning_architecture_schema import validate_planning_architecture_fixture

PLANNING_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "validation-design-family-ready",
    "editing-design-family-ready",
    "planning-family-ready",
    "validation-release-family-ready",
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
    stage_id: str,
    ordinal: int,
    state: str,
    inputs: tuple[str, ...],
    output: str,
    detail: str,
) -> PlanningArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": (f"runtime-stage:{ordinal:02d}",),
        "detail": detail,
    }
    return PlanningArchitectureRuntimeStage(
        **body,
        content_address=addressed(body, "planning-stage"),
    )


def run_planning_architecture(
    fixture: PlanningArchitectureFixture | None = None,
) -> PlanningArchitectureRuntime:
    selected = fixture or default_planning_architecture_fixture()
    audit = audit_planning_architecture_data(selected)
    validate_planning_architecture_fixture(selected)
    plan = build_planning_architecture_plan(selected)
    evaluation = evaluate_planning_architecture_fixture(selected)
    review = build_planning_architecture_review_queue(evaluation)
    ledger = build_planning_architecture_ledger(selected, evaluation)
    artifacts = build_planning_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_planning_architecture_release(selected, evaluation, artifacts)
    replay = replay_planning_architecture_fixture(selected)
    depth = assess_planning_architecture_depth(selected, evaluation)
    quality = assess_planning_architecture_quality(
        selected,
        audit,
        plan,
        evaluation,
        replay,
        release,
        artifacts,
        ledger,
    )
    compliance = assess_planning_architecture_compliance(selected)
    metrics = planning_architecture_metrics(selected, evaluation)
    report = build_planning_architecture_report(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        addressed(selected.to_dict(include_payload=False), "planning-schema"),
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        addressed(selected.cases, "planning-lineage"),
        ledger.content_address,
        addressed(metrics, "planning-metrics-stage"),
        replay.content_address,
        addressed(artifacts, "planning-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "planning-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        compliance.content_address,
        addressed({"control_count": len(review.items)}, "planning-controls"),
        addressed(report, "planning-report-stage"),
        addressed({"fixture": selected.content_address}, "planning-runtime-seed"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "planning-runtime-final",
        ),
    )
    details = (
        "fixture assembled from four public planning families",
        "twenty public source receipts audited",
        "typed D13 schema and source joins validated",
        "sixteen dependency-safe operation nodes compiled",
        "validation-design C01-C04 family retained",
        "editing-design C05-C08 family retained",
        "planning C09-C12 family retained",
        "validation-release C13-C16 family retained",
        "sixty-four delegate-backed cases executed with 458 checks",
        "forty-eight held controls routed to review projections",
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
            zip(PLANNING_ARCHITECTURE_STAGE_IDS, details, strict=True),
            start=1,
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
    return PlanningArchitectureRuntime(
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
        addressed(body, "planning-runtime"),
    )


__all__ = ["PLANNING_ARCHITECTURE_STAGE_IDS", "run_planning_architecture"]
