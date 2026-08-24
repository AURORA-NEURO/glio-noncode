"""Operational workload and handoff trace for the sixteen-domain program."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .program_runtime import architecture_program_domain_matrix
from .program_runtime_bundle import build_program_release, program_release_payloads
from .program_runtime_contracts import ProgramRuntime
from .program_runtime_execution import (
    PROGRAM_RUNTIME_STAGE_COUNT,
    PROGRAM_RUNTIME_STAGE_IDS,
    run_program_runtime,
)
from .program_runtime_release_contracts import ProgramRelease
from .program_runtime_replay import (
    replay_architecture_program,
    run_program_runtime_failure_injections,
)
from .serialization import content_hash, jsonable

PROGRAM_OPERATIONAL_STAGE_COUNT = PROGRAM_RUNTIME_STAGE_COUNT
PROGRAM_OPERATIONAL_ARTIFACT_COUNT = 11
PROGRAM_OPERATIONAL_CHECK_COUNT = 26

PROGRAM_OPERATIONAL_STAGE_BUDGETS = (
    ("catalog-loaded", 256),
    ("specifications-resolved", 512),
    ("fixtures-resolved", 512),
    ("domain-runtimes-executed", 4096),
    ("receipts-normalized", 1024),
    ("domain-acceptance-closed", 4096),
    ("public-boundary-closed", 2048),
    ("reconciliation-closed", 4096),
    ("report-closed", 4096),
    ("quality-closed", 1024),
    ("query-surface-closed", 1024),
    ("runtime-finalized", 512),
)

PROGRAM_OPERATIONAL_ARTIFACT_BUDGETS = (
    ("program-runtime.json", 250_000),
    ("program-report.json", 200_000),
    ("program-summary.json", 25_000),
    ("program-receipts.csv", 25_000),
    ("program-checks.csv", 75_000),
    ("program-domains.csv", 25_000),
    ("program-report.md", 10_000),
    ("program-replay.json", 10_000),
    ("program-failures.json", 10_000),
    ("program-specifications.json", 20_000),
    ("program-matrix.json", 25_000),
)

_STAGE_BUDGETS = dict(PROGRAM_OPERATIONAL_STAGE_BUDGETS)
_ARTIFACT_BUDGETS = dict(PROGRAM_OPERATIONAL_ARTIFACT_BUDGETS)


@dataclass(frozen=True, slots=True)
class ProgramStageWorkReceipt:
    """One deterministic workload receipt for an ordered program stage."""

    sequence: int
    stage_id: str
    state: str
    input_count: int
    output_address: str
    work_units: int
    budget_units: int
    within_budget: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramArtifactWorkReceipt:
    """Byte, line, and budget evidence for one release artifact."""

    artifact_id: str
    kind: str
    filename: str
    byte_count: int
    line_count: int
    byte_budget: int
    within_budget: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramOperationalCheck:
    """One addressed operational, handoff, or boundary assertion."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramOperationalTrace:
    """Complete stage-to-artifact workload trace for a program handoff."""

    run_id: str
    runtime_address: str
    release_address: str
    stages: tuple[ProgramStageWorkReceipt, ...]
    artifacts: tuple[ProgramArtifactWorkReceipt, ...]
    counters: tuple[tuple[str, int | float], ...]
    checks: tuple[ProgramOperationalCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "runtime_address": self.runtime_address,
            "release_address": self.release_address,
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": len(self.stages),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "artifact_count": len(self.artifacts),
            "counters": dict(self.counters),
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "failed_check_ids": list(self.failed_check_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage_input_count(runtime: ProgramRuntime, stage_id: str) -> int:
    """Return the stable cardinality consumed by one program stage."""

    report = runtime.report
    if stage_id == "catalog-loaded":
        return len(report.specs)
    if stage_id == "specifications-resolved":
        return len(report.specs) * 2
    if stage_id == "fixtures-resolved":
        return len(report.receipts)
    if stage_id == "domain-runtimes-executed":
        return len(report.receipts)
    if stage_id == "receipts-normalized":
        return len(report.receipts)
    if stage_id == "domain-acceptance-closed":
        return len(report.receipts)
    if stage_id == "public-boundary-closed":
        return len(report.receipts)
    if stage_id == "reconciliation-closed":
        return len(report.checks)
    if stage_id == "report-closed":
        return len(report.receipts) + len(report.checks)
    if stage_id == "quality-closed":
        return len(runtime.quality.checks)
    if stage_id == "query-surface-closed":
        return len(architecture_program_domain_matrix(report))
    if stage_id == "runtime-finalized":
        return len(runtime.stages)
    return 0


def _stage_work_units(runtime: ProgramRuntime, stage_id: str) -> int:
    """Calculate workload from closed cardinalities, never elapsed time."""

    report = runtime.report
    if stage_id == "catalog-loaded":
        return len(report.specs) + len(runtime.stages)
    if stage_id == "specifications-resolved":
        return len(report.specs) * 3
    if stage_id == "fixtures-resolved":
        return len(report.receipts) * 3 + sum(
            item.fixture_resolution.startswith("resolved") for item in report.receipts
        )
    if stage_id == "domain-runtimes-executed":
        return sum(item.stage_count for item in report.receipts) + len(report.receipts)
    if stage_id == "receipts-normalized":
        return len(report.receipts) * 3 + sum(
            ":" in item.content_address for item in report.receipts
        )
    if stage_id == "domain-acceptance-closed":
        return len(report.receipts) + len(report.checks)
    if stage_id == "public-boundary-closed":
        return len(report.receipts) * 2 + sum(
            not item.issue_codes for item in report.receipts
        )
    if stage_id == "reconciliation-closed":
        return len(report.checks) + len(runtime.quality.checks)
    if stage_id == "report-closed":
        return len(report.specs) + len(report.receipts) + len(report.checks)
    if stage_id == "quality-closed":
        return len(runtime.quality.checks) * 2
    if stage_id == "query-surface-closed":
        return len(architecture_program_domain_matrix(report)) * 3
    if stage_id == "runtime-finalized":
        return len(runtime.stages) * 2 + 1
    return 0


def _stage_receipts(runtime: ProgramRuntime) -> tuple[ProgramStageWorkReceipt, ...]:
    receipts: list[ProgramStageWorkReceipt] = []
    for stage in runtime.stages:
        stage_id = stage.stage_id
        work_units = _stage_work_units(runtime, stage_id)
        budget_units = _STAGE_BUDGETS.get(stage_id, 0)
        body = {
            "sequence": stage.ordinal,
            "stage_id": stage_id,
            "state": stage.state.value,
            "input_count": _stage_input_count(runtime, stage_id),
            "output_address": stage.output_address,
            "work_units": work_units,
            "budget_units": budget_units,
            "within_budget": 0 < work_units <= budget_units,
        }
        receipts.append(
            ProgramStageWorkReceipt(
                **body,
                content_address=content_hash(body, prefix="program-stage-work"),
            )
        )
    return tuple(receipts)


def _artifact_receipts(release: ProgramRelease) -> tuple[ProgramArtifactWorkReceipt, ...]:
    receipts: list[ProgramArtifactWorkReceipt] = []
    for artifact in release.artifacts:
        byte_budget = _ARTIFACT_BUDGETS.get(artifact.filename, 0)
        body = {
            "artifact_id": artifact.artifact_id,
            "kind": artifact.kind.value,
            "filename": artifact.filename,
            "byte_count": artifact.byte_count,
            "line_count": artifact.line_count,
            "byte_budget": byte_budget,
            "within_budget": 0 < artifact.byte_count <= byte_budget,
        }
        receipts.append(
            ProgramArtifactWorkReceipt(
                **body,
                content_address=content_hash(body, prefix="program-artifact-work"),
            )
        )
    return tuple(receipts)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ProgramOperationalCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramOperationalCheck(
        **body,
        content_address=content_hash(body, prefix="program-operational-check"),
    )


def build_program_operational_trace(
    runtime: ProgramRuntime | None = None,
    release: ProgramRelease | None = None,
) -> ProgramOperationalTrace:
    """Build workload, handoff, and public-boundary evidence for the program."""

    selected_runtime = runtime or run_program_runtime()
    selected_release = release or build_program_release(selected_runtime)
    stages = _stage_receipts(selected_runtime)
    artifacts = _artifact_receipts(selected_release)
    total_stage_work = sum(item.work_units for item in stages)
    total_stage_budget = sum(item.budget_units for item in stages)
    total_artifact_bytes = sum(item.byte_count for item in artifacts)
    total_artifact_budget = sum(item.byte_budget for item in artifacts)
    counters: tuple[tuple[str, int | float], ...] = tuple(
        sorted(
            {
                "stage_count": len(stages),
                "artifact_count": len(artifacts),
                "domain_count": len(selected_runtime.report.receipts),
                "program_check_count": len(selected_runtime.report.checks),
                "quality_check_count": len(selected_runtime.quality.checks),
                "release_check_count": len(selected_release.checks),
                "total_stage_work_units": total_stage_work,
                "total_stage_budget_units": total_stage_budget,
                "stage_utilization_percent": round(
                    100.0 * total_stage_work / max(1, total_stage_budget), 6
                ),
                "total_artifact_bytes": total_artifact_bytes,
                "total_artifact_byte_budget": total_artifact_budget,
                "artifact_utilization_percent": round(
                    100.0 * total_artifact_bytes / max(1, total_artifact_budget), 6
                ),
                "total_artifact_lines": sum(item.line_count for item in artifacts),
            }.items()
        )
    )
    counter_map = dict(counters)
    checks = (
        _check(
            "stage-denominator",
            len(stages) == PROGRAM_OPERATIONAL_STAGE_COUNT,
            len(stages),
            PROGRAM_OPERATIONAL_STAGE_COUNT,
            "all twelve program runtime stages produce workload receipts",
        ),
        _check(
            "stage-sequence",
            tuple(item.sequence for item in stages) == tuple(range(1, 13)),
            tuple(item.sequence for item in stages),
            tuple(range(1, 13)),
            "program stage sequences are contiguous and ordered",
        ),
        _check(
            "stage-identities",
            tuple(item.stage_id for item in stages) == PROGRAM_RUNTIME_STAGE_IDS,
            tuple(item.stage_id for item in stages),
            PROGRAM_RUNTIME_STAGE_IDS,
            "work receipts retain canonical program stage identities",
        ),
        _check(
            "stage-addresses",
            all(item.content_address.startswith("program-stage-work:") for item in stages),
            sum(item.content_address.startswith("program-stage-work:") for item in stages),
            len(stages),
            "every stage workload receipt is content-addressed",
        ),
        _check(
            "predecessor-chain",
            all(
                stage.predecessor_address == ""
                or ":" in stage.predecessor_address
                for stage in selected_runtime.stages
            ),
            sum(
                stage.predecessor_address == ""
                or ":" in stage.predecessor_address
                for stage in selected_runtime.stages
            ),
            len(selected_runtime.stages),
            "every program stage predecessor is empty only at the root or addressed",
        ),
        _check(
            "stage-output-addresses",
            all(":" in item.output_address for item in stages),
            sum(":" in item.output_address for item in stages),
            len(stages),
            "every program stage exposes an addressed output",
        ),
        _check(
            "positive-stage-work",
            all(item.work_units > 0 for item in stages),
            min((item.work_units for item in stages), default=0),
            ">0",
            "every program stage has a deterministic workload denominator",
        ),
        _check(
            "positive-stage-budgets",
            all(item.budget_units > 0 for item in stages),
            min((item.budget_units for item in stages), default=0),
            ">0",
            "every program stage has an explicit workload budget",
        ),
        _check(
            "stage-budget-closure",
            all(item.within_budget for item in stages),
            [item.stage_id for item in stages if not item.within_budget],
            [],
            "no program stage exceeds its workload budget",
        ),
        _check(
            "runtime-accepted",
            selected_runtime.accepted,
            selected_runtime.state.value,
            "accepted",
            "the source program runtime is accepted",
        ),
        _check(
            "program-denominators",
            len(selected_runtime.report.receipts) == 16
            and len(selected_runtime.report.checks) == 172,
            (len(selected_runtime.report.receipts), len(selected_runtime.report.checks)),
            (16, 172),
            "all sixteen domain receipts and 172 program checks are retained",
        ),
        _check(
            "quality-denominator",
            len(selected_runtime.quality.checks) == 18,
            len(selected_runtime.quality.checks),
            18,
            "the independent quality gate retains eighteen checks",
        ),
        _check(
            "release-accepted",
            selected_release.accepted,
            selected_release.state.value,
            "published",
            "the release descriptor is publication-ready",
        ),
        _check(
            "release-artifact-denominator",
            len(artifacts) == PROGRAM_OPERATIONAL_ARTIFACT_COUNT,
            len(artifacts),
            PROGRAM_OPERATIONAL_ARTIFACT_COUNT,
            "all eleven portable release artifacts are retained",
        ),
        _check(
            "release-check-denominator",
            len(selected_release.checks) == 18,
            len(selected_release.checks),
            18,
            "the release descriptor retains eighteen publication checks",
        ),
        _check(
            "artifact-identities",
            len({item.artifact_id for item in artifacts}) == len(artifacts)
            and len({item.filename for item in artifacts}) == len(artifacts),
            (len({item.artifact_id for item in artifacts}), len({item.filename for item in artifacts})),
            (len(artifacts), len(artifacts)),
            "release artifact IDs and filenames are unique",
        ),
        _check(
            "artifact-addresses",
            all(item.content_address.startswith("program-artifact-work:") for item in artifacts),
            sum(item.content_address.startswith("program-artifact-work:") for item in artifacts),
            len(artifacts),
            "every artifact workload receipt is content-addressed",
        ),
        _check(
            "artifact-dimensions",
            all(item.byte_count > 0 and item.line_count > 0 for item in artifacts),
            min((item.byte_count for item in artifacts), default=0),
            ">0 bytes and lines",
            "every release artifact has positive dimensions",
        ),
        _check(
            "artifact-budget-closure",
            all(item.within_budget for item in artifacts),
            [item.filename for item in artifacts if not item.within_budget],
            [],
            "no release artifact exceeds its byte budget",
        ),
        _check(
            "public-projection",
            not contains_private_key(
                {
                    "runtime": selected_runtime.to_dict(),
                    "release": selected_release.to_dict(),
                }
            ),
            True,
            True,
            "program and release projections contain no private subject keys",
        ),
        _check(
            "stage-work-closure",
            counter_map["total_stage_work_units"] == sum(item.work_units for item in stages),
            total_stage_work,
            total_stage_work,
            "stage workload counters conserve every stage receipt",
        ),
        _check(
            "artifact-byte-closure",
            counter_map["total_artifact_bytes"] == sum(item.byte_count for item in artifacts),
            total_artifact_bytes,
            total_artifact_bytes,
            "artifact byte counters conserve every artifact receipt",
        ),
        _check(
            "counter-closure",
            len(counter_map) == len(counters) and counters == tuple(sorted(counters)),
            len(counters),
            len(dict(counters)),
            "operational counters are unique and canonically sorted",
        ),
        _check(
            "address-closure",
            selected_runtime.content_address.startswith("architecture-program-runtime:")
            and selected_release.content_address.startswith("architecture-program-release:"),
            (selected_runtime.content_address, selected_release.content_address),
            ("architecture-program-runtime:<digest>", "architecture-program-release:<digest>"),
            "runtime and release inputs are content-addressed",
        ),
        _check(
            "matrix-closure",
            len(architecture_program_domain_matrix(selected_runtime.report)) == 16,
            len(architecture_program_domain_matrix(selected_runtime.report)),
            16,
            "the query matrix retains one row per architecture domain",
        ),
        _check(
            "accepted-state-closure",
            selected_runtime.accepted and selected_release.accepted,
            (selected_runtime.accepted, selected_release.accepted),
            (True, True),
            "operational acceptance requires both runtime and release acceptance",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "run_id": selected_runtime.run_id,
        "runtime_address": selected_runtime.content_address,
        "release_address": selected_release.content_address,
        "stages": stages,
        "artifacts": artifacts,
        "counters": counters,
        "checks": checks,
        "accepted": accepted,
    }
    return ProgramOperationalTrace(
        **body,
        content_address=content_hash(body, prefix="architecture-program-operational"),
    )


def build_program_operational_closure(
    runtime: ProgramRuntime | None = None,
    release: ProgramRelease | None = None,
) -> dict[str, Any]:
    """Build a self-contained offline handoff closure with artifact line sets."""

    selected_runtime = runtime or run_program_runtime()
    replay = replay_architecture_program()
    failures = run_program_runtime_failure_injections()
    selected_release = release or build_program_release(
        selected_runtime,
        replay=replay,
        failure_controls=failures,
    )
    trace = build_program_operational_trace(selected_runtime, selected_release)
    payloads = program_release_payloads(
        selected_runtime,
        replay=replay,
        failure_controls=failures,
    )
    return {
        **trace.to_dict(),
        "operational": trace.to_dict(),
        "runtime": selected_runtime.to_dict(),
        "release": selected_release.to_dict(),
        "replay": replay.to_dict(),
        "failure_controls": failures.to_dict(),
        "artifact_payload_lines": {
            filename: text.splitlines() for filename, text in sorted(payloads.items())
        },
    }


def verify_program_operational_trace(trace: ProgramOperationalTrace) -> tuple[str, ...]:
    """Recompute trace integrity and return every detected failure."""

    failures: list[str] = []
    if not trace.accepted:
        failures.append("operational-not-accepted")
    if len(trace.stages) != PROGRAM_OPERATIONAL_STAGE_COUNT:
        failures.append("stage-count")
    if len(trace.artifacts) != PROGRAM_OPERATIONAL_ARTIFACT_COUNT:
        failures.append("artifact-count")
    if len(trace.checks) != PROGRAM_OPERATIONAL_CHECK_COUNT:
        failures.append("check-count")
    if trace.failed_check_ids:
        failures.extend(trace.failed_check_ids)
    if not trace.content_address.startswith("architecture-program-operational:"):
        failures.append("operational-address")
    if len(dict(trace.counters)) != len(trace.counters):
        failures.append("counter-duplicates")
    if tuple(item.stage_id for item in trace.stages) != PROGRAM_RUNTIME_STAGE_IDS:
        failures.append("stage-identities")
    if tuple(item.sequence for item in trace.stages) != tuple(range(1, 13)):
        failures.append("stage-sequence")
    for receipt in trace.stages:
        body = {
            "sequence": receipt.sequence,
            "stage_id": receipt.stage_id,
            "state": receipt.state,
            "input_count": receipt.input_count,
            "output_address": receipt.output_address,
            "work_units": receipt.work_units,
            "budget_units": receipt.budget_units,
            "within_budget": receipt.within_budget,
        }
        if receipt.content_address != content_hash(body, prefix="program-stage-work"):
            failures.append(f"stage-address:{receipt.stage_id}")
        if receipt.within_budget != (0 < receipt.work_units <= receipt.budget_units):
            failures.append(f"stage-budget:{receipt.stage_id}")
    for receipt in trace.artifacts:
        body = {
            "artifact_id": receipt.artifact_id,
            "kind": receipt.kind,
            "filename": receipt.filename,
            "byte_count": receipt.byte_count,
            "line_count": receipt.line_count,
            "byte_budget": receipt.byte_budget,
            "within_budget": receipt.within_budget,
        }
        if receipt.content_address != content_hash(body, prefix="program-artifact-work"):
            failures.append(f"artifact-address:{receipt.filename}")
        if receipt.within_budget != (0 < receipt.byte_count <= receipt.byte_budget):
            failures.append(f"artifact-budget:{receipt.filename}")
    if contains_private_key(trace.to_dict()):
        failures.append("private-projection")
    body = {
        "run_id": trace.run_id,
        "runtime_address": trace.runtime_address,
        "release_address": trace.release_address,
        "stages": trace.stages,
        "artifacts": trace.artifacts,
        "counters": trace.counters,
        "checks": trace.checks,
        "accepted": trace.accepted,
    }
    if trace.content_address != content_hash(body, prefix="architecture-program-operational"):
        failures.append("operational-address-integrity")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "PROGRAM_OPERATIONAL_ARTIFACT_BUDGETS",
    "PROGRAM_OPERATIONAL_ARTIFACT_COUNT",
    "PROGRAM_OPERATIONAL_CHECK_COUNT",
    "PROGRAM_OPERATIONAL_STAGE_BUDGETS",
    "PROGRAM_OPERATIONAL_STAGE_COUNT",
    "ProgramArtifactWorkReceipt",
    "ProgramOperationalCheck",
    "ProgramOperationalTrace",
    "ProgramStageWorkReceipt",
    "build_program_operational_closure",
    "build_program_operational_trace",
    "verify_program_operational_trace",
]
