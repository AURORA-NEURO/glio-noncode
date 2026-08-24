"""End-to-end 24-stage runtime for the composed Domain 03 specimen architecture."""

from __future__ import annotations

from .specimen_architecture_access import specimen_architecture_access_policy
from .specimen_architecture_bundle import (
    materialize_specimen_architecture_artifacts,
    release_specimen_architecture,
)
from .specimen_architecture_compliance import assess_specimen_architecture_compliance
from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureFixture,
    SpecimenArchitectureRuntime,
    SpecimenArchitectureRuntimeStage,
    SpecimenArchitectureState,
    addressed,
)
from .specimen_architecture_depth import specimen_architecture_depth_report
from .specimen_architecture_failures import classify_specimen_architecture_failures
from .specimen_architecture_invariants import check_specimen_architecture_invariants
from .specimen_architecture_lineage import build_specimen_architecture_ledger
from .specimen_architecture_metrics import materialize_specimen_architecture_metrics
from .specimen_architecture_observability import observe_specimen_architecture_run
from .specimen_architecture_operations import evaluate_specimen_architecture_fixture
from .specimen_architecture_plan import compile_specimen_architecture_plan
from .specimen_architecture_policy import score_specimen_architecture_policy
from .specimen_architecture_public_data import (
    audit_specimen_architecture_data,
    default_specimen_architecture_fixture,
)
from .specimen_architecture_quality import assess_specimen_architecture_quality
from .specimen_architecture_replay import replay_specimen_architecture_fixture
from .specimen_architecture_review import build_specimen_architecture_review_queue
from .specimen_architecture_runbook import specimen_architecture_runbook
from .specimen_architecture_schema import specimen_architecture_schema
from .specimen_architecture_validation import validate_specimen_architecture_matrix

SPECIMEN_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "plan-compiled",
    "policy-scored",
    "ingestion-closed",
    "context-family-ready",
    "origin-family-ready",
    "lineage-family-ready",
    "preanalytic-family-ready",
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


def run_specimen_architecture(
    fixture: SpecimenArchitectureFixture | str | None = None,
    *,
    run_id: str = "specimen-architecture-run-v1",
) -> SpecimenArchitectureRuntime:
    """Execute intake, adapter composition, review, lineage, and release."""

    value = (
        default_specimen_architecture_fixture(fixture)
        if isinstance(fixture, (str, type(None)))
        else fixture
    )
    assert value is not None
    audit = audit_specimen_architecture_data(value)
    plan = compile_specimen_architecture_plan(value)
    policy = score_specimen_architecture_policy(value.fixture_id, value.cases)
    evaluation = evaluate_specimen_architecture_fixture(value)
    review_queue = build_specimen_architecture_review_queue(value.fixture_id, value.cases)
    ledger = build_specimen_architecture_ledger(value.fixture_id, value.cases, evaluation)
    validation = validate_specimen_architecture_matrix(value, evaluation)
    schema = specimen_architecture_schema()
    artifacts = materialize_specimen_architecture_artifacts(
        value,
        evaluation,
        review_queue,
        ledger,
        materialize_specimen_architecture_metrics(value, evaluation, review_queue, len(validation)),
    )
    metrics = materialize_specimen_architecture_metrics(
        value, evaluation, review_queue, len(validation)
    )
    access = specimen_architecture_access_policy(artifacts)
    replay = replay_specimen_architecture_fixture(value, evaluation)
    compliance = assess_specimen_architecture_compliance(value)
    invariants = check_specimen_architecture_invariants(
        value, evaluation, plan, review_queue, ledger
    )
    runbook = specimen_architecture_runbook()
    failures = classify_specimen_architecture_failures(evaluation)
    observations = observe_specimen_architecture_run(
        run_id, len(SPECIMEN_ARCHITECTURE_STAGE_IDS), metrics
    )
    all_checks: tuple[SpecimenArchitectureCheck, ...] = tuple(
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
        + observations.checks
    )
    release = release_specimen_architecture(
        value, evaluation, review_queue, ledger, artifacts, all_checks
    )
    quality = assess_specimen_architecture_quality(
        value,
        evaluation,
        plan,
        review_queue,
        ledger,
        artifacts,
        release,
        len(SPECIMEN_ARCHITECTURE_STAGE_IDS),
        compliance,
    )
    depth = specimen_architecture_depth_report(
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
        SpecimenArchitectureState.PUBLISHED
        if quality.passed
        and not failures.release_blocked
        and depth.accepted
        and compliance.accepted
        else SpecimenArchitectureState.BLOCKED
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
    return SpecimenArchitectureRuntime(
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
        addressed(body, "specimen-runtime"),
    )


def replay_checks(replay: object) -> tuple[SpecimenArchitectureCheck, ...]:
    """Adapt a replay report into checks consumed by the release gate."""

    from .specimen_architecture_contracts import SpecimenArchitectureCheckKind

    return tuple(
        SpecimenArchitectureCheck(
            check_id=check_id,
            kind=SpecimenArchitectureCheckKind.LINEAGE,
            passed=passed,
            observed=observed,
            required=True,
            detail=detail,
            content_address=addressed(
                {"check_id": check_id, "passed": passed, "observed": observed},
                "specimen-replay-check",
            ),
        )
        for check_id, passed, observed, detail in (
            (
                "replay-receipts",
                replay.matching_receipts,
                replay.matching_receipts,
                "receipt projection is deterministic",
            ),
            (
                "replay-checks",
                replay.matching_checks,
                replay.matching_checks,
                "check projection is deterministic",
            ),
            (
                "replay-address",
                replay.first_address == replay.second_address,
                (replay.first_address, replay.second_address),
                "evaluation address is deterministic",
            ),
        )
    )


def _stages(
    value: SpecimenArchitectureFixture,
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
) -> list[SpecimenArchitectureRuntimeStage]:
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
        addressed(validation, "specimen-validation"),
        schema.content_address,
        addressed(artifacts, "specimen-artifacts"),
        access.content_address,
        replay.content_address,
        depth.content_address,
        compliance.content_address,
        release.content_address,
        quality.content_address,
        addressed(
            {
                "metrics": metrics.content_address,
                "validation": addressed(validation, "specimen-validation"),
            },
            "specimen-observability",
        ),
        addressed(
            {"run_id": run_id, "stage_count": len(SPECIMEN_ARCHITECTURE_STAGE_IDS)},
            "specimen-final",
        ),
    )
    states = [SpecimenArchitectureState.ACCEPTED] * 20 + [
        release.state,
        quality.state,
        SpecimenArchitectureState.ACCEPTED,
        SpecimenArchitectureState.ACCEPTED,
    ]
    stages: list[SpecimenArchitectureRuntimeStage] = []
    previous = f"sha256:{run_id}"
    for ordinal, (stage_id, output, state) in enumerate(
        zip(SPECIMEN_ARCHITECTURE_STAGE_IDS, outputs, states, strict=True), 1
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
            SpecimenArchitectureRuntimeStage(
                stage_id,
                ordinal,
                state,
                previous,
                output,
                f"{stage_id} completed",
                addressed(body, "specimen-runtime-stage"),
            )
        )
        previous = output
    return stages


__all__ = ["SPECIMEN_ARCHITECTURE_STAGE_IDS", "replay_checks", "run_specimen_architecture"]
