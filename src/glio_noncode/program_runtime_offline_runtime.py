"""Staged runtime that verifies a program handoff without producer state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .program_runtime_offline_audit import audit_program_runtime_offline_bundle
from .program_runtime_offline_boundary import audit_program_runtime_offline_boundary
from .program_runtime_offline_bundle import build_program_runtime_offline_bundle
from .program_runtime_offline_certification import certify_program_runtime_offline_bundle
from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_HANDOFF_STAGE_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_VERSION,
    ProgramRuntimeOfflineBundle,
    ProgramRuntimeOfflineBundleState,
    ProgramRuntimeOfflineReplay,
    ProgramRuntimeOfflineRuntimeStage,
)
from .program_runtime_offline_indexes import (
    audit_program_runtime_offline_indexes,
    build_program_runtime_offline_indexes,
)
from .program_runtime_offline_reconciliation import reconcile_program_runtime_offline_bundle
from .program_runtime_offline_summary import (
    audit_program_runtime_offline_summary,
    build_program_runtime_offline_summary,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineObservability:
    bundle_id: str
    run_id: str
    artifact_count: int
    stage_count: int
    certification_check_count: int
    completed: bool
    addressed: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineRuntimeReport:
    run_id: str
    state: ProgramRuntimeOfflineBundleState
    stages: tuple[ProgramRuntimeOfflineRuntimeStage, ...]
    bundle: ProgramRuntimeOfflineBundle
    observability: ProgramRuntimeOfflineObservability
    replay: ProgramRuntimeOfflineReplay
    audit: Any
    boundary: dict[str, Any]
    indexes: Any
    index_audit: Any
    reconciliation: Any
    summary: Any
    summary_audit: Any
    certification: Any
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PROGRAM_RUNTIME_OFFLINE_RUNTIME_VERSION,
            "run_id": self.run_id,
            "state": self.state,
            "stages": [item.to_dict() for item in self.stages],
            "bundle": self.bundle.to_dict(include_payloads=False),
            "observability": self.observability.to_dict(),
            "replay": self.replay.to_dict(),
            "audit": self.audit.to_dict(),
            "boundary": self.boundary,
            "indexes": self.indexes.to_dict(),
            "index_audit": self.index_audit.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "summary": self.summary.to_dict(),
            "summary_audit": self.summary_audit.to_dict(),
            "certification": self.certification.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str,
    ordinal: int,
    state: ProgramRuntimeOfflineBundleState,
    input_value: Any,
    output_value: Any,
    detail: str,
) -> ProgramRuntimeOfflineRuntimeStage:
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "input_address": content_hash(input_value, prefix="program-runtime-offline-input"),
        "output_address": content_hash(output_value, prefix="program-runtime-offline-output"),
        "detail": detail,
    }
    return ProgramRuntimeOfflineRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-stage"),
    )


def _state(accepted: bool) -> ProgramRuntimeOfflineBundleState:
    return (
        ProgramRuntimeOfflineBundleState.READY
        if accepted
        else ProgramRuntimeOfflineBundleState.BLOCKED
    )


def _replay(bundle: ProgramRuntimeOfflineBundle) -> ProgramRuntimeOfflineReplay:
    first = build_program_runtime_offline_bundle(bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    second = build_program_runtime_offline_bundle(bundle_id=bundle.bundle_id, run_id=bundle.run_id)
    deterministic = first.content_address == second.content_address == bundle.content_address
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "expected_address": bundle.content_address,
        "deterministic": deterministic,
        "accepted": deterministic,
    }
    return ProgramRuntimeOfflineReplay(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-replay"),
    )


def run_program_runtime_offline_runtime(
    *,
    bundle_id: str = "architecture-program-public-bundle",
    run_id: str = "architecture-program-offline-runtime",
) -> ProgramRuntimeOfflineRuntimeReport:
    """Materialize, audit, index, reconcile, summarize, certify, and replay."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    bundle = build_program_runtime_offline_bundle(bundle_id=bundle_id, run_id=run_id)
    stages: list[ProgramRuntimeOfflineRuntimeStage] = []
    ready = _state(bundle.ready)
    stages.append(
        _stage(
            "bundle-materialized",
            1,
            ready,
            {},
            bundle.content_address,
            "public aggregate bundle materialized",
        )
    )
    inventory_state = _state(bundle.artifact_count == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT)
    stages.append(
        _stage(
            "artifact-inventory-closed",
            2,
            inventory_state,
            bundle.content_address,
            {"artifact_count": bundle.artifact_count},
            "portable artifact inventory is conserved",
        )
    )
    audit = audit_program_runtime_offline_bundle(bundle)
    audit_state = _state(audit.accepted)
    stages.append(
        _stage(
            "exact-byte-audit",
            3,
            audit_state,
            bundle.content_address,
            audit.to_dict(),
            "artifact bytes, lines, and addresses reconcile",
        )
    )
    boundary = audit_program_runtime_offline_boundary(bundle)
    boundary_state = _state(bool(boundary.get("accepted")))
    stages.append(
        _stage(
            "public-boundary-closed",
            4,
            boundary_state,
            bundle.content_address,
            boundary,
            "recursive public-key and path boundary is closed",
        )
    )
    indexes = build_program_runtime_offline_indexes(bundle)
    index_audit = audit_program_runtime_offline_indexes(bundle, indexes)
    index_state = _state(index_audit.accepted)
    stages.append(
        _stage(
            "address-indexes-closed",
            5,
            index_state,
            bundle.content_address,
            index_audit.to_dict(),
            "address-only query indexes are closed",
        )
    )
    reconciliation = reconcile_program_runtime_offline_bundle(bundle)
    reconciliation_state = _state(reconciliation.accepted)
    stages.append(
        _stage(
            "denominator-reconciled",
            6,
            reconciliation_state,
            bundle.content_address,
            reconciliation.to_dict(),
            "runtime, report, release, and derived rows reconcile",
        )
    )
    summary = build_program_runtime_offline_summary(bundle)
    summary_audit = audit_program_runtime_offline_summary(summary)
    summary_state = _state(summary_audit.accepted)
    stages.append(
        _stage(
            "summary-closed",
            7,
            summary_state,
            bundle.content_address,
            summary_audit.to_dict(),
            "review counters and domain rows are closed",
        )
    )
    certification = certify_program_runtime_offline_bundle(bundle)
    certification_state = _state(certification.accepted)
    stages.append(
        _stage(
            "certification-closed",
            8,
            certification_state,
            bundle.content_address,
            certification.to_dict(),
            "seven independent certification domains are closed",
        )
    )
    observability = ProgramRuntimeOfflineObservability(
        bundle_id=bundle.bundle_id,
        run_id=run_id,
        artifact_count=bundle.artifact_count,
        stage_count=PROGRAM_RUNTIME_OFFLINE_HANDOFF_STAGE_COUNT,
        certification_check_count=certification.check_count,
        completed=True,
        addressed=all(item.content_address for item in stages),
        accepted=bundle.ready
        and audit.accepted
        and boundary_state is ProgramRuntimeOfflineBundleState.READY
        and index_audit.accepted
        and reconciliation.accepted
        and summary_audit.accepted
        and certification.accepted,
        content_address="",
    )
    observability = ProgramRuntimeOfflineObservability(
        **(
            observability.to_dict()
            | {
                "content_address": content_hash(
                    observability.to_dict() | {"content_address": ""},
                    prefix="program-runtime-offline-observability",
                )
            }
        )
    )
    stages.append(
        _stage(
            "observability-closed",
            9,
            _state(observability.accepted),
            bundle.content_address,
            observability.to_dict(),
            "offline stages and certification counters are observable",
        )
    )
    replay = _replay(bundle)
    stages.append(
        _stage(
            "replay-verified",
            10,
            _state(replay.accepted),
            bundle.content_address,
            replay.to_dict(),
            "two independent builds have the same root address",
        )
    )
    final_accepted = (
        bundle.ready
        and audit.accepted
        and bool(boundary.get("accepted"))
        and index_audit.accepted
        and reconciliation.accepted
        and summary_audit.accepted
        and certification.accepted
        and observability.accepted
        and replay.accepted
    )
    stages.append(
        _stage(
            "runtime-finalized",
            11,
            _state(final_accepted),
            bundle.content_address,
            {"accepted": final_accepted, "stage_count": len(stages) + 1},
            "finalize the portable architecture-program verification runtime",
        )
    )
    final_accepted = final_accepted and len(stages) == 11
    final_state = _state(final_accepted)
    body = {
        "run_id": run_id,
        "state": final_state,
        "stages": stages,
        "bundle": bundle,
        "observability": observability,
        "replay": replay,
        "audit": audit,
        "boundary": boundary,
        "indexes": indexes,
        "index_audit": index_audit,
        "reconciliation": reconciliation,
        "summary": summary,
        "summary_audit": summary_audit,
        "certification": certification,
        "accepted": final_accepted,
    }
    return ProgramRuntimeOfflineRuntimeReport(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-runtime"),
    )


def program_runtime_offline_runtime_json(report: ProgramRuntimeOfflineRuntimeReport) -> str:
    import json

    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


__all__ = [
    "ProgramRuntimeOfflineObservability",
    "ProgramRuntimeOfflineRuntimeReport",
    "program_runtime_offline_runtime_json",
    "run_program_runtime_offline_runtime",
]
