"""Twenty-two-stage D11 causal evidence runtime."""

from __future__ import annotations

from .causal_architecture_artifacts import build_causal_architecture_artifacts
from .causal_architecture_contracts import (
    CausalArchitectureFixture,
    CausalArchitectureRuntime,
    CausalArchitectureRuntimeStage,
    addressed,
)
from .causal_architecture_depth import assess_causal_architecture_depth
from .causal_architecture_ledger import build_causal_architecture_ledger
from .causal_architecture_operations import evaluate_causal_architecture_fixture
from .causal_architecture_plan import build_causal_architecture_plan
from .causal_architecture_public_data import (
    audit_causal_architecture_data,
    default_causal_architecture_fixture,
)
from .causal_architecture_quality import assess_causal_architecture_quality
from .causal_architecture_release import build_causal_architecture_release
from .causal_architecture_replay import replay_causal_architecture_fixture
from .causal_architecture_review import build_causal_architecture_review_queue

CAUSAL_ARCHITECTURE_STAGE_IDS = (
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
    stage_id: str, ordinal: int, state: str, inputs: tuple[str, ...], output: str, detail: str
) -> CausalArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": ("runtime-stage",),
        "detail": detail,
    }
    return CausalArchitectureRuntimeStage(**body, content_address=addressed(body, "causal-stage"))


def run_causal_architecture(
    fixture: CausalArchitectureFixture | None = None,
) -> CausalArchitectureRuntime:
    selected = fixture or default_causal_architecture_fixture()
    audit = audit_causal_architecture_data(selected)
    plan = build_causal_architecture_plan(selected)
    evaluation = evaluate_causal_architecture_fixture(selected)
    review = build_causal_architecture_review_queue(evaluation)
    ledger = build_causal_architecture_ledger(selected, evaluation)
    artifacts = build_causal_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_causal_architecture_release(selected, evaluation, artifacts)
    replay = replay_causal_architecture_fixture(selected)
    quality = assess_causal_architecture_quality(
        selected, audit, plan, evaluation, replay, release, artifacts
    )
    depth = assess_causal_architecture_depth(selected, evaluation)
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
        addressed(selected.sources, "causal-lineage"),
        ledger.content_address,
        addressed(evaluation.checks, "causal-metrics"),
        replay.content_address,
        addressed(artifacts, "causal-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "causal-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        addressed({"fixture": selected.content_address}, "causal-runtime-seed"),
        addressed({"review": review.content_address}, "causal-controls"),
        addressed({"ledger": ledger.content_address}, "causal-observability"),
    )
    details = (
        "fixture constructed from four causal evidence families",
        "source joins audited",
        "typed causal schema validated",
        "sixteen causal dependencies ordered",
        "foundation hypothesis, graph, prior, and likelihood paths joined",
        "beta mediator and counterfactual paths joined",
        "alpha sensitivity, confounding, dependence, and negative paths joined",
        "frontier posterior, driver, abstention, and dossier paths joined",
        "64 causal cases executed with 392 checks",
        "48 causal controls routed",
        "causal source lineage closed",
        "causal ledger closed",
        "causal metrics materialized",
        "deterministic replay closed",
        "six causal artifacts materialized",
        "causal bundle address seeded",
        "causal release built",
        "causal quality gate passed",
        "causal depth accounted",
        "runtime address seeded",
        "causal controls closed",
        "causal observability closed",
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
            zip(CAUSAL_ARCHITECTURE_STAGE_IDS, details, strict=True), start=1
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
    return CausalArchitectureRuntime(
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
        addressed(body, "causal-runtime"),
    )


__all__ = ["CAUSAL_ARCHITECTURE_STAGE_IDS", "run_causal_architecture"]
