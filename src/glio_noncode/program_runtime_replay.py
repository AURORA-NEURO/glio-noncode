"""Deterministic replay and negative controls for the program runtime."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .program_runtime import default_architecture_program_specs, run_architecture_program
from .program_runtime_contracts import (
    ArchitectureProgramSpec,
    ProgramRuntimeState,
    addressed,
)
from .program_runtime_execution import run_program_runtime
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ProgramRuntimeReplayReport:
    """Address comparison for two independent complete program runs."""

    first_report_address: str
    second_report_address: str
    first_runtime_address: str
    second_runtime_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeFailureProbe:
    """One controlled missing-reference probe."""

    probe_id: str
    domain_id: str
    removed_surface: str
    observed_state: ProgramRuntimeState
    failed_check_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeFailureReport:
    """Collection of negative controls for resolution and execution boundaries."""

    probes: tuple[ProgramRuntimeFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "probes": [item.to_dict() for item in self.probes],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_architecture_program() -> ProgramRuntimeReplayReport:
    """Run the program twice and compare report and runtime addresses."""

    first = run_program_runtime()
    second = run_program_runtime()
    body = {
        "first_report_address": first.report.content_address,
        "second_report_address": second.report.content_address,
        "first_runtime_address": first.content_address,
        "second_runtime_address": second.content_address,
        "accepted": first.report.content_address == second.report.content_address
        and first.content_address == second.content_address,
    }
    return ProgramRuntimeReplayReport(**body, content_address=addressed(body, "architecture-program-replay"))


def _mutated_specs(domain_id: str, surface: str) -> tuple[ArchitectureProgramSpec, ...]:
    specs = default_architecture_program_specs()
    mutated: list[ArchitectureProgramSpec] = []
    for spec in specs:
        if spec.domain_id != domain_id:
            mutated.append(spec)
            continue
        field = "fixture_reference" if surface == "fixture" else "runtime_reference"
        mutated.append(
            replace(
                spec,
                **{
                    field: f"glio_noncode.missing_program_surface_{domain_id.lower()}"
                },
            )
        )
    return tuple(mutated)


def run_program_runtime_failure_injections() -> ProgramRuntimeFailureReport:
    """Prove missing fixture and runtime references remain visible as review."""

    probes: list[ProgramRuntimeFailureProbe] = []
    for probe_id, domain_id, surface in (
        ("missing-fixture-reference", "D01", "fixture"),
        ("missing-runtime-reference", "D16", "runtime"),
    ):
        report = run_architecture_program(_mutated_specs(domain_id, surface))
        receipt = next(item for item in report.receipts if item.domain_id == domain_id)
        failed_check_ids = tuple(
            item.check_id for item in report.checks if item.domain_id == domain_id and not item.passed
        )
        expected_issue = f"{surface}_reference_failed"
        passed = (
            report.state is ProgramRuntimeState.REVIEW
            and not receipt.accepted
            and expected_issue in receipt.issue_codes
            and bool(failed_check_ids)
        )
        body = {
            "probe_id": probe_id,
            "domain_id": domain_id,
            "removed_surface": surface,
            "observed_state": report.state,
            "failed_check_ids": failed_check_ids,
            "issue_codes": receipt.issue_codes,
            "passed": passed,
        }
        probes.append(
            ProgramRuntimeFailureProbe(
                **body,
                content_address=addressed(body, "architecture-program-failure-probe"),
            )
        )
    body = {"probes": tuple(probes), "accepted": all(item.passed for item in probes)}
    return ProgramRuntimeFailureReport(
        **body,
        content_address=addressed(body, "architecture-program-failures"),
    )


__all__ = [
    "ProgramRuntimeFailureProbe",
    "ProgramRuntimeFailureReport",
    "ProgramRuntimeReplayReport",
    "replay_architecture_program",
    "run_program_runtime_failure_injections",
]
