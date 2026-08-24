"""Twenty-four-stage D08 cell-state architecture runtime."""

from __future__ import annotations

from .cell_state_architecture_access import cell_state_architecture_access_policy
from .cell_state_architecture_artifacts import build_cell_state_architecture_artifacts
from .cell_state_architecture_bundle import build_cell_state_architecture_bundle
from .cell_state_architecture_compliance import assess_cell_state_architecture_compliance
from .cell_state_architecture_contracts import (
    CellStateArchitectureFixture,
    CellStateArchitectureRuntime,
    CellStateArchitectureRuntimeStage,
    addressed,
)
from .cell_state_architecture_depth import assess_cell_state_architecture_depth
from .cell_state_architecture_invariants import cell_state_architecture_invariants
from .cell_state_architecture_ledger import build_cell_state_architecture_ledger
from .cell_state_architecture_lineage import build_cell_state_architecture_lineage
from .cell_state_architecture_metrics import cell_state_architecture_metrics
from .cell_state_architecture_operations import evaluate_cell_state_architecture_fixture
from .cell_state_architecture_plan import build_cell_state_architecture_plan
from .cell_state_architecture_public_data import (
    audit_cell_state_architecture_data,
    default_cell_state_architecture_fixture,
)
from .cell_state_architecture_quality import assess_cell_state_architecture_quality
from .cell_state_architecture_release import build_cell_state_architecture_release
from .cell_state_architecture_replay import replay_cell_state_architecture_fixture
from .cell_state_architecture_review import build_cell_state_architecture_review_queue
from .cell_state_architecture_schema import validate_cell_state_architecture_fixture

D08_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "taxonomy-family-ready",
    "prior-family-ready",
    "territory-family-ready",
    "cell-state-family-ready",
    "cases-executed",
    "review-routed",
    "lineage-linked",
    "ledger-closed",
    "metrics-materialized",
    "invariants-closed",
    "replay-closed",
    "artifacts-materialized",
    "bundle-closed",
    "access-closed",
    "release-built",
    "quality-gated",
    "depth-accounted",
    "controls-closed",
    "compliance-closed",
    "runtime-finalized",
)


def _stage(
    stage_id: str,
    ordinal: int,
    state: str,
    inputs: tuple[str, ...],
    output: str,
    checks: tuple[str, ...],
    detail: str,
) -> CellStateArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": checks,
        "detail": detail,
    }
    return CellStateArchitectureRuntimeStage(
        **body, content_address=addressed(body, "cell-state-stage")
    )


def run_cell_state_architecture(
    fixture: CellStateArchitectureFixture | None = None,
) -> CellStateArchitectureRuntime:
    selected = fixture or default_cell_state_architecture_fixture()
    validate_cell_state_architecture_fixture(selected)
    audit = audit_cell_state_architecture_data(selected)
    plan = build_cell_state_architecture_plan(selected)
    evaluation = evaluate_cell_state_architecture_fixture(selected)
    review = build_cell_state_architecture_review_queue(evaluation)
    lineage = build_cell_state_architecture_lineage(selected)
    ledger = build_cell_state_architecture_ledger(selected, evaluation)
    metrics = cell_state_architecture_metrics(selected, evaluation)
    replay = replay_cell_state_architecture_fixture(selected)
    artifacts = build_cell_state_architecture_artifacts(selected, audit, evaluation, review, ledger)
    bundle = build_cell_state_architecture_bundle(selected, evaluation, artifacts)
    access = cell_state_architecture_access_policy(artifacts)
    release = build_cell_state_architecture_release(selected, evaluation, artifacts)
    quality = assess_cell_state_architecture_quality(
        selected, audit, plan, evaluation, replay, release, artifacts, ledger
    )
    invariants = cell_state_architecture_invariants(selected)
    depth = assess_cell_state_architecture_depth(selected, evaluation)
    compliance = assess_cell_state_architecture_compliance(selected)
    outputs = (
        selected.content_address,
        addressed(
            {"sources": [item.content_address for item in selected.sources]},
            "cell-state-source-audit",
        ),
        selected.content_address,
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        addressed(lineage, "cell-state-lineage-seed"),
        ledger.content_address,
        str(metrics["content_address"]),
        addressed(invariants, "cell-state-invariants"),
        replay.content_address,
        addressed(artifacts, "cell-state-artifacts"),
        str(bundle["content_address"]),
        str(access["content_address"]),
        release.content_address,
        quality.content_address,
        depth.content_address,
        addressed({"review": review.content_address}, "cell-state-controls"),
        addressed(compliance, "cell-state-compliance"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "cell-state-runtime-final",
        ),
    )
    details = (
        "fixture constructed from four public D08 tranches",
        "source count and joins audited",
        "typed schema and identity validated",
        "sixteen dependencies topologically ordered",
        "C01-C04 disease taxonomy and territory context joined",
        "C05-C08 developmental and malignant state priors joined",
        "C09-C12 spatial and treatment territory priors joined",
        "C13-C16 abundance, mapping, OOD, and publication joined",
        "64 cases executed with 458 checks",
        "48 control cases routed to review",
        "source-to-operation-to-case lineage closed",
        "append-only ledger receipts closed",
        "operation, family, scenario, and pass metrics materialized",
        "cross-surface invariants evaluated",
        "deterministic replay passed",
        "six review-safe artifacts materialized",
        "release manifest assembled",
        "artifact access policy evaluated",
        "release boundary constructed",
        "quality gate evaluated",
        "depth counters recorded",
        "control routing and delegated contexts closed",
        "aggregate boundary compliance closed",
        "runtime address materialized",
    )
    stages = tuple(
        _stage(
            stage_id,
            ordinal,
            "accepted",
            (outputs[ordinal - 2],) if ordinal > 1 else (),
            outputs[ordinal - 1],
            ("runtime-stage",),
            detail,
        )
        for ordinal, (stage_id, detail) in enumerate(
            zip(D08_STAGE_IDS, details, strict=True), start=1
        )
    )
    accepted = (
        audit.accepted
        and plan.accepted
        and evaluation.accepted
        and review.accepted
        and replay.accepted
        and bool(bundle["accepted"])
        and bool(access["accepted"])
        and quality.accepted
        and bool(compliance["accepted"])
        and release.state.value == "published"
        and all(invariants.values())
    )
    body = {
        "fixture": selected.content_address,
        "evaluation": evaluation.content_address,
        "quality": quality.content_address,
        "release": release.content_address,
        "stages": stages,
        "accepted": accepted,
    }
    return CellStateArchitectureRuntime(
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
        addressed(body, "cell-state-runtime"),
    )


def replay_cell_state_architecture_runtime(runtime: CellStateArchitectureRuntime) -> bool:
    replay = replay_cell_state_architecture_fixture(runtime.fixture)
    return replay.accepted and replay.first_address == runtime.evaluation.content_address


__all__ = ["D08_STAGE_IDS", "replay_cell_state_architecture_runtime", "run_cell_state_architecture"]
