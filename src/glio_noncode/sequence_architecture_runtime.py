"""Twenty-four-stage end-to-end D06 sequence architecture runtime."""

from __future__ import annotations

from .sequence_architecture_access import sequence_architecture_access_policy
from .sequence_architecture_bundle import (
    materialize_sequence_architecture_artifacts,
    release_sequence_architecture,
)
from .sequence_architecture_compliance import assess_sequence_architecture_compliance
from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureFixture,
    SequenceArchitectureRuntime,
    SequenceArchitectureRuntimeStage,
    SequenceArchitectureState,
    addressed,
)
from .sequence_architecture_depth import sequence_architecture_depth_report
from .sequence_architecture_failures import classify_sequence_architecture_failures
from .sequence_architecture_invariants import check_sequence_architecture_invariants
from .sequence_architecture_lineage import build_sequence_architecture_ledger
from .sequence_architecture_metrics import materialize_sequence_architecture_metrics
from .sequence_architecture_operations import evaluate_sequence_architecture_fixture
from .sequence_architecture_plan import compile_sequence_architecture_plan
from .sequence_architecture_policy import score_sequence_architecture_policy
from .sequence_architecture_public_data import (
    audit_sequence_architecture_data,
    default_sequence_architecture_fixture,
)
from .sequence_architecture_quality import assess_sequence_architecture_quality
from .sequence_architecture_replay import replay_sequence_architecture_fixture
from .sequence_architecture_review import build_sequence_architecture_review_queue
from .sequence_architecture_runbook import sequence_architecture_runbook
from .sequence_architecture_schema import sequence_architecture_schema
from .sequence_architecture_validation import validate_sequence_architecture_matrix

SEQUENCE_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "plan-compiled",
    "policy-scored",
    "ingestion-closed",
    "effect-family-ready",
    "grammar-family-ready",
    "regulation-family-ready",
    "frontier-family-ready",
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


def run_sequence_architecture(
    fixture: SequenceArchitectureFixture | str | None = None,
    *,
    run_id: str = "sequence-architecture-run-v1",
) -> SequenceArchitectureRuntime:
    value = (
        default_sequence_architecture_fixture(fixture)
        if isinstance(fixture, (str, type(None)))
        else fixture
    )
    assert value is not None
    audit = audit_sequence_architecture_data(value)
    plan = compile_sequence_architecture_plan(value)
    policy = score_sequence_architecture_policy(value.fixture_id, value.cases)
    evaluation = evaluate_sequence_architecture_fixture(value)
    review_queue = build_sequence_architecture_review_queue(value.fixture_id, value.cases)
    ledger = build_sequence_architecture_ledger(value.fixture_id, value.cases, evaluation)
    validation = validate_sequence_architecture_matrix(value, evaluation)
    schema = sequence_architecture_schema()
    metrics = materialize_sequence_architecture_metrics(
        value, evaluation, review_queue, len(validation)
    )
    artifacts = materialize_sequence_architecture_artifacts(
        value, evaluation, review_queue, len(validation), ledger.content_address
    )
    access = sequence_architecture_access_policy(artifacts)
    replay = replay_sequence_architecture_fixture(value, evaluation)
    compliance = assess_sequence_architecture_compliance(value)
    invariants = check_sequence_architecture_invariants(
        value, evaluation, plan, review_queue, ledger
    )
    runbook = sequence_architecture_runbook()
    failures = classify_sequence_architecture_failures(evaluation)
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
    )
    release = release_sequence_architecture(
        value,
        artifacts,
        review_queue,
        all(item.passed for item in all_checks) and not failures.release_blocked,
    )
    depth = sequence_architecture_depth_report(
        value, evaluation, plan, review_queue, ledger, None
    )
    quality = assess_sequence_architecture_quality(
        value,
        evaluation,
        plan,
        review_queue,
        ledger,
        artifacts,
        release,
        len(SEQUENCE_ARCHITECTURE_STAGE_IDS),
        compliance,
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
        SequenceArchitectureState.PUBLISHED
        if quality.passed
        and compliance.accepted
        and depth.accepted
        and not failures.release_blocked
        else SequenceArchitectureState.BLOCKED
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
    return SequenceArchitectureRuntime(
        fixture_id=value.fixture_id,
        run_id=run_id,
        state=state,
        stages=tuple(stages),
        audit=audit,
        plan=plan,
        evaluation=evaluation,
        review_queue=review_queue,
        ledger=ledger,
        metrics=metrics,
        validation=validation,
        artifacts=artifacts,
        release=release,
        depth=depth,
        quality=quality,
        compliance=compliance,
        content_address=addressed(body, "sequence-runtime"),
    )


def replay_checks(replay: object) -> tuple[SequenceArchitectureCheck, ...]:
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
        SequenceArchitectureCheck(
            check_id=name,
            kind=SequenceArchitectureCheckKind.LINEAGE,
            passed=passed,
            observed=observed,
            required=True,
            detail=detail,
            content_address=addressed(
                {"check_id": name, "passed": passed, "observed": observed}, "sequence-replay-check"
            ),
        )
        for name, passed, observed, detail in values
    )


def _stages(
    value: SequenceArchitectureFixture,
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
) -> list[SequenceArchitectureRuntimeStage]:
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
        addressed(validation, "sequence-validation"),
        schema.content_address,
        addressed(artifacts, "sequence-artifacts"),
        access.content_address,
        replay.content_address,
        depth.content_address,
        compliance.content_address,
        release.content_address,
        quality.content_address,
        addressed(
            {
                "metrics": metrics.content_address,
                "validation": addressed(validation, "sequence-validation"),
                "audit": audit.content_address,
            },
            "sequence-observability",
        ),
        addressed(
            {"run_id": run_id, "stage_count": len(SEQUENCE_ARCHITECTURE_STAGE_IDS)},
            "sequence-runtime-final",
        ),
    )
    states = [SequenceArchitectureState.ACCEPTED] * 20 + [
        release.state,
        quality.release_state,
        SequenceArchitectureState.ACCEPTED,
        SequenceArchitectureState.ACCEPTED,
    ]
    stages: list[SequenceArchitectureRuntimeStage] = []
    previous = f"sha256:{run_id}"
    for ordinal, (stage_id, output, state) in enumerate(
        zip(SEQUENCE_ARCHITECTURE_STAGE_IDS, outputs, states, strict=True), 1
    ):
        body = {
            "stage_id": stage_id,
            "ordinal": ordinal,
            "state": state,
            "input_addresses": (previous,),
            "output_addresses": (output,),
            "check_count": 1,
            "run_id": run_id,
        }
        stages.append(
            SequenceArchitectureRuntimeStage(
                ordinal=ordinal,
                stage_id=stage_id,
                state=state,
                input_addresses=(previous,),
                output_addresses=(output,),
                check_count=1,
                content_address=addressed(body, "sequence-runtime-stage"),
            )
        )
        previous = output
    return stages


__all__ = ["SEQUENCE_ARCHITECTURE_STAGE_IDS", "replay_checks", "run_sequence_architecture"]
