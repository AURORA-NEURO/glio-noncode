"""End-to-end twenty-stage runtime for the composed D05 atlas."""

from __future__ import annotations

from .atlas_architecture_access import atlas_architecture_access_policy
from .atlas_architecture_bundle import (
    materialize_atlas_architecture_artifacts,
    release_atlas_architecture,
)
from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureFixture,
    AtlasArchitectureRuntime,
    AtlasArchitectureRuntimeStage,
    AtlasArchitectureState,
    addressed,
)
from .atlas_architecture_depth import atlas_architecture_depth_report
from .atlas_architecture_failures import classify_atlas_architecture_failures
from .atlas_architecture_invariants import check_atlas_architecture_invariants
from .atlas_architecture_lineage import build_atlas_architecture_ledger
from .atlas_architecture_metrics import materialize_atlas_architecture_metrics
from .atlas_architecture_observability import observe_atlas_architecture_run
from .atlas_architecture_operations import evaluate_atlas_architecture_fixture
from .atlas_architecture_plan import compile_atlas_architecture_plan
from .atlas_architecture_policy import score_atlas_architecture_policy
from .atlas_architecture_public_data import (
    audit_atlas_architecture_data,
    default_atlas_architecture_fixture,
)
from .atlas_architecture_quality import assess_atlas_architecture_quality
from .atlas_architecture_replay import replay_atlas_architecture_fixture
from .atlas_architecture_review import build_atlas_architecture_review_queue
from .atlas_architecture_runbook import atlas_architecture_runbook
from .atlas_architecture_schema import atlas_architecture_schema
from .atlas_architecture_validation import validate_atlas_architecture_matrix

ATLAS_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "plan-compiled",
    "policy-scored",
    "ingestion-closed",
    "regulatory-family-ready",
    "molecular-family-ready",
    "alpha-evidence-family-ready",
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
    "release-gated",
    "runtime-finalized",
)


def run_atlas_architecture(
    fixture: AtlasArchitectureFixture | str | None = None,
    *,
    run_id: str = "atlas-architecture-run-v1",
) -> AtlasArchitectureRuntime:
    """Execute D05 intake, family composition, review, replay, and release."""

    value = (
        default_atlas_architecture_fixture(fixture)
        if isinstance(fixture, (str, type(None)))
        else fixture
    )
    assert value is not None
    audit = audit_atlas_architecture_data(value)
    plan = compile_atlas_architecture_plan(value)
    policy = score_atlas_architecture_policy(value.fixture_id, value.cases)
    evaluation = evaluate_atlas_architecture_fixture(value)
    review_queue = build_atlas_architecture_review_queue(value.fixture_id, value.cases)
    ledger = build_atlas_architecture_ledger(value.fixture_id, value.cases, evaluation)
    validation = validate_atlas_architecture_matrix(value, evaluation)
    schema = atlas_architecture_schema()
    metrics = materialize_atlas_architecture_metrics(
        value, evaluation, review_queue, len(validation)
    )
    artifacts = materialize_atlas_architecture_artifacts(
        value, evaluation, review_queue, ledger, metrics
    )
    access = atlas_architecture_access_policy(artifacts)
    replay = replay_atlas_architecture_fixture(value, evaluation)
    invariants = check_atlas_architecture_invariants(value, evaluation, plan, review_queue, ledger)
    runbook = atlas_architecture_runbook()
    failures = classify_atlas_architecture_failures(evaluation)
    observation = observe_atlas_architecture_run(run_id, len(ATLAS_ARCHITECTURE_STAGE_IDS), metrics)
    all_checks = tuple(
        audit.checks
        + evaluation.checks
        + policy.checks
        + validation
        + schema.checks
        + access.checks
        + replay_checks(replay)
        + invariants
        + runbook.checks
        + observation.checks
    )
    release = release_atlas_architecture(
        value, evaluation, review_queue, ledger, artifacts, all_checks
    )
    quality = assess_atlas_architecture_quality(
        value,
        evaluation,
        plan,
        review_queue,
        ledger,
        artifacts,
        release,
        len(ATLAS_ARCHITECTURE_STAGE_IDS),
    )
    depth = atlas_architecture_depth_report(value, evaluation, plan, review_queue, ledger)
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
        release,
        quality,
    )
    state = (
        AtlasArchitectureState.PUBLISHED
        if quality.passed and not failures.release_blocked and depth.accepted
        else AtlasArchitectureState.BLOCKED
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
    }
    return AtlasArchitectureRuntime(
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
        addressed(body, "atlas-runtime"),
    )


def replay_checks(replay: object) -> tuple[AtlasArchitectureCheck, ...]:
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
        AtlasArchitectureCheck(
            name,
            AtlasArchitectureCheckKind.LINEAGE,
            passed,
            observed,
            True,
            detail,
            addressed(
                {"check_id": name, "passed": passed, "observed": observed}, "atlas-replay-check"
            ),
        )
        for name, passed, observed, detail in values
    )


def _stages(
    value: AtlasArchitectureFixture,
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
    release: object,
    quality: object,
) -> list[AtlasArchitectureRuntimeStage]:
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
        addressed(validation, "atlas-validation"),
        schema.content_address,
        addressed(artifacts, "atlas-artifacts"),
        access.content_address,
        replay.content_address,
        release.content_address,
        quality.content_address,
    )
    states = [AtlasArchitectureState.ACCEPTED] * 18 + [release.state, quality.state]
    stages: list[AtlasArchitectureRuntimeStage] = []
    previous = f"sha256:{run_id}"
    for ordinal, (stage_id, output, state) in enumerate(
        zip(ATLAS_ARCHITECTURE_STAGE_IDS, outputs, states, strict=True), start=1
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
            AtlasArchitectureRuntimeStage(
                stage_id,
                ordinal,
                state,
                previous,
                output,
                f"{stage_id} completed",
                addressed(body, "atlas-runtime-stage"),
            )
        )
        previous = output
    return stages


__all__ = ["ATLAS_ARCHITECTURE_STAGE_IDS", "replay_checks", "run_atlas_architecture"]
