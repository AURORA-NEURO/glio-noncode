"""Accessibility checks for serialized collaboration review surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_public_data import GammaFrontierFixture, GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierAccessibilityCheck:
    """One accessibility and navigation check."""

    check_id: str
    surface: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierAccessibilityReport:
    """Accessibility report over board columns, tables, and decisions."""

    fixture_id: str
    checks: tuple[GammaFrontierAccessibilityCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def for_surface(self, surface: str) -> tuple[GammaFrontierAccessibilityCheck, ...]:
        return tuple(item for item in self.checks if item.surface == surface)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(
    index: int, surface: str, passed: bool, observed: Any, required: Any, detail: str
) -> GammaFrontierAccessibilityCheck:
    body = {
        "check_id": f"gamma-a11y-{index:03d}",
        "surface": surface,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierAccessibilityCheck(
        **body, content_address=content_hash(body, prefix="a11y")
    )


def evaluate_gamma_frontier_accessibility(
    fixture: GammaFrontierFixture, evaluation: GammaFrontierEvaluation
) -> GammaFrontierAccessibilityReport:
    """Require labels, state text, and issue text in every serialized surface."""

    checks: list[GammaFrontierAccessibilityCheck] = []
    index = 1
    for operation in GammaFrontierOperation:
        rows = evaluation.by_operation(operation)
        checks.append(
            _check(index, operation.value, bool(rows), len(rows), ">0", "operation has review rows")
        )
        index += 1
        checks.append(
            _check(
                index,
                operation.value,
                all("state" in item.output for item in rows),
                sum("state" in item.output for item in rows),
                len(rows),
                "each row exposes state text",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                operation.value,
                all(item.content_address.startswith("sha256:") for item in rows),
                len(rows),
                len(rows),
                "each row has a stable address",
            )
        )
        index += 1
    board = evaluation.by_operation(GammaFrontierOperation.EXPERIMENT_BOARD)
    checks.append(
        _check(
            index,
            "experiment_board",
            all("columns" in item.output for item in board),
            len(board),
            len(board),
            "board output retains columns",
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": fixture.fixture_id, "checks": tuple(checks), "accepted": accepted}
    return GammaFrontierAccessibilityReport(
        **body, content_address=content_hash(body, prefix="a11y-report")
    )


__all__ = [
    "GammaFrontierAccessibilityCheck",
    "GammaFrontierAccessibilityReport",
    "evaluate_gamma_frontier_accessibility",
]
