"""Accessibility checks for serialized chromatin-alpha surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierFixture,
    ChromatinAlphaFrontierOperation,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierAccessibilityCheck:
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
class ChromatinAlphaFrontierAccessibilityReport:
    fixture_id: str
    checks: tuple[ChromatinAlphaFrontierAccessibilityCheck, ...]
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

    def for_surface(self, surface: str) -> tuple[ChromatinAlphaFrontierAccessibilityCheck, ...]:
        return tuple(check for check in self.checks if check.surface == surface)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(
    index: int, surface: str, passed: bool, observed: Any, required: Any, detail: str
) -> ChromatinAlphaFrontierAccessibilityCheck:
    return ChromatinAlphaFrontierAccessibilityCheck(
        f"chromatin-alpha-a11y-{index:03d}", surface, passed, observed, required, detail
    )


def evaluate_chromatin_alpha_frontier_accessibility(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierAccessibilityReport:
    checks: list[ChromatinAlphaFrontierAccessibilityCheck] = []
    index = 1
    for operation in ChromatinAlphaFrontierOperation:
        rows = tuple(item for item in evaluation.records if item.adapter.operation is operation)
        checks.extend(
            (
                _check(
                    index, operation.value, len(rows) == 4, len(rows), 4, "operation has four rows"
                ),
                _check(
                    index + 1,
                    operation.value,
                    all(item.observed_state for item in rows),
                    len(rows),
                    len(rows),
                    "observed state text is visible",
                ),
                _check(
                    index + 2,
                    operation.value,
                    all(item.expected_state for item in rows),
                    len(rows),
                    len(rows),
                    "expected state text is visible",
                ),
                _check(
                    index + 3,
                    operation.value,
                    all(item.adapter.measurements is not None for item in rows),
                    len(rows),
                    len(rows),
                    "measurement field is present",
                ),
                _check(
                    index + 4,
                    operation.value,
                    all(item.adapter.content_address.startswith("sha256:") for item in rows),
                    len(rows),
                    len(rows),
                    "receipt address is visible",
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
            _check(
                index + 2,
                "fixture",
                all(source.release for source in fixture.sources),
                len(fixture.sources),
                5,
                "source release labels are visible",
            ),
        )
    )
    return ChromatinAlphaFrontierAccessibilityReport(
        fixture.fixture_id, tuple(checks), all(check.passed for check in checks)
    )


__all__ = [
    "ChromatinAlphaFrontierAccessibilityCheck",
    "ChromatinAlphaFrontierAccessibilityReport",
    "evaluate_chromatin_alpha_frontier_accessibility",
]
