"""Twenty-four-stage D12 cohort architecture runtime."""

from __future__ import annotations

from .cohort_architecture_artifacts import build_cohort_architecture_artifacts
from .cohort_architecture_compliance import assess_cohort_architecture_compliance
from .cohort_architecture_contracts import (
    CohortArchitectureFixture,
    CohortArchitectureRuntime,
    CohortArchitectureRuntimeStage,
    addressed,
)
from .cohort_architecture_depth import assess_cohort_architecture_depth
from .cohort_architecture_ledger import build_cohort_architecture_ledger
from .cohort_architecture_metrics import cohort_architecture_metrics
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
from .cohort_architecture_schema import validate_cohort_architecture_fixture

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
    "controls-closed",
    "compliance-closed",
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
    validate_cohort_architecture_fixture(selected)
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
    compliance = assess_cohort_architecture_compliance(selected)
    metrics = cohort_architecture_metrics(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        addressed(selected.to_dict(include_payload=False), "cohort-schema"),
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
        addressed({"review": review.content_address}, "cohort-controls"),
        addressed(compliance, "cohort-compliance"),
        addressed(
            {
                "fixture": selected.content_address,
                "evaluation": evaluation.content_address,
                "metrics": metrics,
            },
            "cohort-report-stage",
        ),
        addressed({"fixture": selected.content_address}, "cohort-runtime-seed"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "cohort-runtime-final",
        ),
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
        "64 cohort cases executed with 458 checks",
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
        "cohort controls closed",
        "public aggregate compliance closed",
        "cohort report projection materialized",
        "runtime address seeded",
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
        and compliance["accepted"]
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
        depth,
        quality,
        stages,
        accepted,
        addressed(body, "cohort-runtime"),
    )


__all__ = ["COHORT_ARCHITECTURE_STAGE_IDS", "run_cohort_architecture"]
