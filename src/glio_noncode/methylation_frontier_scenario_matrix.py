"""Scenario matrix for supported, control, and abstention methylation paths."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .methylation_frontier_public_data import MethylationFrontierOperation
from .serialization import content_hash, jsonable


class MethylationFrontierScenarioStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class MethylationFrontierScenario:
    scenario_id: str
    operation: MethylationFrontierOperation
    context: str
    input_shape: str
    expected_state: str
    expected_boundary: str
    status: MethylationFrontierScenarioStatus
    required_evidence: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.context or not self.input_shape:
            raise ValidationError("scenario identity is incomplete")
        if not self.required_evidence:
            raise ValidationError("scenario requires evidence")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierScenarioMatrix:
    scenarios: tuple[MethylationFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValidationError("scenario matrix cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: MethylationFrontierOperation
    ) -> tuple[MethylationFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def by_status(
        self, status: MethylationFrontierScenarioStatus
    ) -> tuple[MethylationFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.status is status)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"scenario_count": len(self.scenarios)}


def build_methylation_frontier_scenario_matrix() -> MethylationFrontierScenarioMatrix:
    """Create a 32-case operation-by-path matrix."""

    paths = (
        (
            "supported",
            "valid aggregate payload",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.PASS,
            ("receipt", "state", "measurement"),
        ),
        (
            "partial",
            "valid payload with warning",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.REVIEW,
            ("warning", "state", "receipt"),
        ),
        (
            "invalid",
            "malformed critical field",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.REVIEW,
            ("error", "issue_code", "receipt"),
        ),
        (
            "out_of_domain",
            "foreign context or length",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.REVIEW,
            ("boundary", "state", "receipt"),
        ),
        (
            "abstained",
            "insufficient support",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.REVIEW,
            ("abstention", "state", "receipt"),
        ),
        (
            "missing_source",
            "declared source unavailable",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.REVIEW,
            ("source_receipt", "state", "review"),
        ),
        (
            "replay",
            "same payload repeated",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.PASS,
            ("content_address", "same_result"),
        ),
        (
            "boundary",
            "subject-level field attempted",
            "public_aggregate_non_patient",
            MethylationFrontierScenarioStatus.REVIEW,
            ("boundary_error", "quarantine"),
        ),
    )
    scenarios = tuple(
        MethylationFrontierScenario(
            scenario_id=f"methylation-scenario-{index:03d}",
            operation=operation,
            context=path[0],
            input_shape=path[1],
            expected_state=path[0],
            expected_boundary=path[2],
            status=path[3],
            required_evidence=path[4],
        )
        for index, (operation, path) in enumerate(
            ((operation, path) for operation in MethylationFrontierOperation for path in paths),
            start=1,
        )
    )
    return MethylationFrontierScenarioMatrix(
        scenarios, all(item.required_evidence for item in scenarios)
    )


__all__ = [
    "MethylationFrontierScenario",
    "MethylationFrontierScenarioMatrix",
    "MethylationFrontierScenarioStatus",
    "build_methylation_frontier_scenario_matrix",
]
