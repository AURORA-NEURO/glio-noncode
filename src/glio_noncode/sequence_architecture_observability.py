"""Runtime observation checks for D06 stages and receipt population."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureRuntime,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureObservation:
    fixture_id: str
    stage_count: int
    case_count: int
    positive_count: int
    control_count: int
    issue_count: int
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        from .serialization import jsonable

        return jsonable(self)


def observe_sequence_architecture_run(
    runtime: SequenceArchitectureRuntime,
) -> SequenceArchitectureObservation:
    checks = (
        _check(
            "observe-stages",
            len(runtime.stages) == 20,
            len(runtime.stages),
            20,
            "all ordered runtime stages are present",
        ),
        _check(
            "observe-cases",
            len(runtime.evaluation.receipts) == 64,
            len(runtime.evaluation.receipts),
            64,
            "all cases have receipts",
        ),
        _check(
            "observe-positives",
            runtime.evaluation.positive_count == 16,
            runtime.evaluation.positive_count,
            16,
            "sixteen positive paths are observable",
        ),
        _check(
            "observe-controls",
            runtime.evaluation.control_count == 48,
            runtime.evaluation.control_count,
            48,
            "forty-eight controls are observable",
        ),
        _check(
            "observe-control-issues",
            sum(
                bool(item.observed_issue_codes)
                for item in runtime.evaluation.receipts
                if item.expected_state.value == "review"
            )
            == 48,
            sum(
                bool(item.observed_issue_codes)
                for item in runtime.evaluation.receipts
                if item.expected_state.value == "review"
            ),
            48,
            "every held control has an issue receipt",
        ),
    )
    body = {
        "fixture_id": runtime.fixture_id,
        "stage_count": len(runtime.stages),
        "case_count": len(runtime.evaluation.receipts),
        "checks": checks,
    }
    return SequenceArchitectureObservation(
        fixture_id=runtime.fixture_id,
        stage_count=len(runtime.stages),
        case_count=len(runtime.evaluation.receipts),
        positive_count=runtime.evaluation.positive_count,
        control_count=runtime.evaluation.control_count,
        issue_count=sum(len(item.observed_issue_codes) for item in runtime.evaluation.receipts),
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-observation"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.RELEASE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-observation-check"),
    )


__all__ = ["SequenceArchitectureObservation", "observe_sequence_architecture_run"]
