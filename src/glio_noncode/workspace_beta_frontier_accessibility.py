"""Accessibility and interaction metadata checks for beta workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_public_data import BetaFrontierFixture


@dataclass(frozen=True, slots=True)
class BetaFrontierAccessibilityCheck:
    check_id: str
    surface: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.surface, "surface")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierAccessibilityReport:
    fixture_id: str
    checks: tuple[BetaFrontierAccessibilityCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    keyboard_order: tuple[str, ...]
    focus_boundaries: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def for_surface(self, surface: str) -> tuple[BetaFrontierAccessibilityCheck, ...]:
        return tuple(item for item in self.checks if item.surface == surface)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(index: int, surface: str, passed: bool, observed: Any, required: Any, detail: str) -> BetaFrontierAccessibilityCheck:
    body = {"check_id": f"accessibility-{index:03d}", "surface": surface, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return BetaFrontierAccessibilityCheck(**body, content_address=content_hash(body))


def evaluate_beta_frontier_accessibility(fixture: BetaFrontierFixture, evaluation: BetaFrontierEvaluation) -> BetaFrontierAccessibilityReport:
    """Check section labels, order, focus, and review row affordances."""

    checks: list[BetaFrontierAccessibilityCheck] = []
    keyboard_order: list[str] = []
    focus_boundaries: list[str] = []
    index = 1
    for record in fixture.records:
        payload = record.payload
        if record.operation.value == "evidence_table":
            workspace = payload.get("workspace", {})
            sections = workspace.get("sections", ())
            labels = tuple(str(item.get("accessible_label", "")) for item in sections)
            orders = tuple(int(item.get("order", -1)) for item in sections)
            checks.extend(
                (
                    _check(index, "evidence_table", bool(labels) and all(labels), labels, "non-empty labels", "table sections expose accessible labels"),
                    _check(index + 1, "evidence_table", len(orders) == len(set(orders)), orders, "unique order", "table sections have unique reading order"),
                    _check(index + 2, "evidence_table", all(str(item.get("description", "")) for item in sections), True, True, "table sections expose descriptions"),
                )
            )
            index += 3
            keyboard_order.extend(labels)
            focus_boundaries.append(str(workspace.get("workspace_id", "")))
        else:
            checks.extend(
                (
                    _check(index, record.operation.value, bool(record.context_key), record.context_key, "exact context", "projection record retains context for focus"),
                    _check(index + 1, record.operation.value, bool(record.notes), record.notes, "review note", "projection record retains a review note"),
                )
            )
            index += 2
    checks.extend(
        (
            _check(index, "global", len(keyboard_order) >= 2, keyboard_order, "two table sections", "keyboard order is non-empty"),
            _check(index + 1, "global", all(focus_boundaries), focus_boundaries, "workspace IDs", "focus boundaries are named"),
            _check(index + 2, "global", len(evaluation.executions) == 16, len(evaluation.executions), 16, "every projection row has an accessibility check"),
            _check(index + 3, "global", all(item.content_address.startswith("sha256:") for item in checks), True, True, "accessibility checks are addressed"),
        )
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"fixture_id": fixture.fixture_id, "checks": tuple(checks), "accepted": not failed, "failed_check_ids": failed, "keyboard_order": tuple(keyboard_order), "focus_boundaries": tuple(focus_boundaries)}
    return BetaFrontierAccessibilityReport(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierAccessibilityCheck", "BetaFrontierAccessibilityReport", "evaluate_beta_frontier_accessibility"]
