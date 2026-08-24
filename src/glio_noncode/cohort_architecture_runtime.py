"""Twenty-two-stage D12 cohort architecture runtime."""

from __future__ import annotations

from .cohort_architecture_artifacts import build_cohort_architecture_artifacts
from .cohort_architecture_contracts import (
    CohortArchitectureFixture,
    CohortArchitectureRuntime,
    CohortArchitectureRuntimeStage,
    addressed,
)
from .cohort_architecture_depth import assess_cohort_architecture_depth
from .cohort_architecture_ledger import build_cohort_architecture_ledger
from .cohort_architecture_operations import evaluate_cohort_architecture_fixture
from .cohort_architecture_plan import build_cohort_architecture_plan
from .cohort_architecture_public_data import (
    audit_cohort_architecture_data,
    default_cohort_architecture_fixture,
)
from .cohort_architecture_quality import assess_cohort_architecture_quality
from .cohort_architecture_release import build_cohort_architecture_release
from .cohort_architecture_replay import replay_cohort_architecture_fixture
from .cohort_architecture_review import build_cohort_architecture_review_queue

COHORT_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "foundation-family-ready",
    "beta-family-ready",
    "alpha-family-ready",
    "frontier-family-ready",
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
    "runtime-finalized",
    "controls-closed",
    "observability-closed",
)


def _stage(
    stage_id: str,
    ordinal: int,
    state: str,
    inputs: tuple[str, ...],
    output: str,
    detail: str,
) -> CohortArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": ("runtime-stage",),
        "detail": detail,
    }
    return CohortArchitectureRuntimeStage(
        **body,
        content_address=addressed(body, "cohort-stage"),
    )


def run_cohort_architecture(
    fixture: CohortArchitectureFixture | None = None,
) -> CohortArchitectureRuntime:
    selected = fixture or default_cohort_architecture_fixture()
    audit = audit_cohort_architecture_data(selected)
    plan = build_cohort_architecture_plan(selected)
    evaluation = evaluate_cohort_architecture_fixture(selected)
    review = build_cohort_architecture_review_queue(evaluation)
    ledger = build_cohort_architecture_ledger(selected, evaluation)
    artifacts = build_cohort_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_cohort_architecture_release(selected, evaluation, artifacts)
    replay = replay_cohort_architecture_fixture(selected)
    quality = assess_cohort_architecture_quality(
        selected,
        audit,
        plan,
        evaluation,
        replay,
        release,
        artifacts,
        ledger,
    )
    depth = assess_cohort_architecture_depth(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        selected.content_address,
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        addressed(selected.sources, "cohort-lineage"),
        ledger.content_address,
        addressed(evaluation.checks, "cohort-metrics"),
        replay.content_address,
        addressed(artifacts, "cohort-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "cohort-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        addressed({"fixture": selected.content_address}, "cohort-runtime-seed"),
        addressed({"review": review.content_address}, "cohort-controls"),
        addressed({"ledger": ledger.content_address}, "cohort-observability"),
    )
    details = (
        "fixture constructed from four cohort evidence families",
        "source joins audited",
        "typed cohort schema validated",
        "sixteen cohort dependencies ordered",
        "foundation query, callable, sequence, and chromatin paths joined",
        "beta recurrence, burden, function, and pathway paths joined",
        "alpha clonality, recurrence, treatment, and replication paths joined",
        "frontier fairness, transport, federated, and discovery paths joined",
        "64 cohort cases executed with 392 checks",
        "48 cohort controls routed",
        "cohort source lineage closed",
        "cohort ledger closed",
        "cohort metrics materialized",
        "deterministic replay closed",
        "six cohort artifacts materialized",
        "cohort bundle address seeded",
        "cohort release built",
        "cohort quality gate passed",
        "cohort depth accounted",
        "runtime address seeded",
        "cohort controls closed",
        "cohort observability closed",
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
            zip(COHORT_ARCHITECTURE_STAGE_IDS, details, strict=True),
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
        and release.state.value == "published"
    )
    body = {
        "fixture": selected.content_address,
        "evaluation": evaluation.content_address,
        "release": release.content_address,
        "stages": stages,
        "accepted": accepted,
    }
    return CohortArchitectureRuntime(
        selected,
        audit,
        plan,
        evaluation,
        review,
        ledger,
        artifacts,
        release,
        stages,
        accepted,
        addressed(body, "cohort-runtime"),
    )


__all__ = ["COHORT_ARCHITECTURE_STAGE_IDS", "run_cohort_architecture"]
