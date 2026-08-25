"""Twelve-stage deterministic runtime for closing the D14 offline handoff."""

from __future__ import annotations

from typing import Any

from .evidence_lifecycle_frontier_offline_bundle import build_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_closure_boundary import (
    audit_evidence_lifecycle_closure_boundary,
)
from .evidence_lifecycle_frontier_offline_closure_certification import (
    certify_evidence_lifecycle_closure,
)
from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_VERSION,
    EvidenceLifecycleClosureReplay,
    EvidenceLifecycleClosureRuntimeReport,
    EvidenceLifecycleClosureRuntimeStage,
    EvidenceLifecycleClosureState,
)
from .evidence_lifecycle_frontier_offline_closure_graph import (
    build_evidence_lifecycle_closure_graph,
)
from .evidence_lifecycle_frontier_offline_closure_indexes import (
    audit_evidence_lifecycle_closure_indexes,
    build_evidence_lifecycle_closure_indexes,
)
from .evidence_lifecycle_frontier_offline_closure_observability import (
    build_evidence_lifecycle_closure_observability,
)
from .evidence_lifecycle_frontier_offline_closure_reconciliation import (
    diff_evidence_lifecycle_closure_bundles,
    reconcile_evidence_lifecycle_closure,
)
from .evidence_lifecycle_frontier_offline_closure_summary import (
    audit_evidence_lifecycle_closure_summary,
    build_evidence_lifecycle_closure_summary,
)
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash, jsonable, require_non_empty


def _stage(
    ordinal: int, stage_id: str, input_address: str, value: Any, detail: str
) -> EvidenceLifecycleClosureRuntimeStage:
    output_address = content_hash(
        {"stage_id": stage_id, "value": jsonable(value)},
        prefix="evidence-lifecycle-closure-stage-output",
    )
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": EvidenceLifecycleClosureState.READY,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return EvidenceLifecycleClosureRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-runtime-stage"),
    )


def _replay(
    left: EvidenceLifecycleOfflineBundle, right: EvidenceLifecycleOfflineBundle
) -> EvidenceLifecycleClosureReplay:
    delta = diff_evidence_lifecycle_closure_bundles(left, right)
    body = {
        "first_address": left.content_address,
        "second_address": right.content_address,
        "expected_address": left.content_address,
        "deterministic": delta.accepted and left.content_address == right.content_address,
        "accepted": delta.accepted and left.content_address == right.content_address,
    }
    return EvidenceLifecycleClosureReplay(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-replay")
    )


def run_evidence_lifecycle_closure_runtime(
    *,
    bundle_id: str = "evidence-lifecycle-public-bundle",
    run_id: str = "evidence-lifecycle-closure-runtime",
) -> EvidenceLifecycleClosureRuntimeReport:
    """Run source materialization plus every independent closure projection."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    source_bundle = build_evidence_lifecycle_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:source"
    )
    stages: list[EvidenceLifecycleClosureRuntimeStage] = []
    input_address = source_bundle.content_address
    stages.append(
        _stage(
            1,
            "source_bundle",
            input_address,
            source_bundle.to_dict(include_payloads=False),
            "materialize source D14 bundle",
        )
    )
    boundary = audit_evidence_lifecycle_closure_boundary(source_bundle)
    stages.append(
        _stage(
            2,
            "boundary",
            stages[-1].output_address,
            boundary,
            "audit public boundary and forbidden keys",
        )
    )
    indexes = build_evidence_lifecycle_closure_indexes(source_bundle)
    stages.append(
        _stage(
            3, "indexes", stages[-1].output_address, indexes, "build ten bounded closure indexes"
        )
    )
    index_audit = audit_evidence_lifecycle_closure_indexes(source_bundle, indexes)
    stages.append(
        _stage(
            4,
            "index_audit",
            stages[-1].output_address,
            index_audit,
            "audit index conservation and addresses",
        )
    )
    reconciliation = reconcile_evidence_lifecycle_closure(source_bundle)
    stages.append(
        _stage(
            5,
            "reconciliation",
            stages[-1].output_address,
            reconciliation,
            "reconcile source projections and denominators",
        )
    )
    summary = build_evidence_lifecycle_closure_summary(source_bundle)
    stages.append(
        _stage(
            6,
            "summary",
            stages[-1].output_address,
            summary,
            "materialize operation, queue, and state summary",
        )
    )
    summary_audit = audit_evidence_lifecycle_closure_summary(summary)
    stages.append(
        _stage(
            7,
            "summary_audit",
            stages[-1].output_address,
            summary_audit,
            "audit summary conservation",
        )
    )
    certification = certify_evidence_lifecycle_closure(source_bundle)
    stages.append(
        _stage(
            8,
            "certification",
            stages[-1].output_address,
            certification,
            "issue eight-domain certification",
        )
    )
    observability = build_evidence_lifecycle_closure_observability(source_bundle)
    stages.append(
        _stage(
            9,
            "observability",
            stages[-1].output_address,
            observability,
            "materialize closure events and metrics",
        )
    )
    graph = build_evidence_lifecycle_closure_graph(source_bundle)
    stages.append(
        _stage(
            10, "graph", stages[-1].output_address, graph, "build connected public closure graph"
        )
    )
    replay_left = build_evidence_lifecycle_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:replay"
    )
    replay_right = build_evidence_lifecycle_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:replay"
    )
    replay = _replay(replay_left, replay_right)
    stages.append(
        _stage(
            11, "replay", stages[-1].output_address, replay, "verify deterministic source replay"
        )
    )
    accepted = all(
        (
            boundary.accepted,
            indexes.accepted,
            index_audit.accepted,
            reconciliation.accepted,
            summary.accepted,
            summary_audit.accepted,
            certification.accepted,
            observability.accepted,
            graph.accepted,
            replay.accepted,
        )
    )
    final_value = {
        "accepted": accepted,
        "bundle_id": source_bundle.bundle_id,
        "stage_count": len(stages) + 1,
        "certification": certification.content_address,
        "replay": replay.content_address,
    }
    stages.append(
        _stage(
            12,
            "finalize",
            stages[-1].output_address,
            final_value,
            "finalize closure release decision",
        )
    )
    state = (
        EvidenceLifecycleClosureState.READY if accepted else EvidenceLifecycleClosureState.BLOCKED
    )
    body = {
        "run_id": run_id,
        "state": state,
        "stages": tuple(stages),
        "bundle": source_bundle,
        "boundary": boundary,
        "indexes": indexes,
        "index_audit": index_audit,
        "reconciliation": reconciliation,
        "summary": summary,
        "summary_audit": summary_audit,
        "certification": certification,
        "observability": observability,
        "graph": graph,
        "replay": replay,
        "accepted": accepted,
    }
    return EvidenceLifecycleClosureRuntimeReport(
        **body,
        content_address=content_hash(
            {"version": EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_VERSION, **body},
            prefix="evidence-lifecycle-closure-runtime",
        ),
    )


__all__ = ["run_evidence_lifecycle_closure_runtime"]
