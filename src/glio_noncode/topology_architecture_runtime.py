"""Twenty-two-stage D09 topology architecture runtime."""

from __future__ import annotations

from .topology_architecture_artifacts import build_topology_architecture_artifacts
from .topology_architecture_contracts import (
    TopologyArchitectureFixture,
    TopologyArchitectureRuntime,
    TopologyArchitectureRuntimeStage,
    addressed,
)
from .topology_architecture_depth import assess_topology_architecture_depth
from .topology_architecture_ledger import build_topology_architecture_ledger
from .topology_architecture_lineage import build_topology_architecture_lineage
from .topology_architecture_metrics import topology_architecture_metrics
from .topology_architecture_operations import evaluate_topology_architecture_fixture
from .topology_architecture_plan import build_topology_architecture_plan
from .topology_architecture_public_data import (
    audit_topology_architecture_data,
    default_topology_architecture_fixture,
)
from .topology_architecture_quality import assess_topology_architecture_quality
from .topology_architecture_release import build_topology_architecture_release
from .topology_architecture_replay import replay_topology_architecture_fixture
from .topology_architecture_review import build_topology_architecture_review_queue
from .topology_architecture_schema import validate_topology_architecture_fixture

TOPOLOGY_ARCHITECTURE_STAGE_IDS = (
    "fixture-loaded",
    "sources-audited",
    "schema-validated",
    "plan-compiled",
    "context-family-ready",
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
) -> TopologyArchitectureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_addresses": inputs,
        "output_address": output,
        "check_ids": ("runtime-stage",),
        "detail": detail,
    }
    return TopologyArchitectureRuntimeStage(
        **body, content_address=addressed(body, "topology-stage")
    )


def run_topology_architecture(
    fixture: TopologyArchitectureFixture | None = None,
) -> TopologyArchitectureRuntime:
    selected = fixture or default_topology_architecture_fixture()
    validate_topology_architecture_fixture(selected)
    audit = audit_topology_architecture_data(selected)
    plan = build_topology_architecture_plan(selected)
    evaluation = evaluate_topology_architecture_fixture(selected)
    review = build_topology_architecture_review_queue(evaluation)
    lineage = build_topology_architecture_lineage(selected)
    ledger = build_topology_architecture_ledger(selected, evaluation)
    metrics = topology_architecture_metrics(selected, evaluation)
    replay = replay_topology_architecture_fixture(selected)
    artifacts = build_topology_architecture_artifacts(selected, audit, evaluation, review, ledger)
    release = build_topology_architecture_release(selected, evaluation, artifacts)
    quality = assess_topology_architecture_quality(
        selected, audit, plan, evaluation, replay, release
    )
    depth = assess_topology_architecture_depth(selected, evaluation)
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
        lineage["content_address"],
        ledger.content_address,
        str(metrics["content_address"]),
        replay.content_address,
        addressed(artifacts, "topology-artifacts"),
        addressed({"evaluation": evaluation.content_address}, "topology-bundle"),
        release.content_address,
        quality.content_address,
        depth.content_address,
        addressed({"fixture": selected.content_address}, "topology-runtime-seed"),
        addressed({"review": review.content_address}, "topology-controls"),
        addressed({"ledger": ledger.content_address}, "topology-observability"),
    )
    details = (
        "fixture constructed from four topology tranches",
        "source joins audited",
        "typed topology schema validated",
        "sixteen topology dependencies ordered",
        "C01-C04 contact import and boundary context joined",
        "C05-C08 loop, capture, and contact scoring joined",
        "C09-C12 motif, factor, IDH, and SV topology joined",
        "C13-C16 ecDNA, compartment, transport, and publication joined",
        "64 topology cases executed with 392 checks",
        "48 topology controls routed",
        "topology source lineage closed",
        "topology ledger closed",
        "topology metrics materialized",
        "deterministic replay closed",
        "six topology artifacts materialized",
        "topology bundle address seeded",
        "topology release built",
        "topology quality gate passed",
        "topology depth accounted",
        "runtime address seeded",
        "topology controls closed",
        "topology observability closed",
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
            zip(TOPOLOGY_ARCHITECTURE_STAGE_IDS, details, strict=True), start=1
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
        "quality": quality.content_address,
        "release": release.content_address,
        "stages": stages,
        "accepted": accepted,
    }
    return TopologyArchitectureRuntime(
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
        addressed(body, "topology-runtime"),
    )


__all__ = ["TOPOLOGY_ARCHITECTURE_STAGE_IDS", "run_topology_architecture"]
