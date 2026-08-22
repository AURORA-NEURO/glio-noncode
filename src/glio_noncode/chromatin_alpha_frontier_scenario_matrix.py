"""Scenario matrix for supported and bounded chromatin-alpha paths."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


class ChromatinAlphaFrontierScenarioStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierScenario:
    scenario_id: str
    operation: ChromatinAlphaFrontierOperation
    context: str
    input_shape: str
    expected_state: str
    expected_boundary: str
    status: ChromatinAlphaFrontierScenarioStatus
    required_evidence: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.scenario_id
            or not self.context
            or not self.input_shape
            or not self.required_evidence
        ):
            raise ValidationError("scenario is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierScenarioMatrix:
    scenarios: tuple[ChromatinAlphaFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValidationError("scenario matrix cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: ChromatinAlphaFrontierOperation
    ) -> tuple[ChromatinAlphaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def by_status(
        self, status: ChromatinAlphaFrontierScenarioStatus
    ) -> tuple[ChromatinAlphaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.status is status)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"scenario_count": len(self.scenarios)}


def build_chromatin_alpha_frontier_scenario_matrix() -> ChromatinAlphaFrontierScenarioMatrix:
    paths = (
        (
            "supported",
            "valid aggregate rows",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.PASS,
            ("state", "receipt", "measurement"),
        ),
        (
            "ambiguous",
            "mixed replicate directions",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.REVIEW,
            ("spread", "state", "review"),
        ),
        (
            "partial",
            "missing or invalid row",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.REVIEW,
            ("issue_code", "state", "receipt"),
        ),
        (
            "out_of_domain",
            "foreign context",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.REVIEW,
            ("context", "quarantine", "receipt"),
        ),
        (
            "abstained",
            "insufficient observations",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.REVIEW,
            ("abstention", "state", "review"),
        ),
        (
            "replay",
            "same input repeated",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.PASS,
            ("address", "same_result"),
        ),
        (
            "boundary",
            "subject-level input attempted",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.REVIEW,
            ("boundary_error", "quarantine"),
        ),
        (
            "release",
            "supported positive path",
            "public_aggregate_non_patient",
            ChromatinAlphaFrontierScenarioStatus.PASS,
            ("policy", "lineage", "bundle"),
        ),
    )
    scenarios = tuple(
        ChromatinAlphaFrontierScenario(
            scenario_id=f"chromatin-alpha-scenario-{index:03d}",
            operation=operation,
            context=path[0],
            input_shape=path[1],
            expected_state=path[0],
            expected_boundary=path[2],
            status=path[3],
            required_evidence=path[4],
        )
        for index, (operation, path) in enumerate(
            ((operation, path) for operation in ChromatinAlphaFrontierOperation for path in paths),
            start=1,
        )
    )
    return ChromatinAlphaFrontierScenarioMatrix(
        scenarios, all(item.required_evidence for item in scenarios)
    )


def evaluate_chromatin_alpha_frontier_scenarios(
    matrix: ChromatinAlphaFrontierScenarioMatrix | None = None,
) -> ChromatinAlphaFrontierScenarioMatrix:
    selected = matrix or build_chromatin_alpha_frontier_scenario_matrix()
    return ChromatinAlphaFrontierScenarioMatrix(
        selected.scenarios,
        selected.accepted
        and all(
            item.status is not ChromatinAlphaFrontierScenarioStatus.FAIL
            for item in selected.scenarios
        ),
    )


__all__ = [
    "ChromatinAlphaFrontierScenario",
    "ChromatinAlphaFrontierScenarioMatrix",
    "ChromatinAlphaFrontierScenarioStatus",
    "build_chromatin_alpha_frontier_scenario_matrix",
    "evaluate_chromatin_alpha_frontier_scenarios",
]
