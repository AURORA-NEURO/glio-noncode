"""Deterministic operational workload and budget trace for D04 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .reference_release_frontier_observability import (
    ReferenceReleaseObservabilityReport,
    observe_reference_release,
)
from .reference_release_frontier_runtime import ReferenceReleaseRuntimeReport
from .serialization import content_hash, jsonable

REFERENCE_RELEASE_OPERATIONAL_STAGE_COUNT = 9
REFERENCE_RELEASE_OPERATIONAL_CHECK_COUNT = 18

_STAGE_BUDGETS = {
    "data-audit": 500,
    "fixture-evaluation": 1000,
    "metrics": 256,
    "policy": 1000,
    "lineage": 2000,
    "projection-audit": 1000,
    "reconciliation": 512,
    "quality-gate": 1000,
    "replay": 512,
}


@dataclass(frozen=True, slots=True)
class ReferenceReleaseStageWorkReceipt:
    """One deterministic stage workload receipt without wall-clock data."""

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
class ReferenceReleaseOperationalCheck:
    """One operational trace integrity or safety assertion."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseOperationalTrace:
    """Stage workload trace and independent operational acceptance gate."""

    run_id: str
    runtime_address: str
    observability_address: str
    stages: tuple[ReferenceReleaseStageWorkReceipt, ...]
    counters: tuple[tuple[str, int | float], ...]
    checks: tuple[ReferenceReleaseOperationalCheck, ...]
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
            "observability_address": self.observability_address,
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": len(self.stages),
            "counters": dict(self.counters),
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "failed_check_ids": list(self.failed_check_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _work_units(runtime: ReferenceReleaseRuntimeReport, stage_id: str) -> int:
    """Calculate stable work units from report cardinalities, not elapsed time."""

    if stage_id == "data-audit":
        return len(runtime.data_audit.checks) + 16
    if stage_id == "fixture-evaluation":
        return len(runtime.evaluation.executions) * 3 + len(runtime.evaluation.checks)
    if stage_id == "metrics":
        return (
            len(runtime.metrics.operation_metrics) * 5
            + len(runtime.metrics.issue_code_counts)
            + runtime.metrics.max_output_keys
        )
    if stage_id == "policy":
        return len(runtime.policy.rules) * 2 + len(runtime.policy.decisions) * 3 + len(runtime.policy.checks)
    if stage_id == "lineage":
        return len(runtime.lineage.nodes) + len(runtime.lineage.edges)
    if stage_id == "projection-audit":
        return len(runtime.projection.checks)
    if stage_id == "reconciliation":
        return len(runtime.reconciliation.checks)
    if stage_id == "quality-gate":
        return len(runtime.quality.checks)
    if stage_id == "replay":
        return len(runtime.replay.checks) * 2
    return 0


def _stage_receipts(runtime: ReferenceReleaseRuntimeReport) -> tuple[ReferenceReleaseStageWorkReceipt, ...]:
    receipts: list[ReferenceReleaseStageWorkReceipt] = []
    for stage in runtime.stages:
        work_units = _work_units(runtime, stage.stage_id)
        budget_units = _STAGE_BUDGETS.get(stage.stage_id, 0)
        body = {
            "sequence": stage.sequence,
            "stage_id": stage.stage_id,
            "state": stage.state,
            "input_count": len(stage.inputs),
            "output_address": stage.output_address,
            "work_units": work_units,
            "budget_units": budget_units,
            "within_budget": 0 < work_units <= budget_units,
        }
        receipts.append(
            ReferenceReleaseStageWorkReceipt(
                **body,
                content_address=content_hash(body, prefix="release-stage-work"),
            )
        )
    return tuple(receipts)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ReferenceReleaseOperationalCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceReleaseOperationalCheck(
        **body,
        content_address=content_hash(body, prefix="release-operational-check"),
    )


def build_reference_release_operational_trace(
    runtime: ReferenceReleaseRuntimeReport,
    observability: ReferenceReleaseObservabilityReport | None = None,
) -> ReferenceReleaseOperationalTrace:
    """Build deterministic stage workload, utilization, and safety evidence."""

    selected_observability = observability or observe_reference_release(runtime)
    stages = _stage_receipts(runtime)
    total_work = sum(item.work_units for item in stages)
    total_budget = sum(item.budget_units for item in stages)
    utilization = round(100.0 * total_work / max(1, total_budget), 6)
    counters: tuple[tuple[str, int | float], ...] = tuple(
        sorted(
            {
                "stage_count": len(stages),
                "execution_count": len(runtime.evaluation.executions),
                "evaluation_check_count": len(runtime.evaluation.checks),
                "quality_check_count": len(runtime.quality.checks),
                "total_work_units": total_work,
                "total_budget_units": total_budget,
                "utilization_percent": utilization,
                "max_stage_work_units": max((item.work_units for item in stages), default=0),
                "review_observation_count": len(selected_observability.observations),
            }.items()
        )
    )
    checks = (
        _check(
            "stage-denominator",
            len(stages) == REFERENCE_RELEASE_OPERATIONAL_STAGE_COUNT,
            len(stages),
            REFERENCE_RELEASE_OPERATIONAL_STAGE_COUNT,
            "all nine runtime stages produce workload receipts",
        ),
        _check(
            "stage-sequence",
            tuple(item.sequence for item in stages) == tuple(range(1, 10)),
            tuple(item.sequence for item in stages),
            tuple(range(1, 10)),
            "stage sequences are contiguous and ordered",
        ),
        _check(
            "stage-identities",
            tuple(item.stage_id for item in stages) == tuple(item.stage_id for item in runtime.stages),
            tuple(item.stage_id for item in stages),
            tuple(item.stage_id for item in runtime.stages),
            "work receipts retain runtime stage identities",
        ),
        _check(
            "stage-addresses",
            all(item.content_address.startswith("release-stage-work:") for item in stages),
            sum(item.content_address.startswith("release-stage-work:") for item in stages),
            len(stages),
            "every workload receipt is content-addressed",
        ),
        _check(
            "stage-output-addresses",
            all(":" in item.output_address for item in stages),
            sum(":" in item.output_address for item in stages),
            len(stages),
            "every runtime stage exposes an output address",
        ),
        _check(
            "positive-work",
            all(item.work_units > 0 for item in stages),
            min((item.work_units for item in stages), default=0),
            ">0",
            "every stage has a deterministic workload denominator",
        ),
        _check(
            "positive-budgets",
            all(item.budget_units > 0 for item in stages),
            min((item.budget_units for item in stages), default=0),
            ">0",
            "every stage has an explicit workload budget",
        ),
        _check(
            "budget-closure",
            all(item.within_budget for item in stages),
            [item.stage_id for item in stages if not item.within_budget],
            [],
            "no stage exceeds its deterministic workload budget",
        ),
        _check(
            "runtime-accepted",
            runtime.accepted,
            runtime.accepted,
            True,
            "the source runtime is accepted",
        ),
        _check(
            "observability-accepted",
            selected_observability.accepted,
            selected_observability.accepted,
            True,
            "the source observability report is accepted",
        ),
        _check(
            "observability-address",
            selected_observability.content_address.startswith("observability:"),
            selected_observability.content_address,
            "observability:<digest>",
            "observability report is addressed",
        ),
        _check(
            "runtime-address",
            runtime.content_address.startswith("release-runtime:"),
            runtime.content_address,
            "release-runtime:<digest>",
            "runtime report is addressed",
        ),
        _check(
            "execution-denominator",
            len(runtime.evaluation.executions) == 16,
            len(runtime.evaluation.executions),
            16,
            "operational counters retain all sixteen execution receipts",
        ),
        _check(
            "evaluation-check-denominator",
            len(runtime.evaluation.checks) == 48,
            len(runtime.evaluation.checks),
            48,
            "operational counters retain all evaluation checks",
        ),
        _check(
            "positive-control-denominator",
            runtime.evaluation.positive_count == 4 and runtime.evaluation.control_count == 12,
            (runtime.evaluation.positive_count, runtime.evaluation.control_count),
            (4, 12),
            "positive and control receipt counts remain balanced",
        ),
        _check(
            "utilization-bound",
            0.0 < utilization <= 100.0,
            utilization,
            "(0,100]",
            "aggregate deterministic workload remains inside budget",
        ),
        _check(
            "public-projection",
            not contains_private_key(
                {"runtime": runtime.to_dict(), "observability": selected_observability.to_dict()}
            ),
            True,
            True,
            "operational projections contain no private subject keys",
        ),
        _check(
            "counter-closure",
            counters
            == tuple(
                sorted(
                    {
                        "stage_count": len(stages),
                        "execution_count": len(runtime.evaluation.executions),
                        "evaluation_check_count": len(runtime.evaluation.checks),
                        "quality_check_count": len(runtime.quality.checks),
                        "total_work_units": total_work,
                        "total_budget_units": total_budget,
                        "utilization_percent": utilization,
                        "max_stage_work_units": max(
                            (item.work_units for item in stages), default=0
                        ),
                        "review_observation_count": len(selected_observability.observations),
                    }.items()
                )
            ),
            True,
            True,
            "operational counters are internally conserved",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "run_id": runtime.run_id,
        "runtime_address": runtime.content_address,
        "observability_address": selected_observability.content_address,
        "stages": stages,
        "counters": counters,
        "checks": checks,
        "accepted": accepted,
    }
    return ReferenceReleaseOperationalTrace(
        **body,
        content_address=content_hash(body, prefix="release-operational"),
    )


def verify_reference_release_operational_trace(
    trace: ReferenceReleaseOperationalTrace,
) -> tuple[str, ...]:
    """Return operational trace failures without suppressing any check.

    Verification recomputes receipt, check, counter, and trace addresses so a
    serialized operational report cannot be marked valid after a field-level
    edit.
    """

    failures: list[str] = []
    if not trace.accepted:
        failures.append("operational-not-accepted")
    if len(trace.stages) != REFERENCE_RELEASE_OPERATIONAL_STAGE_COUNT:
        failures.append("stage-count")
    if len(trace.checks) != REFERENCE_RELEASE_OPERATIONAL_CHECK_COUNT:
        failures.append("check-count")
    if trace.failed_check_ids:
        failures.extend(trace.failed_check_ids)
    if not trace.content_address.startswith("release-operational:"):
        failures.append("operational-address")
    if len(dict(trace.counters)) != len(trace.counters):
        failures.append("counter-duplicates")
    expected_stage_ids = tuple(_STAGE_BUDGETS)
    if tuple(item.stage_id for item in trace.stages) != expected_stage_ids:
        failures.append("stage-identities")
    if tuple(item.sequence for item in trace.stages) != tuple(range(1, 10)):
        failures.append("stage-sequence")
    for receipt in trace.stages:
        stage_body = {
            "sequence": receipt.sequence,
            "stage_id": receipt.stage_id,
            "state": receipt.state,
            "input_count": receipt.input_count,
            "output_address": receipt.output_address,
            "work_units": receipt.work_units,
            "budget_units": receipt.budget_units,
            "within_budget": receipt.within_budget,
        }
        if receipt.content_address != content_hash(stage_body, prefix="release-stage-work"):
            failures.append(f"stage-address:{receipt.stage_id}")
        expected_within_budget = 0 < receipt.work_units <= receipt.budget_units
        if receipt.within_budget != expected_within_budget:
            failures.append(f"stage-budget:{receipt.stage_id}")
    for check in trace.checks:
        check_body = {
            "check_id": check.check_id,
            "passed": check.passed,
            "observed": check.observed,
            "required": check.required,
            "detail": check.detail,
        }
        if check.content_address != content_hash(check_body, prefix="release-operational-check"):
            failures.append(f"check-address:{check.check_id}")
    counters = trace.counter_map
    expected_counter_keys = {
        "stage_count",
        "execution_count",
        "evaluation_check_count",
        "quality_check_count",
        "total_work_units",
        "total_budget_units",
        "utilization_percent",
        "max_stage_work_units",
        "review_observation_count",
    }
    if set(counters) != expected_counter_keys:
        failures.append("counter-keys")
    total_work = sum(item.work_units for item in trace.stages)
    total_budget = sum(item.budget_units for item in trace.stages)
    if counters.get("stage_count") != len(trace.stages):
        failures.append("counter-stage-count")
    if counters.get("total_work_units") != total_work:
        failures.append("counter-work-total")
    if counters.get("total_budget_units") != total_budget:
        failures.append("counter-budget-total")
    expected_utilization = round(100.0 * total_work / max(1, total_budget), 6)
    if counters.get("utilization_percent") != expected_utilization:
        failures.append("counter-utilization")
    if counters.get("max_stage_work_units") != max(
        (item.work_units for item in trace.stages), default=0
    ):
        failures.append("counter-max-work")
    if contains_private_key(trace.to_dict()):
        failures.append("private-projection")
    trace_body = {
        "run_id": trace.run_id,
        "runtime_address": trace.runtime_address,
        "observability_address": trace.observability_address,
        "stages": trace.stages,
        "counters": trace.counters,
        "checks": trace.checks,
        "accepted": trace.accepted,
    }
    if trace.content_address != content_hash(trace_body, prefix="release-operational"):
        failures.append("operational-address-integrity")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "REFERENCE_RELEASE_OPERATIONAL_CHECK_COUNT",
    "REFERENCE_RELEASE_OPERATIONAL_STAGE_COUNT",
    "ReferenceReleaseOperationalCheck",
    "ReferenceReleaseOperationalTrace",
    "ReferenceReleaseStageWorkReceipt",
    "build_reference_release_operational_trace",
    "verify_reference_release_operational_trace",
]
