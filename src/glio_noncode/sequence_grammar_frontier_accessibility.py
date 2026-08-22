"""Accessibility shape checks for sequence grammar review views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .sequence_grammar_frontier_views import SequenceGrammarView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarAccessibilityReport:
    accepted: bool
    checks: tuple[dict[str, Any], ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("accessibility report requires checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "check_count": len(self.checks),
            "checks": jsonable(self.checks),
            "content_address": self.content_address,
        }


def audit_sequence_grammar_accessibility(
    fixture: SequenceGrammarFixture, view: SequenceGrammarView
) -> SequenceGrammarAccessibilityReport:
    checks = (
        {
            "check_id": "labels",
            "passed": all(entry.operation.value and entry.state.value for entry in view.entries),
            "detail": "operation and state labels are present",
        },
        {
            "check_id": "priority",
            "passed": all(entry.priority >= 1 for entry in view.entries),
            "detail": "review priority is explicit",
        },
        {
            "check_id": "address",
            "passed": all(entry.result_address.startswith("sha256:") for entry in view.entries),
            "detail": "result links are stable",
        },
        {
            "check_id": "context",
            "passed": bool(fixture.context_key),
            "detail": "context is available to a review consumer",
        },
        {
            "check_id": "control-count",
            "passed": view.review_count == 12,
            "detail": "control review count is visible",
        },
    )
    return SequenceGrammarAccessibilityReport(
        all(item["passed"] for item in checks), checks, fixture.fixture_id
    )


__all__ = ["SequenceGrammarAccessibilityReport", "audit_sequence_grammar_accessibility"]
