"""Replayable fixture evaluation for Domain 06 C05-C08."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_adapters import (
    SequenceGrammarAdapterResult,
    execute_sequence_grammar_record,
)
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarOperation,
    SequenceGrammarRecord,
    SequenceGrammarRole,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarCheck:
    """One deterministic evaluation assertion."""

    check_id: str
    record_id: str
    check_type: str
    passed: bool
    expected: Any
    observed: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.record_id.strip() or not self.detail.strip():
            raise ValidationError("evaluation checks require identity and detail")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "check_id": self.check_id,
                        "record_id": self.record_id,
                        "check_type": self.check_type,
                        "passed": self.passed,
                        "expected": self.expected,
                        "observed": self.observed,
                        "detail": self.detail,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarExecution:
    """Adapter output joined to its fixture record."""

    record_id: str
    operation: SequenceGrammarOperation
    role: SequenceGrammarRole
    expected_state: SequenceGrammarState
    adapter_state: SequenceGrammarState
    issue_codes: tuple[str, ...]
    expected_issue_codes: tuple[str, ...]
    accepted: bool
    detail: str
    measurements: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    adapter_address: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.adapter_address:
            raise ValidationError("execution identity and adapter address are required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "expected_state": self.expected_state,
                        "adapter_state": self.adapter_state,
                        "issue_codes": self.issue_codes,
                        "expected_issue_codes": self.expected_issue_codes,
                        "accepted": self.accepted,
                        "detail": self.detail,
                        "measurements": self.measurements,
                        "warnings": self.warnings,
                        "adapter_address": self.adapter_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarEvaluation:
    """Complete fixture replay with per-record checks and counts."""

    fixture_id: str
    fixture_address: str
    accepted: bool
    executions: tuple[SequenceGrammarExecution, ...]
    checks: tuple[SequenceGrammarCheck, ...]
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    invalid_count: int
    abstained_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id.strip() or not self.fixture_address:
            raise ValidationError("evaluation fixture identity is required")
        if not self.executions or not self.checks:
            raise ValidationError("evaluation requires executions and checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "fixture_address": self.fixture_address,
                        "accepted": self.accepted,
                        "executions": self.executions,
                        "checks": self.checks,
                        "positive_count": self.positive_count,
                        "control_count": self.control_count,
                    }
                ),
            )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def execution_map(self) -> dict[str, SequenceGrammarExecution]:
        return {execution.record_id: execution for execution in self.executions}

    def operation_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for execution in self.executions:
            counts[execution.operation.value] = counts.get(execution.operation.value, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_address": self.fixture_address,
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "supported_count": self.supported_count,
            "review_count": self.review_count,
            "invalid_count": self.invalid_count,
            "abstained_count": self.abstained_count,
            "check_count": len(self.checks),
            "failed_check_ids": list(self.failed_check_ids),
            "operation_counts": self.operation_counts(),
            "executions": [execution.to_dict() for execution in self.executions],
            "checks": [check.to_dict() for check in self.checks],
            "content_address": self.content_address,
        }


def _execution(
    record: SequenceGrammarRecord, result: SequenceGrammarAdapterResult
) -> SequenceGrammarExecution:
    expected_codes = tuple(sorted(record.expected_issue_codes))
    observed_codes = tuple(sorted(result.issue_codes))
    state_ok = result.state is record.expected_state
    code_ok = set(expected_codes) <= set(observed_codes)
    return SequenceGrammarExecution(
        record_id=record.record_id,
        operation=record.operation,
        role=record.role,
        expected_state=record.expected_state,
        adapter_state=result.state,
        issue_codes=result.issue_codes,
        expected_issue_codes=record.expected_issue_codes,
        accepted=state_ok and code_ok,
        detail=result.detail,
        measurements=result.measurements,
        warnings=result.warnings,
        adapter_address=result.content_address,
    )


def _checks(
    record: SequenceGrammarRecord, execution: SequenceGrammarExecution
) -> tuple[SequenceGrammarCheck, ...]:
    checks = (
        (
            "state",
            execution.expected_state.value,
            execution.adapter_state.value,
            execution.expected_state is execution.adapter_state,
            "adapter state matches declared boundary",
        ),
        (
            "issues",
            tuple(sorted(execution.expected_issue_codes)),
            tuple(sorted(execution.issue_codes)),
            set(execution.expected_issue_codes) <= set(execution.issue_codes),
            "declared issue codes are retained",
        ),
        (
            "operation",
            record.operation.value,
            execution.operation.value,
            record.operation is execution.operation,
            "operation identity is conserved",
        ),
        (
            "role",
            record.role.value,
            execution.role.value,
            record.role is execution.role,
            "positive/control role is conserved",
        ),
        (
            "address",
            True,
            execution.adapter_address.startswith("sha256:"),
            execution.adapter_address.startswith("sha256:"),
            "adapter result is addressed",
        ),
        (
            "detail",
            True,
            bool(execution.detail.strip()),
            bool(execution.detail.strip()),
            "adapter emitted operational detail",
        ),
    )
    return tuple(
        SequenceGrammarCheck(
            check_id=f"{record.record_id}:{check_type}",
            record_id=record.record_id,
            check_type=check_type,
            passed=passed,
            expected=expected,
            observed=observed,
            detail=detail,
        )
        for check_type, expected, observed, passed, detail in checks
    )


def evaluate_sequence_grammar_fixture(fixture: SequenceGrammarFixture) -> SequenceGrammarEvaluation:
    """Execute and check every positive and control record exactly once."""

    executions: list[SequenceGrammarExecution] = []
    checks: list[SequenceGrammarCheck] = []
    for record in fixture.records:
        execution = _execution(record, execute_sequence_grammar_record(record))
        executions.append(execution)
        checks.extend(_checks(record, execution))
    states = [execution.adapter_state for execution in executions]
    accepted = all(check.passed for check in checks)
    return SequenceGrammarEvaluation(
        fixture_id=fixture.fixture_id,
        fixture_address=fixture.content_address,
        accepted=accepted,
        executions=tuple(executions),
        checks=tuple(checks),
        positive_count=sum(
            execution.role is SequenceGrammarRole.POSITIVE for execution in executions
        ),
        control_count=sum(
            execution.role is SequenceGrammarRole.CONTROL for execution in executions
        ),
        supported_count=sum(state is SequenceGrammarState.SUPPORTED for state in states),
        review_count=sum(
            state in {SequenceGrammarState.PARTIAL, SequenceGrammarState.AMBIGUOUS}
            for state in states
        ),
        invalid_count=sum(state is SequenceGrammarState.INVALID for state in states),
        abstained_count=sum(state is SequenceGrammarState.ABSTAINED for state in states),
    )


__all__ = [
    "SequenceGrammarCheck",
    "SequenceGrammarEvaluation",
    "SequenceGrammarExecution",
    "evaluate_sequence_grammar_fixture",
]
