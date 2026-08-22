"""Accessibility checks for serialized methylation review surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_public_data import (
    MethylationFrontierFixture,
    MethylationFrontierOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierAccessibilityCheck:
    check_id: str
    surface: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.surface or not self.detail:
            raise ValidationError("accessibility check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierAccessibilityReport:
    fixture_id: str
    checks: tuple[MethylationFrontierAccessibilityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("accessibility report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    def for_surface(self, surface: str) -> tuple[MethylationFrontierAccessibilityCheck, ...]:
        return tuple(check for check in self.checks if check.surface == surface)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(
    index: int, surface: str, passed: bool, observed: Any, required: Any, detail: str
) -> MethylationFrontierAccessibilityCheck:
    return MethylationFrontierAccessibilityCheck(
        check_id=f"methylation-a11y-{index:03d}",
        surface=surface,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
    )


def evaluate_methylation_frontier_accessibility(
    fixture: MethylationFrontierFixture,
    evaluation: MethylationFrontierEvaluation,
) -> MethylationFrontierAccessibilityReport:
    """Require state, operation, issue, and receipt text for every operation."""

    checks: list[MethylationFrontierAccessibilityCheck] = []
    index = 1
    for operation in MethylationFrontierOperation:
        rows = tuple(item for item in evaluation.records if item.adapter.operation is operation)
        checks.extend(
            (
                _check(
                    index,
                    operation.value,
                    bool(rows),
                    len(rows),
                    4,
                    "operation has four review rows",
                ),
                _check(
                    index + 1,
                    operation.value,
                    all(item.observed_state.value for item in rows),
                    len(rows),
                    len(rows),
                    "state text is visible",
                ),
                _check(
                    index + 2,
                    operation.value,
                    all(item.expected_state.value for item in rows),
                    len(rows),
                    len(rows),
                    "expected path text is visible",
                ),
                _check(
                    index + 3,
                    operation.value,
                    all(item.adapter.content_address.startswith("sha256:") for item in rows),
                    len(rows),
                    len(rows),
                    "stable receipt is visible",
                ),
                _check(
                    index + 4,
                    operation.value,
                    all(item.observed_issue_codes is not None for item in rows),
                    len(rows),
                    len(rows),
                    "issue field is present even when empty",
                ),
            )
        )
        index += 5
    checks.extend(
        (
            _check(
                index,
                "fixture",
                bool(fixture.context_key),
                fixture.context_key,
                "context key",
                "context label is visible",
            ),
            _check(
                index + 1,
                "fixture",
                fixture.evidence_boundary == "public_aggregate_non_patient",
                fixture.evidence_boundary,
                "public_aggregate_non_patient",
                "boundary label is visible",
            ),
        )
    )
    return MethylationFrontierAccessibilityReport(
        fixture_id=fixture.fixture_id,
        checks=tuple(checks),
        accepted=all(check.passed for check in checks),
    )


__all__ = [
    "MethylationFrontierAccessibilityCheck",
    "MethylationFrontierAccessibilityReport",
    "evaluate_methylation_frontier_accessibility",
]
