"""End-to-end 24-stage runtime for composed D04 reference operations."""

from __future__ import annotations

from .reference_architecture_access import reference_architecture_access_policy
from .reference_architecture_bundle import (
    materialize_reference_architecture_artifacts,
    release_reference_architecture,
)
from .reference_architecture_compliance import assess_reference_architecture_compliance
from .reference_architecture_contracts import (
    ReferenceArchitectureCheck,
    ReferenceArchitectureFixture,
    ReferenceArchitectureRuntime,
    ReferenceArchitectureRuntimeStage,
    ReferenceArchitectureState,
    addressed,
)
from .reference_architecture_depth import reference_architecture_depth_report
from .reference_architecture_failures import classify_reference_architecture_failures
from .reference_architecture_invariants import check_reference_architecture_invariants
from .reference_architecture_lineage import build_reference_architecture_ledger
from .reference_architecture_metrics import materialize_reference_architecture_metrics
from .reference_architecture_observability import observe_reference_architecture_run
from .reference_architecture_operations import evaluate_reference_architecture_fixture
from .reference_architecture_plan import compile_reference_architecture_plan
from .reference_architecture_policy import score_reference_architecture_policy
from .reference_architecture_public_data import (
    audit_reference_architecture_data,
    default_reference_architecture_fixture,
)
from .reference_architecture_quality import assess_reference_architecture_quality
from .reference_architecture_replay import replay_reference_architecture_fixture
from .reference_architecture_review import build_reference_architecture_review_queue
from .reference_architecture_runbook import reference_architecture_runbook
from .reference_architecture_schema import reference_architecture_schema
from .reference_architecture_validation import validate_reference_architecture_matrix

REFERENCE_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "plan-compiled",
    "policy-scored",
    "ingestion-closed",
    "coordinate-family-ready",
    "annotation-family-ready",
    "governance-family-ready",
    "release-family-ready",
    "cases-executed",
    "review-routed",
    "lineage-linked",
    "metrics-materialized",
    "validation-matrix-closed",
    "schema-closed",
    "artifacts-materialized",
    "access-closed",
    "replay-closed",
    "depth-accounted",
    "compliance-closed",
    "release-gated",
    "quality-gated",
    "observability-closed",
    "runtime-finalized",
)


def run_reference_architecture(
    fixture: ReferenceArchitectureFixture | str | None = None,
    *,
    run_id: str = "reference-architecture-run-v1",
) -> ReferenceArchitectureRuntime:
    """Execute D04 intake, adapter composition, review, replay, and release."""

    value = (
        default_reference_architecture_fixture(fixture)
        if isinstance(fixture, (str, type(None)))
        else fixture
    )
    assert value is not None
    audit = audit_reference_architecture_data(value)
    plan = compile_reference_architecture_plan(value)
    policy = score_reference_architecture_policy(value.fixture_id, value.cases)
    evaluation = evaluate_reference_architecture_fixture(value)
    review_queue = build_reference_architecture_review_queue(value.fixture_id, value.cases)
    ledger = build_reference_architecture_ledger(value.fixture_id, value.cases, evaluation)
    validation = validate_reference_architecture_matrix(value, evaluation)
    schema = reference_architecture_schema()
    metrics = materialize_reference_architecture_metrics(
        value, evaluation, review_queue, len(validation)
    )
    artifacts = materialize_reference_architecture_artifacts(
        value, evaluation, review_queue, ledger, metrics
    )
    access = reference_architecture_access_policy(artifacts)
    replay = replay_reference_architecture_fixture(value, evaluation)
    compliance = assess_reference_architecture_compliance(value)
    invariants = check_reference_architecture_invariants(
        value, evaluation, plan, review_queue, ledger
    )
    runbook = reference_architecture_runbook()
    failures = classify_reference_architecture_failures(evaluation)
    observation = observe_reference_architecture_run(
        run_id, len(REFERENCE_ARCHITECTURE_STAGE_IDS), metrics
    )
    all_checks = tuple(
        audit.checks
        + evaluation.checks
        + policy.checks
        + validation
        + schema.checks
        + compliance.checks
        + access.checks
        + replay_checks(replay)
        + invariants
        + runbook.checks
        + observation.checks
    )
    release = release_reference_architecture(
        value, evaluation, review_queue, ledger, artifacts, all_checks
    )
    quality = assess_reference_architecture_quality(
        value,
        evaluation,
        plan,
        review_queue,
        ledger,
        artifacts,
        release,
        len(REFERENCE_ARCHITECTURE_STAGE_IDS),
        compliance,
    )
    depth = reference_architecture_depth_report(
        value, evaluation, plan, review_queue, ledger, None
    )
    stages = _stages(
        value,
        run_id,
        audit,
        plan,
        policy,
        evaluation,
        review_queue,
        ledger,
        metrics,
        validation,
        schema,
        artifacts,
        access,
        replay,
        depth,
        compliance,
        release,
        quality,
    )
    state = (
        ReferenceArchitectureState.PUBLISHED
        if quality.passed
        and not failures.release_blocked
        and depth.accepted
        and compliance.accepted
        else ReferenceArchitectureState.BLOCKED
    )
    body = {
        "run_id": run_id,
        "fixture_id": value.fixture_id,
        "state": state,
        "stages": stages,
        "evaluation": evaluation,
        "plan": plan,
        "review_queue": review_queue,
        "ledger": ledger,
        "artifacts": artifacts,
        "release": release,
        "depth": depth,
        "quality": quality,
        "compliance": compliance,
    }
    return ReferenceArchitectureRuntime(
        run_id,
        value.fixture_id,
        state,
        tuple(stages),
        evaluation,
        plan,
        review_queue,
        ledger,
        artifacts,
        release,
        depth,
        quality,
        compliance,
        addressed(body, "reference-runtime"),
    )


def replay_checks(replay: object) -> tuple[ReferenceArchitectureCheck, ...]:
    from .reference_architecture_contracts import ReferenceArchitectureCheckKind

    values = (
        (
            "replay-receipts",
            replay.matching_receipts,
            replay.matching_receipts,
            "receipt projections match",
        ),
        (
            "replay-checks",
            replay.matching_checks,
            replay.matching_checks,
            "check projections match",
        ),
        (
            "replay-address",
            replay.first_address == replay.second_address,
            (replay.first_address, replay.second_address),
            "evaluation addresses match",
        ),
    )
    return tuple(
        ReferenceArchitectureCheck(
            name,
            ReferenceArchitectureCheckKind.LINEAGE,
            passed,
            observed,
            True,
            detail,
            addressed(
                {"check_id": name, "passed": passed, "observed": observed}, "reference-replay-check"
            ),
        )
        for name, passed, observed, detail in values
    )


def _stages(
    value: ReferenceArchitectureFixture,
    run_id: str,
    audit: object,
    plan: object,
    policy: object,
    evaluation: object,
    review_queue: object,
    ledger: object,
    metrics: object,
    validation: tuple[object, ...],
    schema: object,
    artifacts: tuple[object, ...],
    access: object,
    replay: object,
    depth: object,
    compliance: object,
    release: object,
    quality: object,
) -> list[ReferenceArchitectureRuntimeStage]:
    outputs = (
        value.content_address,
        audit.content_address,
        plan.content_address,
        policy.content_address,
        audit.content_address,
        plan.content_address,
        plan.content_address,
        plan.content_address,
        plan.content_address,
        evaluation.content_address,
        review_queue.content_address,
        ledger.content_address,
        metrics.content_address,
        addressed(validation, "reference-validation"),
        schema.content_address,
        addressed(artifacts, "reference-artifacts"),
        access.content_address,
        replay.content_address,
        depth.content_address,
        compliance.content_address,
        release.content_address,
        quality.content_address,
        addressed(
            {
                "metrics": metrics.content_address,
                "validation": addressed(validation, "reference-validation"),
            },
            "reference-observability",
        ),
        addressed(
            {"run_id": run_id, "stage_count": len(REFERENCE_ARCHITECTURE_STAGE_IDS)},
            "reference-final",
        ),
    )
    states = [ReferenceArchitectureState.ACCEPTED] * 20 + [
        release.state,
        quality.state,
        ReferenceArchitectureState.ACCEPTED,
        ReferenceArchitectureState.ACCEPTED,
    ]
    stages: list[ReferenceArchitectureRuntimeStage] = []
    previous = f"sha256:{run_id}"
    for ordinal, (stage_id, output, state) in enumerate(
        zip(REFERENCE_ARCHITECTURE_STAGE_IDS, outputs, states, strict=True), 1
    ):
        body = {
            "stage_id": stage_id,
            "ordinal": ordinal,
            "state": state,
            "input_address": previous,
            "output_address": output,
            "run_id": run_id,
        }
        stages.append(
            ReferenceArchitectureRuntimeStage(
                stage_id,
                ordinal,
                state,
                previous,
                output,
                f"{stage_id} completed",
                addressed(body, "reference-runtime-stage"),
            )
        )
        previous = output
    return stages


__all__ = ["REFERENCE_ARCHITECTURE_STAGE_IDS", "replay_checks", "run_reference_architecture"]
