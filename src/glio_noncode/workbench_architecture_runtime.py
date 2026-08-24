"""Twenty-four-stage D15 workbench architecture runtime."""

from __future__ import annotations

from .workbench_architecture_artifacts import build_workbench_architecture_artifacts
from .workbench_architecture_compliance import assess_workbench_architecture_compliance
from .workbench_architecture_contracts import (
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureRuntime,
    WorkbenchArchitectureRuntimeStage,
    addressed,
)
from .workbench_architecture_depth import assess_workbench_architecture_depth
from .workbench_architecture_ledger import build_workbench_architecture_ledger
from .workbench_architecture_metrics import workbench_architecture_metrics
from .workbench_architecture_operations import evaluate_workbench_architecture_fixture
from .workbench_architecture_plan import build_workbench_architecture_plan
from .workbench_architecture_public_data import (
    audit_workbench_architecture_data,
    default_workbench_architecture_fixture,
)
from .workbench_architecture_quality import assess_workbench_architecture_quality
from .workbench_architecture_release import build_workbench_architecture_release
from .workbench_architecture_replay import replay_workbench_architecture_fixture
from .workbench_architecture_reporting import build_workbench_architecture_report
from .workbench_architecture_review import build_workbench_architecture_review_queue
from .workbench_architecture_schema import validate_workbench_architecture_fixture

WORKBENCH_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "foundation-family-ready",
    "beta-family-ready",
    "collaboration-family-ready",
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
) -> WorkbenchArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": (f"runtime-stage:{ordinal:02d}",),
        "detail": detail,
    }
    return WorkbenchArchitectureRuntimeStage(
        **body, content_address=addressed(body, "workbench-architecture-stage")
    )


def run_workbench_architecture(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> WorkbenchArchitectureRuntime:
    selected = fixture or default_workbench_architecture_fixture()
    audit = audit_workbench_architecture_data(selected)
    validate_workbench_architecture_fixture(selected)
    plan = build_workbench_architecture_plan(selected)
    evaluation = evaluate_workbench_architecture_fixture(selected)
    review = build_workbench_architecture_review_queue(evaluation, selected)
    ledger = build_workbench_architecture_ledger(selected, evaluation)
    artifacts = build_workbench_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_workbench_architecture_release(selected, evaluation, artifacts)
    replay = replay_workbench_architecture_fixture(selected)
    depth = assess_workbench_architecture_depth(selected, evaluation)
    quality = assess_workbench_architecture_quality(
        selected, audit, plan, evaluation, replay, release, artifacts, ledger
    )
    compliance = assess_workbench_architecture_compliance(selected)
    metrics = workbench_architecture_metrics(selected, evaluation)
    report = build_workbench_architecture_report(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        addressed(selected.to_dict(include_payload=False), "workbench-architecture-schema"),
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        addressed(selected.cases, "workbench-architecture-lineage"),
        ledger.content_address,
        addressed(metrics, "workbench-architecture-metrics-stage"),
        replay.content_address,
        addressed(artifacts, "workbench-architecture-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "workbench-architecture-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        compliance.content_address,
        addressed({"control_count": len(review.items)}, "workbench-architecture-controls"),
        addressed(report, "workbench-architecture-report-stage"),
        addressed({"fixture": selected.content_address}, "workbench-architecture-runtime-seed"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "workbench-architecture-runtime-final",
        ),
    )
    details = (
        "fixture assembled from four public aggregate workbench families",
        "twenty public source receipts audited",
        "typed D15 schema and source joins validated",
        "sixteen dependency-safe operation nodes compiled",
        "foundation C01-C04 family retained",
        "beta C05-C08 family retained",
        "collaboration C09-C12 family retained",
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
            zip(WORKBENCH_ARCHITECTURE_STAGE_IDS, details, strict=True), start=1
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
    return WorkbenchArchitectureRuntime(
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
        addressed(body, "workbench-architecture-runtime"),
    )


__all__ = ["WORKBENCH_ARCHITECTURE_STAGE_IDS", "run_workbench_architecture"]
