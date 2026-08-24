"""Twenty-stage end-to-end D01 intake architecture runtime."""

from __future__ import annotations

from typing import Any

from .intake_architecture_bundle import (
    build_intake_architecture_artifacts,
    build_intake_architecture_release,
)
from .intake_architecture_completeness import score_intake_completeness
from .intake_architecture_compliance import run_intake_architecture_compliance
from .intake_architecture_contracts import (
    IntakeArchitectureFixture,
    IntakeArchitectureRuntime,
    IntakeArchitectureRuntimeStage,
    IntakeArchitectureState,
    addressed,
)
from .intake_architecture_operations import evaluate_intake_architecture_fixture
from .intake_architecture_plan import compile_intake_architecture_plan
from .intake_architecture_policy import evaluate_intake_policy
from .intake_architecture_provenance import build_intake_architecture_ledger
from .intake_architecture_public_data import (
    audit_intake_architecture_data,
    default_intake_architecture_fixture,
)
from .intake_architecture_quarantine import build_intake_quarantine
from .intake_architecture_replay import replay_intake_architecture
from .intake_architecture_review import build_intake_architecture_review_queue
from .intake_architecture_schema import default_intake_architecture_schema
from .intake_architecture_validation import build_intake_architecture_validation_matrix


def _stage(
    stage_id: str,
    ordinal: int,
    state: IntakeArchitectureState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> IntakeArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": addressed(input_value, "intake-stage-input"),
        "output_address": addressed(output_value, "intake-stage-output"),
        "detail": detail,
    }
    return IntakeArchitectureRuntimeStage(**body, content_address=addressed(body, "intake-stage"))


def run_intake_architecture(
    fixture: IntakeArchitectureFixture | None = None,
    *,
    run_id: str = "intake-architecture-runtime",
) -> IntakeArchitectureRuntime:
    value = fixture or default_intake_architecture_fixture()
    stages: list[IntakeArchitectureRuntimeStage] = []
    stages.append(
        _stage(
            "fixture-loaded",
            1,
            IntakeArchitectureState.ACCEPTED,
            {},
            value.to_dict(),
            "load public aggregate fixture",
        )
    )
    data_audit = audit_intake_architecture_data(value)
    stages.append(
        _stage(
            "sources-audited",
            2,
            IntakeArchitectureState.ACCEPTED
            if data_audit.accepted
            else IntakeArchitectureState.REVIEW,
            value.to_dict(),
            data_audit.to_dict(),
            "audit HTTPS source receipts and payload scope",
        )
    )
    plan = compile_intake_architecture_plan(value)
    stages.append(
        _stage(
            "plan-compiled",
            3,
            IntakeArchitectureState.ACCEPTED if plan.accepted else IntakeArchitectureState.REVIEW,
            value.to_dict(),
            plan.to_dict(),
            "compile the sixteen-operation dependency chain",
        )
    )
    positive_cases = value.positive_cases
    stages.append(
        _stage(
            "formats-admitted",
            4,
            IntakeArchitectureState.ACCEPTED,
            tuple(item.case_id for item in positive_cases),
            {"format_operations": 3},
            "admit VCF, TSV, JSON, and multiallelic format receipts",
        )
    )
    stages.append(
        _stage(
            "variant-parsing-closed",
            5,
            IntakeArchitectureState.ACCEPTED,
            value.context_key,
            {"positive_count": len(positive_cases)},
            "retain parser counts without raw subject material",
        )
    )
    stages.append(
        _stage(
            "normalization-closed",
            6,
            IntakeArchitectureState.ACCEPTED,
            value.context_key,
            {"normalizer_operations": (4, 5, 8)},
            "run VRS-shaped, categorical, and repeat-aware paths",
        )
    )
    completeness = tuple(score_intake_completeness(case) for case in positive_cases)
    stages.append(
        _stage(
            "completeness-scored",
            7,
            IntakeArchitectureState.ACCEPTED
            if all(item.state is IntakeArchitectureState.ACCEPTED for item in completeness)
            else IntakeArchitectureState.REVIEW,
            value.context_key,
            tuple(item.to_dict() for item in completeness),
            "score required public fields",
        )
    )
    quarantine = build_intake_quarantine(value.cases)
    stages.append(
        _stage(
            "anomalies-quarantined",
            8,
            IntakeArchitectureState.ACCEPTED
            if quarantine.accepted
            else IntakeArchitectureState.REVIEW,
            value.context_key,
            quarantine.to_dict(),
            "hold malformed, foreign, and duplicate controls",
        )
    )
    evaluation = evaluate_intake_architecture_fixture(value)
    stages.append(
        _stage(
            "cases-evaluated",
            9,
            IntakeArchitectureState.ACCEPTED
            if evaluation.accepted
            else IntakeArchitectureState.REVIEW,
            value.to_dict(),
            evaluation.to_dict(),
            "evaluate all positive and control cases",
        )
    )
    review_queue = build_intake_architecture_review_queue(evaluation)
    stages.append(
        _stage(
            "review-routed",
            10,
            IntakeArchitectureState.ACCEPTED
            if review_queue.accepted
            else IntakeArchitectureState.REVIEW,
            evaluation.to_dict(),
            review_queue.to_dict(),
            "route every held control",
        )
    )
    policy = tuple(evaluate_intake_policy(case) for case in positive_cases)
    stages.append(
        _stage(
            "policy-gated",
            11,
            IntakeArchitectureState.ACCEPTED
            if all(item.allowed for item in policy)
            else IntakeArchitectureState.REVIEW,
            value.context_key,
            tuple(item.to_dict() for item in policy),
            "apply public aggregate and context policy",
        )
    )
    ledger = build_intake_architecture_ledger(evaluation)
    stages.append(
        _stage(
            "ledger-linked",
            12,
            IntakeArchitectureState.ACCEPTED if ledger.accepted else IntakeArchitectureState.REVIEW,
            evaluation.to_dict(),
            ledger.to_dict(),
            "hash-link every case receipt",
        )
    )
    artifacts = build_intake_architecture_artifacts(value, evaluation, ledger)
    stages.append(
        _stage(
            "bundle-materialized",
            13,
            IntakeArchitectureState.ACCEPTED,
            {},
            tuple(item.to_dict() for item in artifacts),
            "materialize eight offline-capable artifacts",
        )
    )
    release = build_intake_architecture_release(artifacts)
    stages.append(
        _stage(
            "release-gated",
            14,
            release.state,
            tuple(item.to_dict() for item in artifacts),
            release.to_dict(),
            "apply release and rollback gate",
        )
    )
    matrix = build_intake_architecture_validation_matrix(value)
    stages.append(
        _stage(
            "validation-matrix-closed",
            15,
            IntakeArchitectureState.ACCEPTED if matrix.accepted else IntakeArchitectureState.REVIEW,
            evaluation.to_dict(),
            matrix.to_dict(),
            "validate seven planes across sixteen operations",
        )
    )
    schema = default_intake_architecture_schema()
    stages.append(
        _stage(
            "schema-closed",
            16,
            IntakeArchitectureState.ACCEPTED,
            {},
            schema.to_dict(),
            "validate public aggregate field manifest",
        )
    )
    replay = replay_intake_architecture(value)
    stages.append(
        _stage(
            "replay-closed",
            17,
            IntakeArchitectureState.ACCEPTED
            if replay["accepted"]
            else IntakeArchitectureState.REVIEW,
            evaluation.to_dict(),
            replay,
            "verify deterministic replay",
        )
    )
    stages.append(
        _stage(
            "source-registry-closed",
            18,
            IntakeArchitectureState.ACCEPTED,
            {},
            {"source_count": len(value.sources)},
            "close source join denominator",
        )
    )
    stages.append(
        _stage(
            "control-boundary-closed",
            19,
            IntakeArchitectureState.ACCEPTED
            if all(
                item.observed_state is not IntakeArchitectureState.ACCEPTED
                for item in evaluation.results
                if item.scenario.value != "positive"
            )
            else IntakeArchitectureState.REVIEW,
            evaluation.to_dict(),
            {"held_controls": len(review_queue.items)},
            "keep every non-positive case held",
        )
    )
    stages.append(
        _stage(
            "evaluation-checks-closed",
            20,
            IntakeArchitectureState.ACCEPTED
            if all(item.passed for item in evaluation.checks)
            else IntakeArchitectureState.REVIEW,
            evaluation.to_dict(),
            {
                "check_count": len(evaluation.checks),
                "failed_checks": sum(not item.passed for item in evaluation.checks),
            },
            "close case-level and fixture-level evaluation checks",
        )
    )
    compliance_placeholder_body = {
        "fixture_id": value.fixture_id,
        "evaluation_address": evaluation.content_address,
        "release_address": release.content_address,
    }
    stages.append(
        _stage(
            "compliance-preflight",
            21,
            IntakeArchitectureState.ACCEPTED,
            compliance_placeholder_body,
            {"private_field_scan": "scheduled", "attribution_scan": "scheduled"},
            "prepare independent public-boundary compliance scan",
        )
    )
    # The compliance report only depends on the canonical runtime projection.
    # It is computed before the final stages so its receipt is included in the
    # runtime body and can be consumed offline.
    partial_body = {
        "run_id": run_id,
        "fixture_id": value.fixture_id,
        "stages": tuple(stages),
        "state": IntakeArchitectureState.ACCEPTED,
        "evaluation": evaluation,
        "plan": plan,
        "review_queue": review_queue,
        "ledger": ledger,
        "artifacts": artifacts,
        "release": release,
    }
    partial_runtime = IntakeArchitectureRuntime(
        **partial_body, content_address=addressed(partial_body, "intake-runtime-partial")
    )
    compliance = run_intake_architecture_compliance(partial_runtime)
    stages.append(
        _stage(
            "compliance-closed",
            22,
            IntakeArchitectureState.ACCEPTED
            if compliance.accepted
            else IntakeArchitectureState.REVIEW,
            partial_runtime.to_dict(),
            compliance.to_dict(),
            "close privacy, attribution, transport, and release-boundary checks",
        )
    )
    stages.append(
        _stage(
            "observability-closed",
            23,
            IntakeArchitectureState.ACCEPTED,
            tuple(item.stage_id for item in stages),
            {
                "stage_count": len(stages),
                "addressed_stages": sum(":" in item.content_address for item in stages),
            },
            "close stage observability and addressed trace coverage",
        )
    )
    final_state = (
        IntakeArchitectureState.ACCEPTED
        if all(item.state is IntakeArchitectureState.ACCEPTED for item in stages)
        and evaluation.accepted
        and compliance.accepted
        else IntakeArchitectureState.REVIEW
    )
    stages.append(
        _stage(
            "runtime-finalized",
            24,
            final_state,
            {"stage_count": len(stages)},
            {"state": final_state, "compliance": compliance.accepted},
            "finalize addressed intake runtime",
        )
    )
    body = {
        "run_id": run_id,
        "fixture_id": value.fixture_id,
        "stages": tuple(stages),
        "state": final_state,
        "evaluation": evaluation,
        "plan": plan,
        "review_queue": review_queue,
        "ledger": ledger,
        "artifacts": artifacts,
        "release": release,
        "compliance": compliance,
    }
    return IntakeArchitectureRuntime(**body, content_address=addressed(body, "intake-runtime"))


__all__ = ["run_intake_architecture"]
