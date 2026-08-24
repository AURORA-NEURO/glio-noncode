"""Ordered twelve-stage execution wrapper for the architecture program."""

from __future__ import annotations

import json
from typing import Any

from .program_runtime import run_architecture_program
from .program_runtime_contracts import (
    ArchitectureProgramSpec,
    ProgramRuntime,
    ProgramRuntimeStage,
    ProgramRuntimeState,
    addressed,
)
from .program_runtime_quality import run_program_runtime_quality_gate

PROGRAM_RUNTIME_STAGE_COUNT = 12
PROGRAM_RUNTIME_STAGE_IDS = (
    "catalog-loaded",
    "specifications-resolved",
    "fixtures-resolved",
    "domain-runtimes-executed",
    "receipts-normalized",
    "domain-acceptance-closed",
    "public-boundary-closed",
    "reconciliation-closed",
    "report-closed",
    "quality-closed",
    "query-surface-closed",
    "runtime-finalized",
)


def _stage(
    stage_id: str,
    ordinal: int,
    state: ProgramRuntimeState,
    predecessor: Any,
    output: Any,
    detail: str,
) -> ProgramRuntimeStage:
    predecessor_address = (
        predecessor
        if isinstance(predecessor, str) and ":" in predecessor
        else addressed(predecessor, "architecture-program-stage-input")
    )
    output_address = (
        output
        if isinstance(output, str) and ":" in output
        else addressed(output, "architecture-program-stage-output")
    )
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": state,
        "predecessor_address": predecessor_address,
        "output_address": output_address,
        "detail": detail,
    }
    return ProgramRuntimeStage(
        **body,
        content_address=addressed(body, "architecture-program-stage"),
    )


def run_program_runtime(
    specs: tuple[ArchitectureProgramSpec, ...] | None = None,
    *,
    run_id: str | None = None,
) -> ProgramRuntime:
    """Execute, quality-gate, and finalize all sixteen architecture runtimes."""

    report = run_architecture_program(specs)
    quality = run_program_runtime_quality_gate(report)
    stages: list[ProgramRuntimeStage] = []

    def add(state: ProgramRuntimeState, output: Any, detail: str) -> None:
        ordinal = len(stages) + 1
        predecessor = stages[-1].content_address if stages else ""
        stages.append(
            _stage(
                PROGRAM_RUNTIME_STAGE_IDS[ordinal - 1],
                ordinal,
                state,
                predecessor,
                output,
                detail,
            )
        )

    accepted = ProgramRuntimeState.ACCEPTED
    review = ProgramRuntimeState.REVIEW
    add(accepted, report.specs, "load the ordered sixteen-domain program specification catalog")
    add(
        accepted if all(":" in item.content_address for item in report.specs) else review,
        {"specifications": len(report.specs)},
        "resolve and address every canonical fixture/runtime specification",
    )
    add(
        accepted
        if all(item.fixture_resolution.startswith("resolved") for item in report.receipts)
        else review,
        {"resolved": sum(item.fixture_resolution.startswith("resolved") for item in report.receipts)},
        "resolve all fixture factories before execution",
    )
    add(
        accepted
        if all(item.runtime_resolution.startswith("resolved") for item in report.receipts)
        else review,
        {"resolved": sum(item.runtime_resolution.startswith("resolved") for item in report.receipts)},
        "execute every canonical domain runtime",
    )
    add(
        accepted if all(":" in item.content_address for item in report.receipts) else review,
        {"receipts": len(report.receipts)},
        "normalize heterogeneous outputs into addressed public receipts",
    )
    add(
        accepted if all(item.accepted for item in report.receipts) else review,
        {"accepted": sum(item.accepted for item in report.receipts), "total": len(report.receipts)},
        "close the acceptance state for every domain runtime",
    )
    add(
        accepted
        if all("private_projection_key" not in item.issue_codes for item in report.receipts)
        else review,
        {"public_boundary": all("private_projection_key" not in item.issue_codes for item in report.receipts)},
        "verify that every runtime projection remains public aggregate data",
    )
    add(
        accepted if report.failed_checks == 0 else review,
        {"passed": report.passed_checks, "total": len(report.checks)},
        "reconcile domain checks with program-wide checks",
    )
    add(
        accepted if report.accepted else review,
        report.content_address,
        "close the complete sixteen-domain program report",
    )
    add(
        accepted if quality.accepted else review,
        quality.content_address,
        "close the independent program quality gate",
    )
    add(
        accepted,
        {"domains": len(report.receipts), "receipts": len(report.receipts)},
        "close filtering, matrix, and export query projections",
    )
    final_state = (
        accepted
        if report.accepted
        and quality.accepted
        and all(item.state is accepted for item in stages)
        else review
    )
    add(
        final_state,
        {"state": final_state.value, "stage_count": len(stages)},
        "finalize the addressed architecture program runtime",
    )
    body = {
        "run_id": run_id or "architecture-program-runtime",
        "report": report,
        "quality": quality,
        "stages": tuple(stages),
        "state": final_state,
    }
    return ProgramRuntime(
        **body,
        content_address=addressed(body, "architecture-program-runtime"),
    )


def architecture_program_runtime_json(runtime: ProgramRuntime) -> str:
    """Serialize a complete program runtime as stable indented JSON."""

    return json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n"


__all__ = [
    "PROGRAM_RUNTIME_STAGE_COUNT",
    "PROGRAM_RUNTIME_STAGE_IDS",
    "architecture_program_runtime_json",
    "run_program_runtime",
]
