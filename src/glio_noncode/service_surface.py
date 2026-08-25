"""Public service projections for the certified local product surfaces.

The service layer is intentionally assembled from the existing deterministic
certification and architecture runtimes.  It provides one cached snapshot for
HTTP callers and one self-contained closure for offline inspection without
exposing case payloads or mutable runtime internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_certification import (
    capability_certification_domain_matrix,
    capability_certification_percent,
    certify_capability_catalog,
    query_capability_certification,
)
from .capability_certification_contracts import (
    CapabilityCertificationReport,
    CapabilityCertificationState,
)
from .module_fabric_support import contains_private_key
from .program_runtime import (
    architecture_program_domain_matrix,
    architecture_program_percent,
    query_architecture_program,
)
from .program_runtime_contracts import ProgramRuntime
from .program_runtime_diff import build_program_runtime_diff
from .program_runtime_execution import run_program_runtime
from .program_runtime_operational import (
    ProgramOperationalTrace,
    build_program_operational_trace,
)
from .program_release_closure_bundle import build_program_release_snapshot
from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
    PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
    ProgramReleaseSnapshot,
)
from .program_release_closure_query import query_program_release_closure
from .serialization import content_hash

SERVICE_NAME = "glio-noncode"
SERVICE_API_VERSION = "v1"
SERVICE_SURFACE_VERSION = "service-surface-v1"


@dataclass(frozen=True, slots=True)
class ServiceSurfaceSnapshot:
    """Cached, public-ready view of the product's certified runtime surfaces."""

    capability_report: CapabilityCertificationReport
    program_runtime: ProgramRuntime
    operational_trace: ProgramOperationalTrace
    program_release: ProgramReleaseSnapshot
    content_address: str

    @property
    def accepted(self) -> bool:
        """Return whether every published service surface is accepted."""

        return (
            self.capability_report.accepted
            and self.program_runtime.accepted
            and self.operational_trace.accepted
            and self.program_release.accepted
        )


def _capability_status(report: CapabilityCertificationReport) -> dict[str, Any]:
    accepted_count = sum(item.state is CapabilityCertificationState.ACCEPTED for item in report.certificates)
    return {
        "report_address": report.content_address,
        "catalog_address": report.catalog_address,
        "state": report.state.value,
        "accepted": report.accepted,
        "capability_count": report.capability_count,
        "accepted_count": accepted_count,
        "certification_percent": capability_certification_percent(report),
        "domain_count": len(report.domain_summaries),
        "total_checks": report.total_checks,
        "passed_checks": report.passed_checks,
        "failed_checks": report.failed_checks,
        "domains": list(capability_certification_domain_matrix(report)),
    }


def _program_status(runtime: ProgramRuntime) -> dict[str, Any]:
    report = runtime.report
    return {
        "runtime_address": runtime.content_address,
        "run_id": runtime.run_id,
        "state": runtime.state.value,
        "accepted": runtime.accepted,
        "program_percent": architecture_program_percent(report),
        "domain_count": len(report.receipts),
        "stage_count": len(runtime.stages),
        "report_check_count": len(report.checks),
        "report_passed_checks": report.passed_checks,
        "report_failed_checks": report.failed_checks,
        "quality_check_count": len(runtime.quality.checks),
        "quality_passed_checks": runtime.quality.passed_checks,
        "quality_failed_checks": runtime.quality.failed_checks,
        "domains": list(architecture_program_domain_matrix(report)),
    }


def _operational_status(trace: ProgramOperationalTrace) -> dict[str, Any]:
    return {
        "trace_address": trace.content_address,
        "run_id": trace.run_id,
        "accepted": trace.accepted,
        "stage_count": len(trace.stages),
        "artifact_count": len(trace.artifacts),
        "check_count": len(trace.checks),
        "passed_checks": trace.passed_checks,
        "failed_checks": trace.failed_checks,
        "counters": trace.counter_map,
    }


def _program_release_status(snapshot: ProgramReleaseSnapshot) -> dict[str, Any]:
    """Return the compact D01-D16 status used by service clients.

    The service snapshot intentionally carries the immutable aggregate rather
    than a second full runtime report.  Detailed closure planes remain
    available through the dedicated program-release routes, while this status
    makes the top-level service health answer complete and inexpensive to
    consume.
    """

    return {
        "snapshot_address": snapshot.content_address,
        "bundle_id": snapshot.bundle_id,
        "run_id": snapshot.run_id,
        "accepted": snapshot.accepted,
        "domain_count": len(snapshot.domains),
        "artifact_count": len(snapshot.artifacts),
        "dependency_count": len(snapshot.dependencies),
        "gate_count": len(snapshot.gates),
        "accepted_domain_count": sum(item.accepted for item in snapshot.domains),
        "passed_gate_count": sum(item.passed for item in snapshot.gates),
        "domain_percent": round(100.0 * len(snapshot.domains) / PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT, 2),
        "gate_percent": round(100.0 * sum(item.passed for item in snapshot.gates) / PROGRAM_RELEASE_CLOSURE_GATE_COUNT, 2),
        "boundary": snapshot.boundary,
    }


def _status_without_address(snapshot: ServiceSurfaceSnapshot) -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "api_version": SERVICE_API_VERSION,
        "surface_version": SERVICE_SURFACE_VERSION,
        "accepted": snapshot.accepted,
        "capability_certification": _capability_status(snapshot.capability_report),
        "architecture_program": _program_status(snapshot.program_runtime),
        "operational": _operational_status(snapshot.operational_trace),
        "program_release": _program_release_status(snapshot.program_release),
    }


def build_service_surface_snapshot() -> ServiceSurfaceSnapshot:
    """Execute and address the complete public service surface."""

    capability_report = certify_capability_catalog()
    program_runtime = run_program_runtime()
    operational_trace = build_program_operational_trace(program_runtime)
    program_release = build_program_release_snapshot()
    body = {
        "capability_report": capability_report.content_address,
        "program_runtime": program_runtime.content_address,
        "operational_trace": operational_trace.content_address,
        "program_release": program_release.content_address,
        "accepted": capability_report.accepted and program_runtime.accepted and operational_trace.accepted and program_release.accepted,
    }
    return ServiceSurfaceSnapshot(
        capability_report=capability_report,
        program_runtime=program_runtime,
        operational_trace=operational_trace,
        program_release=program_release,
        content_address=content_hash(body, prefix="service-surface"),
    )


def service_surface_status(snapshot: ServiceSurfaceSnapshot) -> dict[str, Any]:
    """Return the compact status document used by health and dashboard clients."""

    status = _status_without_address(snapshot)
    status["content_address"] = snapshot.content_address
    status["public_boundary"] = {
        "safe": not contains_private_key(status),
        "projection": "public",
    }
    return status


def service_capability_projection(
    snapshot: ServiceSurfaceSnapshot,
    *,
    capability_id: str | None = None,
    domain_id: str | None = None,
    mvp_only: bool = False,
    state: CapabilityCertificationState | str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Filter certified capabilities into a stable HTTP/CLI projection."""

    selected_state = CapabilityCertificationState(state) if isinstance(state, str) else state
    rows = query_capability_certification(
        snapshot.capability_report,
        capability_id=capability_id,
        domain_id=domain_id,
        mvp_only=mvp_only,
        state=selected_state,
        text=text,
    )
    return {
        "service": SERVICE_NAME,
        "report_address": snapshot.capability_report.content_address,
        "certification_percent": capability_certification_percent(snapshot.capability_report),
        "count": len(rows),
        "rows": [item.to_dict() for item in rows],
    }


def service_program_projection(
    snapshot: ServiceSurfaceSnapshot,
    *,
    domain_id: str | None = None,
    accepted_only: bool = False,
    text: str | None = None,
) -> dict[str, Any]:
    """Filter architecture receipts into a stable HTTP/CLI projection."""

    rows = query_architecture_program(
        snapshot.program_runtime.report,
        domain_id=domain_id,
        accepted_only=accepted_only,
        text=text,
    )
    return {
        "service": SERVICE_NAME,
        "runtime_address": snapshot.program_runtime.content_address,
        "program_percent": architecture_program_percent(snapshot.program_runtime.report),
        "count": len(rows),
        "rows": [item.to_dict() for item in rows],
    }


def service_operational_projection(snapshot: ServiceSurfaceSnapshot) -> dict[str, Any]:
    """Return the complete accepted operational handoff trace."""

    return snapshot.operational_trace.to_dict()


def service_program_release_projection(
    snapshot: ServiceSurfaceSnapshot,
    *,
    resource: str = "domains",
    domain_id: str | None = None,
    gate_type: str | None = None,
    state: str | None = None,
    relation: str | None = None,
    accepted_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Query the cached D01-D16 aggregate from the service surface.

    This projection deliberately delegates filtering and bounds to the
    closure query contract, so HTTP, CLI, and offline consumers receive the
    same ordering, pagination metadata, and content-addressed result.
    """

    result = query_program_release_closure(
        snapshot.program_release,
        resource=resource,
        domain_id=domain_id,
        gate_type=gate_type,
        state=state,
        relation=relation,
        accepted_only=accepted_only,
        text=text,
        offset=offset,
        limit=limit,
    )
    return {
        "service": SERVICE_NAME,
        "snapshot_address": snapshot.program_release.content_address,
        "release_status": _program_release_status(snapshot.program_release),
        **result.to_dict(),
        "has_more": result.offset + len(result.items) < result.total,
    }


def service_diff_projection(snapshot: ServiceSurfaceSnapshot, control: str = "none") -> dict[str, Any]:
    """Compare the current program surface with one named negative control."""

    diff = build_program_runtime_diff(control)
    return {
        "service": SERVICE_NAME,
        "baseline_address": snapshot.program_runtime.content_address,
        "control": control,
        **diff.to_dict(),
    }


def build_service_surface_closure(snapshot: ServiceSurfaceSnapshot | None = None) -> dict[str, Any]:
    """Build a self-contained offline closure for release review and archival."""

    selected = snapshot or build_service_surface_snapshot()
    closure = {
        "accepted": selected.accepted,
        "status": service_surface_status(selected),
        "capability_certification": selected.capability_report.to_dict(),
        "architecture_program_runtime": selected.program_runtime.to_dict(),
        "operational_trace": selected.operational_trace.to_dict(),
        "program_release_snapshot": selected.program_release.to_dict(),
        "queries": {
            "capabilities": service_capability_projection(selected),
            "mvp_capabilities": service_capability_projection(selected, mvp_only=True),
            "architecture_program": service_program_projection(selected),
            "accepted_architecture_program": service_program_projection(selected, accepted_only=True),
            "program_release_domains": service_program_release_projection(selected),
            "accepted_program_release_gates": service_program_release_projection(
                selected,
                resource="gates",
                accepted_only=True,
            ),
        },
    }
    if contains_private_key(closure):
        raise ValueError("service surface closure contains a private projection key")
    closure["content_address"] = content_hash(closure, prefix="service-surface-closure")
    return closure


__all__ = [
    "SERVICE_API_VERSION",
    "SERVICE_NAME",
    "SERVICE_SURFACE_VERSION",
    "ServiceSurfaceSnapshot",
    "build_service_surface_closure",
    "build_service_surface_snapshot",
    "service_capability_projection",
    "service_diff_projection",
    "service_operational_projection",
    "service_program_release_projection",
    "service_program_projection",
    "service_surface_status",
]
