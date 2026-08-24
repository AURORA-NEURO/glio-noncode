"""Twenty-four-stage D10 link-graph runtime."""

from __future__ import annotations

from .link_graph_architecture_artifacts import build_link_graph_architecture_artifacts
from .link_graph_architecture_compliance import assess_link_graph_architecture_compliance
from .link_graph_architecture_contracts import (
    LinkGraphArchitectureFixture,
    LinkGraphArchitectureRuntime,
    LinkGraphArchitectureRuntimeStage,
    addressed,
)
from .link_graph_architecture_depth import assess_link_graph_architecture_depth
from .link_graph_architecture_ledger import build_link_graph_architecture_ledger
from .link_graph_architecture_metrics import link_graph_architecture_metrics
from .link_graph_architecture_operations import evaluate_link_graph_architecture_fixture
from .link_graph_architecture_plan import build_link_graph_architecture_plan
from .link_graph_architecture_public_data import (
    audit_link_graph_architecture_data,
    default_link_graph_architecture_fixture,
)
from .link_graph_architecture_quality import assess_link_graph_architecture_quality
from .link_graph_architecture_release import build_link_graph_architecture_release
from .link_graph_architecture_replay import replay_link_graph_architecture_fixture
from .link_graph_architecture_review import build_link_graph_architecture_review_queue
from .link_graph_architecture_schema import validate_link_graph_architecture_fixture

LINK_GRAPH_ARCHITECTURE_STAGE_IDS = (
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
    stage_id: str, ordinal: int, state: str, inputs: tuple[str, ...], output: str, detail: str
) -> LinkGraphArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": ("runtime-stage",),
        "detail": detail,
    }
    return LinkGraphArchitectureRuntimeStage(**body, content_address=addressed(body, "link-stage"))


def run_link_graph_architecture(
    fixture: LinkGraphArchitectureFixture | None = None,
) -> LinkGraphArchitectureRuntime:
    selected = fixture or default_link_graph_architecture_fixture()
    audit = audit_link_graph_architecture_data(selected)
    validate_link_graph_architecture_fixture(selected)
    plan = build_link_graph_architecture_plan(selected)
    evaluation = evaluate_link_graph_architecture_fixture(selected)
    review = build_link_graph_architecture_review_queue(evaluation)
    ledger = build_link_graph_architecture_ledger(selected, evaluation)
    artifacts = build_link_graph_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_link_graph_architecture_release(selected, evaluation, artifacts)
    replay = replay_link_graph_architecture_fixture(selected)
    quality = assess_link_graph_architecture_quality(
        selected, audit, plan, evaluation, replay, release, artifacts
    )
    depth = assess_link_graph_architecture_depth(selected, evaluation)
    compliance = assess_link_graph_architecture_compliance(selected)
    metrics = link_graph_architecture_metrics(selected, evaluation)
    outputs = (
        selected.content_address,
        audit.content_address,
        addressed(selected.to_dict(include_payload=False), "link-schema"),
        plan.content_address,
        selected.operations[3].content_address,
        selected.operations[7].content_address,
        selected.operations[11].content_address,
        selected.operations[15].content_address,
        evaluation.content_address,
        review.content_address,
        addressed(selected.sources, "link-lineage"),
        ledger.content_address,
        addressed(evaluation.checks, "link-metrics"),
        replay.content_address,
        addressed(artifacts, "link-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "link-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        addressed({"review": review.content_address}, "link-controls"),
        addressed(compliance, "link-compliance"),
        addressed(
            {
                "fixture": selected.content_address,
                "evaluation": evaluation.content_address,
                "metrics": metrics,
            },
            "link-report-stage",
        ),
        addressed({"fixture": selected.content_address}, "link-runtime-seed"),
        addressed(
            {
                "fixture": selected.content_address,
                "quality": quality.content_address,
                "release": release.content_address,
            },
            "link-runtime-final",
        ),
    )
    details = (
        "fixture constructed from four public link families",
        "source joins audited",
        "typed link schema validated",
        "sixteen link dependencies ordered",
        "foundation overlap, nearest-gene, cCRE, and consensus paths joined",
        "beta activity, coaccessibility, QTL, and allele paths joined",
        "alpha perturbation, contact, tethering, and graph paths joined",
        "frontier correction, ranking, calibration, and publication joined",
        "64 link cases executed with 458 checks",
        "48 link controls routed",
        "link source lineage closed",
        "link ledger closed",
        "link metrics materialized",
        "deterministic replay closed",
        "six link artifacts materialized",
        "link bundle address seeded",
        "link release built",
        "link quality gate passed",
        "link depth accounted",
        "link controls closed",
        "public aggregate compliance closed",
        "link report projection materialized",
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
            zip(LINK_GRAPH_ARCHITECTURE_STAGE_IDS, details, strict=True), start=1
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
    return LinkGraphArchitectureRuntime(
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
        addressed(body, "link-runtime"),
    )


__all__ = ["LINK_GRAPH_ARCHITECTURE_STAGE_IDS", "run_link_graph_architecture"]
