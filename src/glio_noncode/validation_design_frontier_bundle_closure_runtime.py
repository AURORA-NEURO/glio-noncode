"""Orchestrated runtime for the D13 validation-design closure handoff."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_boundary import (
    validate_validation_design_closure_boundary,
)
from .validation_design_frontier_bundle_closure_certification import (
    certify_validation_design_closure,
)
from .validation_design_frontier_bundle_closure_contracts import (
    ValidationDesignClosureReplay,
    ValidationDesignClosureRuntimeReport,
    ValidationDesignClosureRuntimeStage,
    ValidationDesignClosureState,
)
from .validation_design_frontier_bundle_closure_indexes import (
    audit_validation_design_closure_indexes,
    build_validation_design_closure_indexes,
)
from .validation_design_frontier_bundle_closure_observability import (
    audit_validation_design_closure_observability,
    build_validation_design_closure_observability,
)
from .validation_design_frontier_bundle_closure_reconciliation import (
    reconcile_validation_design_closure,
)
from .validation_design_frontier_bundle_closure_summary import (
    audit_validation_design_closure_summary,
    build_validation_design_closure_summary,
)
from .validation_design_frontier_bundle_closure_support import bundle_count_map
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle
from .validation_design_frontier_offline_bundle import build_validation_design_offline_bundle


def _source_runtime(run_id: str) -> Any:
    from .validation_design_frontier_public_data import default_validation_design_frontier_fixture
    from .validation_design_frontier_runtime import run_validation_design_runtime

    return run_validation_design_runtime(
        default_validation_design_frontier_fixture(), run_id=run_id
    )


def _stage(
    stage_id: str,
    ordinal: int,
    state: ValidationDesignClosureState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> ValidationDesignClosureRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(
            input_value, prefix="validation-design-closure-runtime-input"
        ),
        "output_address": content_hash(
            output_value, prefix="validation-design-closure-runtime-output"
        ),
        "detail": detail,
    }
    return ValidationDesignClosureRuntimeStage(
        **body, content_address=content_hash(body, prefix="validation-design-closure-runtime-stage")
    )


def _replay(bundle: ValidationDesignBundle, run_id: str) -> ValidationDesignClosureReplay:
    source_runtime = _source_runtime(run_id)
    first = build_validation_design_offline_bundle(
        runtime=source_runtime, bundle_id=bundle.bundle_id, run_id=run_id
    )
    second = build_validation_design_offline_bundle(
        runtime=source_runtime, bundle_id=bundle.bundle_id, run_id=run_id
    )
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "expected_address": bundle.content_address,
        "deterministic": first.content_address == second.content_address,
        "accepted": first.content_address == second.content_address == bundle.content_address,
    }
    return ValidationDesignClosureReplay(
        **body, content_address=content_hash(body, prefix="validation-design-closure-replay")
    )


def run_validation_design_closure_runtime(
    *,
    bundle_id: str = "validation-design-public-bundle",
    run_id: str = "validation-design-closure-runtime",
) -> ValidationDesignClosureRuntimeReport:
    """Materialize, inspect, certify, observe, replay, and finalize D13 closure."""

    source_runtime = _source_runtime(run_id)
    bundle = build_validation_design_offline_bundle(
        runtime=source_runtime, bundle_id=bundle_id, run_id=run_id
    )
    stages: list[ValidationDesignClosureRuntimeStage] = []

    def add(stage_id: str, value: Any, detail: str, accepted: bool = True) -> None:
        ordinal = len(stages) + 1
        state = (
            ValidationDesignClosureState.READY if accepted else ValidationDesignClosureState.BLOCKED
        )
        previous = bundle.content_address if not stages else stages[-1].output_address
        stages.append(_stage(stage_id, ordinal, state, previous, value, detail))

    add(
        "bundle-materialized",
        bundle.to_dict(include_payloads=False),
        "materialize the original 27-artifact public bundle",
        bundle.ready,
    )
    boundary = validate_validation_design_closure_boundary(bundle)
    add(
        "boundary-validated",
        boundary.to_dict(),
        "validate paths, JSON payloads, and public aggregate keys",
        boundary.accepted,
    )
    indexes = build_validation_design_closure_indexes(bundle)
    add(
        "indexes-built",
        indexes.to_dict(),
        "build address-only indexes across every closure resource",
        indexes.accepted,
    )
    index_audit = audit_validation_design_closure_indexes(bundle, indexes)
    add(
        "indexes-audited",
        index_audit.to_dict(),
        "audit index counts, ordinals, addresses, and conservation",
        index_audit.accepted,
    )
    reconciliation = reconcile_validation_design_closure(bundle)
    add(
        "joins-reconciled",
        reconciliation.to_dict(),
        "reconcile fixture, evaluation, runtime, and release joins",
        reconciliation.accepted,
    )
    summary = build_validation_design_closure_summary(bundle)
    add(
        "summary-built",
        summary.to_dict(),
        "build counters, operation summaries, state partitions, and plane rows",
        summary.accepted,
    )
    summary_audit = audit_validation_design_closure_summary(bundle, summary)
    add(
        "summary-audited",
        summary_audit.to_dict(),
        "audit summary partitions and source counters",
        summary_audit.accepted,
    )
    certification = certify_validation_design_closure(
        bundle,
        indexes=indexes,
        index_audit=index_audit,
        reconciliation=reconciliation,
        summary=summary,
        summary_audit=summary_audit,
    )
    add(
        "certification-completed",
        certification.to_dict(),
        "run eight certification domains with 48 evidence-linked checks",
        certification.accepted,
    )
    observability = build_validation_design_closure_observability(bundle)
    add(
        "observability-built",
        observability.to_dict(),
        "emit two addressed events per runtime stage and 18 metrics",
        observability.accepted,
    )
    observability_checks = audit_validation_design_closure_observability(bundle, observability)
    observability_accepted = all(item.passed for item in observability_checks)
    add(
        "observability-audited",
        {
            "checks": [item.to_dict() for item in observability_checks],
            "accepted": observability_accepted,
        },
        "audit event sequencing, stage coverage, and metric inventory",
        observability_accepted,
    )
    replay = _replay(bundle, run_id)
    add(
        "replay-verified",
        replay.to_dict(),
        "replay exact bundle materialization and compare content addresses",
        replay.accepted,
    )
    accepted = (
        all(item.state is ValidationDesignClosureState.READY for item in stages)
        and bundle.ready
        and boundary.accepted
        and index_audit.accepted
        and reconciliation.accepted
        and summary_audit.accepted
        and certification.accepted
        and observability_accepted
        and replay.accepted
    )
    state = ValidationDesignClosureState.READY if accepted else ValidationDesignClosureState.BLOCKED
    add(
        "runtime-finalized",
        {"state": state.value, "accepted": accepted, "counts": bundle_count_map(bundle)},
        "finalize the closure runtime receipt",
        accepted,
    )
    body = {
        "run_id": run_id,
        "state": state,
        "stages": tuple(stages),
        "bundle": bundle,
        "boundary": boundary,
        "indexes": indexes,
        "index_audit": index_audit,
        "reconciliation": reconciliation,
        "summary": summary,
        "summary_audit": summary_audit,
        "certification": certification,
        "observability": observability,
        "replay": replay,
        "accepted": accepted,
    }
    return ValidationDesignClosureRuntimeReport(
        **body, content_address=content_hash(body, prefix="validation-design-closure-runtime")
    )


__all__ = ["run_validation_design_closure_runtime"]
