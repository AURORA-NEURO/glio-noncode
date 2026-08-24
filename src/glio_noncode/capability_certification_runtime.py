"""Ordered runtime for live capability catalog certification."""

from __future__ import annotations

from typing import Any

from .capability_certification import certify_capability_catalog
from .capability_certification_contracts import (
    CapabilityCertificationRuntime,
    CapabilityCertificationStage,
    CapabilityCertificationState,
    addressed,
)
from .capability_certification_quality import run_capability_certification_quality_gate
from .capability_registry import CapabilityRegistry

RUNTIME_STAGE_COUNT = 12


def _stage(
    stage_id: str,
    ordinal: int,
    state: CapabilityCertificationState,
    predecessor: Any,
    output: Any,
    detail: str,
) -> CapabilityCertificationStage:
    predecessor_address = predecessor if isinstance(predecessor, str) else addressed(predecessor, "capability-certification-stage-input")
    output_address = output if isinstance(output, str) else addressed(output, "capability-certification-stage-output")
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "predecessor_address": predecessor_address,
        "output_address": output_address,
        "detail": detail,
    }
    return CapabilityCertificationStage(**body, content_address=addressed(body, "capability-certification-stage"))


def run_capability_certification(
    *,
    run_id: str | None = None,
    registry: CapabilityRegistry | None = None,
) -> CapabilityCertificationRuntime:
    """Execute all certification and quality stages in dependency order."""

    report = certify_capability_catalog(registry)
    stages: list[CapabilityCertificationStage] = []
    stages.append(_stage("catalog-loaded", 1, CapabilityCertificationState.ACCEPTED, "", report.catalog_address, "load and validate the complete capability catalog"))
    stages.append(_stage("catalog-addressed", 2, CapabilityCertificationState.ACCEPTED, stages[-1].content_address, report.catalog_address, "close the catalog content address"))
    stages.append(_stage("implementation-references-resolved", 3, CapabilityCertificationState.ACCEPTED if all(item.implementation_resolved == item.implementation_count for item in report.certificates) else CapabilityCertificationState.REVIEW, stages[-1].content_address, {"resolved": sum(item.implementation_resolved for item in report.certificates), "total": sum(item.implementation_count for item in report.certificates)}, "resolve every declared implementation reference"))
    stages.append(_stage("test-references-resolved", 4, CapabilityCertificationState.ACCEPTED if all(item.test_resolved == item.test_count for item in report.certificates) else CapabilityCertificationState.REVIEW, stages[-1].content_address, {"resolved": sum(item.test_resolved for item in report.certificates), "total": sum(item.test_count for item in report.certificates)}, "resolve every declared test reference"))
    stages.append(_stage("row-certificates-closed", 5, CapabilityCertificationState.ACCEPTED if all(item.state is CapabilityCertificationState.ACCEPTED for item in report.certificates) else CapabilityCertificationState.REVIEW, stages[-1].content_address, {"capabilities": report.capability_count, "failed_checks": sum(item.failed_checks for item in report.certificates)}, "close the ten-check row certification plane"))
    stages.append(_stage("domain-denominator-closed", 6, CapabilityCertificationState.ACCEPTED if len(report.domain_summaries) == 16 and all(item.capability_count == 16 for item in report.domain_summaries) else CapabilityCertificationState.REVIEW, stages[-1].content_address, {"domains": len(report.domain_summaries), "rows": {item.domain_id: item.capability_count for item in report.domain_summaries}}, "close sixteen domains and sixteen ordered rows per domain"))
    stages.append(_stage("mvp-denominator-closed", 7, CapabilityCertificationState.ACCEPTED if sum(item.mvp_count for item in report.domain_summaries) == 64 else CapabilityCertificationState.REVIEW, stages[-1].content_address, {"mvp_count": sum(item.mvp_count for item in report.domain_summaries)}, "close the 64-row MVP denominator"))
    stages.append(_stage("global-checks-closed", 8, CapabilityCertificationState.ACCEPTED if all(item.passed for item in report.checks) else CapabilityCertificationState.REVIEW, stages[-1].content_address, {"check_count": len(report.checks), "failed_checks": sum(not item.passed for item in report.checks)}, "close catalog-wide identity and boundary checks"))
    stages.append(_stage("quality-gate-closed", 9, CapabilityCertificationState.ACCEPTED if report.accepted else CapabilityCertificationState.REVIEW, stages[-1].content_address, report.content_address, "close the live certification report"))
    quality = run_capability_certification_quality_gate(report)
    stages.append(_stage("quality-evidence-closed", 10, CapabilityCertificationState.ACCEPTED if quality.accepted else CapabilityCertificationState.REVIEW, stages[-1].content_address, quality.content_address, "close the independent quality gate"))
    stages.append(_stage("query-surface-closed", 11, CapabilityCertificationState.ACCEPTED, stages[-1].content_address, {"domain_summaries": len(report.domain_summaries), "certificates": report.capability_count}, "close public filtering and dashboard projections"))
    final_state = CapabilityCertificationState.ACCEPTED if report.accepted and quality.accepted and all(item.state is CapabilityCertificationState.ACCEPTED for item in stages) else CapabilityCertificationState.REVIEW
    stages.append(_stage("runtime-finalized", 12, final_state, stages[-1].content_address, {"state": final_state.value, "stage_count": len(stages)}, "finalize the addressed certification runtime"))
    body = {
        "run_id": run_id or report.report_id,
        "report": report,
        "quality": quality,
        "stages": tuple(stages),
        "state": final_state,
    }
    return CapabilityCertificationRuntime(**body, content_address=addressed(body, "capability-certification-runtime"))


def capability_certification_runtime_json(runtime: CapabilityCertificationRuntime) -> str:
    """Return canonical JSON for a certification runtime."""

    import json

    return json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n"


__all__ = [
    "RUNTIME_STAGE_COUNT",
    "capability_certification_runtime_json",
    "run_capability_certification",
]
