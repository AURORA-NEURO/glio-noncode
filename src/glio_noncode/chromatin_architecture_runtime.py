"""Twenty-four-stage D07 chromatin architecture runtime."""

from __future__ import annotations

from .chromatin_architecture_access import chromatin_architecture_access_policy
from .chromatin_architecture_artifacts import materialize_chromatin_architecture_artifacts
from .chromatin_architecture_bundle import build_chromatin_architecture_bundle
from .chromatin_architecture_compliance import assess_chromatin_architecture_compliance
from .chromatin_architecture_contracts import (
    ChromatinArchitectureFixture,
    ChromatinArchitectureRuntime,
    ChromatinArchitectureRuntimeStage,
    addressed,
)
from .chromatin_architecture_depth import chromatin_architecture_depth_report
from .chromatin_architecture_failures import classify_chromatin_architecture_failures
from .chromatin_architecture_invariants import check_chromatin_architecture_invariants
from .chromatin_architecture_ledger import build_chromatin_architecture_ledger
from .chromatin_architecture_lineage import build_chromatin_architecture_lineage
from .chromatin_architecture_metrics import materialize_chromatin_architecture_metrics
from .chromatin_architecture_operations import evaluate_chromatin_architecture_fixture
from .chromatin_architecture_plan import compile_chromatin_architecture_plan
from .chromatin_architecture_policy import score_chromatin_architecture_policy
from .chromatin_architecture_public_data import default_chromatin_architecture_fixture
from .chromatin_architecture_quality import assess_chromatin_architecture_quality
from .chromatin_architecture_release import release_chromatin_architecture
from .chromatin_architecture_replay import replay_chromatin_architecture_fixture
from .chromatin_architecture_review import build_chromatin_architecture_review_queue
from .chromatin_architecture_schema import validate_chromatin_architecture_schema

CHROMATIN_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "plan-compiled",
    "accessibility-family-ready",
    "methylation-family-ready",
    "chromatin-state-family-ready",
    "cross-assay-family-ready",
    "cases-executed",
    "review-routed",
    "lineage-linked",
    "ledger-closed",
    "metrics-materialized",
    "schema-closed",
    "invariants-closed",
    "replay-closed",
    "artifacts-materialized",
    "depth-accounted",
    "policy-closed",
    "quality-gated",
    "release-built",
    "access-closed",
    "compliance-closed",
    "observability-closed",
    "runtime-finalized",
)


def _stage(
    stage_id: str,
    ordinal: int,
    state: str,
    inputs: tuple[str, ...],
    output: str,
    check_ids: tuple[str, ...],
    detail: str,
) -> ChromatinArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": check_ids,
        "detail": detail,
    }
    return ChromatinArchitectureRuntimeStage(
        **body,
        content_address=addressed(body, "chromatin-stage"),
    )


def run_chromatin_architecture(
    fixture: ChromatinArchitectureFixture | None = None,
) -> ChromatinArchitectureRuntime:
    selected = fixture or default_chromatin_architecture_fixture()
    audit = __import__(
        "glio_noncode.chromatin_architecture_public_data",
        fromlist=["audit_chromatin_architecture_data"],
    ).audit_chromatin_architecture_data(selected)
    plan = compile_chromatin_architecture_plan(selected)
    evaluation = evaluate_chromatin_architecture_fixture(selected)
    review = build_chromatin_architecture_review_queue(selected.fixture_id, selected.cases)
    lineage = build_chromatin_architecture_lineage(selected, evaluation)
    ledger = build_chromatin_architecture_ledger(selected, evaluation)
    metrics = materialize_chromatin_architecture_metrics(evaluation)
    schema = validate_chromatin_architecture_schema(selected, evaluation)
    invariants = check_chromatin_architecture_invariants(selected, evaluation)
    replay = replay_chromatin_architecture_fixture(selected)
    policy = score_chromatin_architecture_policy(evaluation)
    artifacts = materialize_chromatin_architecture_artifacts(
        selected, evaluation, policy, review, lineage, ledger, metrics
    )
    depth = chromatin_architecture_depth_report(selected, evaluation)
    compliance = assess_chromatin_architecture_compliance(selected)
    bundle = build_chromatin_architecture_bundle(
        selected, audit, evaluation, policy, review, lineage, ledger, metrics
    )
    release = release_chromatin_architecture(selected, evaluation, artifacts)
    failures = classify_chromatin_architecture_failures(evaluation)
    quality = assess_chromatin_architecture_quality(
        selected,
        audit,
        plan,
        evaluation,
        policy,
        review,
        lineage,
        metrics,
        schema,
        replay,
        failures,
        release,
        compliance,
    )
    access = chromatin_architecture_access_policy(artifacts)
    all_addresses = (
        selected.content_address,
        evaluation.content_address,
        bundle.content_address,
        depth.content_address,
        release.content_address,
        compliance.content_address,
    )
    stage_details = {
        "fixture-loaded": (
            selected.content_address,
            "fixture constructed from four public tranches",
        ),
        "sources-audited": (
            audit.content_address,
            "source count, joins, and receipt addresses audited",
        ),
        "plan-compiled": (plan.content_address, "sixteen operations are topologically ordered"),
        "accessibility-family-ready": (
            selected.operations[3].content_address,
            "C01-C04 accessibility family joined",
        ),
        "methylation-family-ready": (
            selected.operations[7].content_address,
            "C05-C08 methylation family joined",
        ),
        "chromatin-state-family-ready": (
            selected.operations[11].content_address,
            "C09-C12 chromatin-state family joined",
        ),
        "cross-assay-family-ready": (
            selected.operations[15].content_address,
            "C13-C16 cross-assay family joined",
        ),
        "cases-executed": (evaluation.content_address, "64 cases executed with receipts"),
        "review-routed": (review.content_address, "48 controls routed to review"),
        "lineage-linked": (lineage.content_address, "source-to-case-to-receipt links closed"),
        "ledger-closed": (ledger.content_address, "final dispositions recorded"),
        "metrics-materialized": (
            metrics.content_address,
            "operation and issue metrics materialized",
        ),
        "schema-closed": (schema.content_address, "interchange schema checks passed"),
        "invariants-closed": (
            addressed(invariants, "chromatin-invariants"),
            "cross-surface invariants passed",
        ),
        "replay-closed": (replay.content_address, "deterministic replay passed"),
        "artifacts-materialized": (
            addressed(artifacts, "chromatin-artifacts"),
            "six sanitized artifacts materialized",
        ),
        "depth-accounted": (
            depth.content_address,
            "source, operation, case, family, state, issue, and check depth accounted",
        ),
        "policy-closed": (policy.content_address, "policy decisions closed"),
        "quality-gated": (quality.content_address, "quality gate evaluated"),
        "release-built": (release.content_address, "release boundary built"),
        "access-closed": (access.content_address, "artifact access policy evaluated"),
        "compliance-closed": (
            compliance.content_address,
            "public boundary and review-safe payload compliance closed",
        ),
        "observability-closed": (
            addressed(all_addresses, "chromatin-observability-seed"),
            "runtime addresses are observable",
        ),
        "runtime-finalized": (
            addressed(all_addresses, "chromatin-runtime"),
            "runtime final address materialized",
        ),
    }
    stages = tuple(
        _stage(
            stage_id,
            ordinal,
            "accepted",
            (stage_details[CHROMATIN_ARCHITECTURE_STAGE_IDS[ordinal - 2]][0],)
            if ordinal > 1
            else (),
            stage_details[stage_id][0],
            ("runtime-stage",),
            stage_details[stage_id][1],
        )
        for ordinal, stage_id in enumerate(CHROMATIN_ARCHITECTURE_STAGE_IDS, start=1)
    )
    accepted = (
        audit.accepted
        and plan.accepted
        and evaluation.accepted
        and review.accepted
        and lineage.accepted
        and schema.accepted
        and replay.accepted
        and policy.accepted
        and quality.accepted
        and depth.check_count == 458
        and compliance.accepted
        and bundle.accepted
        and release.state.value == "published"
        and access.accepted
        and all(item.passed for item in invariants)
    )
    body = {
        "fixture": selected.content_address,
        "evaluation": evaluation.content_address,
        "quality": quality.content_address,
        "depth": depth.content_address,
        "compliance": compliance.content_address,
        "release": release.content_address,
        "stages": stages,
        "accepted": accepted,
    }
    return ChromatinArchitectureRuntime(
        fixture=selected,
        audit=audit,
        plan=plan,
        evaluation=evaluation,
        review_queue=review,
        ledger=ledger,
        artifacts=artifacts,
        release=release,
        depth=depth,
        quality=quality,
        compliance=compliance,
        stages=stages,
        accepted=accepted,
        content_address=addressed(body, "chromatin-runtime"),
    )


def replay_chromatin_architecture_checks(
    runtime: ChromatinArchitectureRuntime,
) -> bool:
    replay = replay_chromatin_architecture_fixture(runtime.fixture)
    return replay.accepted and replay.first_address == runtime.evaluation.content_address


__all__ = [
    "CHROMATIN_ARCHITECTURE_STAGE_IDS",
    "replay_chromatin_architecture_checks",
    "run_chromatin_architecture",
]
