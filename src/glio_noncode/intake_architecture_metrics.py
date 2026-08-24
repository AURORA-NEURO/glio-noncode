"""Aggregate metrics for D01 execution without exposing source payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureRuntime, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitectureOperationMetric:
    operation_id: str
    total_cases: int
    positive_cases: int
    held_cases: int
    accepted_cases: int
    receipt_count: int
    evaluation_check_count: int
    issue_code_counts: tuple[tuple[str, int], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "total_cases": self.total_cases,
            "positive_cases": self.positive_cases,
            "held_cases": self.held_cases,
            "accepted_cases": self.accepted_cases,
            "receipt_count": self.receipt_count,
            "evaluation_check_count": self.evaluation_check_count,
            "issue_code_counts": {key: value for key, value in self.issue_code_counts},
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class IntakeArchitectureMetrics:
    fixture_id: str
    total_cases: int
    positive_cases: int
    control_cases: int
    accepted_cases: int
    held_cases: int
    evaluation_check_count: int
    compliance_check_count: int
    stage_count: int
    state_counts: tuple[tuple[str, int], ...]
    operation_metrics: tuple[IntakeArchitectureOperationMetric, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "total_cases": self.total_cases,
            "positive_cases": self.positive_cases,
            "control_cases": self.control_cases,
            "accepted_cases": self.accepted_cases,
            "held_cases": self.held_cases,
            "evaluation_check_count": self.evaluation_check_count,
            "compliance_check_count": self.compliance_check_count,
            "stage_count": self.stage_count,
            "state_counts": {key: value for key, value in self.state_counts},
            "operation_metrics": [item.to_dict() for item in self.operation_metrics],
            "content_address": self.content_address,
        }


def measure_intake_architecture(runtime: IntakeArchitectureRuntime) -> IntakeArchitectureMetrics:
    operation_metrics = []
    for spec in runtime.plan.nodes:
        rows = tuple(
            item for item in runtime.evaluation.results if item.operation_id == spec.operation_id
        )
        positive = tuple(item for item in rows if item.scenario.value == "positive")
        body = {
            "operation_id": spec.operation_id,
            "total_cases": len(rows),
            "positive_cases": len(positive),
            "held_cases": sum(item.observed_state.value != "accepted" for item in rows),
            "accepted_cases": sum(item.observed_state.value == "accepted" for item in rows),
            "receipt_count": sum(len(item.receipt_addresses) for item in rows),
            "evaluation_check_count": sum(
                item.case_id == result.case_id
                for item in runtime.evaluation.checks
                for result in rows
            ),
            "issue_code_counts": tuple(
                sorted(
                    (code, sum(code in item.issue_codes for item in rows))
                    for code in {code for item in rows for code in item.issue_codes}
                )
            ),
        }
        operation_metrics.append(
            IntakeArchitectureOperationMetric(
                **body, content_address=addressed(body, "intake-metric-operation")
            )
        )
    body = {
        "fixture_id": runtime.fixture_id,
        "total_cases": len(runtime.evaluation.results),
        "positive_cases": sum(
            item.scenario.value == "positive" for item in runtime.evaluation.results
        ),
        "control_cases": sum(
            item.scenario.value != "positive" for item in runtime.evaluation.results
        ),
        "accepted_cases": sum(
            item.observed_state.value == "accepted" for item in runtime.evaluation.results
        ),
        "held_cases": sum(
            item.observed_state.value != "accepted" for item in runtime.evaluation.results
        ),
        "evaluation_check_count": len(runtime.evaluation.checks),
        "compliance_check_count": len(runtime.compliance.checks) if runtime.compliance else 0,
        "stage_count": len(runtime.stages),
        "state_counts": tuple(
            sorted(
                (
                    state,
                    sum(item.observed_state.value == state for item in runtime.evaluation.results),
                )
                for state in {item.observed_state.value for item in runtime.evaluation.results}
            )
        ),
        "operation_metrics": tuple(operation_metrics),
    }
    return IntakeArchitectureMetrics(**body, content_address=addressed(body, "intake-metrics"))


__all__ = [
    "IntakeArchitectureOperationMetric",
    "IntakeArchitectureMetrics",
    "measure_intake_architecture",
]
