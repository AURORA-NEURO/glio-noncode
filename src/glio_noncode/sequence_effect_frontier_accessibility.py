"""Accessibility projection checks for sequence-effect review surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .sequence_effect_frontier_views import SequenceEffectView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectAccessibilityReport:
    accepted: bool
    criteria: tuple[dict[str, Any], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"accepted": self.accepted, "criteria": self.criteria}),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_sequence_effect_accessibility(
    fixture: SequenceEffectFixture, view: SequenceEffectView
) -> SequenceEffectAccessibilityReport:
    criteria = tuple(
        {"criterion_id": criterion_id, "passed": passed, "detail": detail}
        for criterion_id, passed, detail in (
            ("context-label", bool(view.context_key), "context remains visible"),
            (
                "role-label",
                all(item.role in {"positive", "control"} for item in view.entries),
                "role is explicit",
            ),
            ("state-label", all(item.state for item in view.entries), "state is explicit"),
            (
                "action-label",
                all(item.action for item in view.entries),
                "review action is explicit",
            ),
            (
                "pagination-bound",
                len(view.entries) <= len(fixture.records),
                "view does not duplicate records",
            ),
            ("source-summary", bool(view.source_ids), "source summary is available"),
            (
                "control-visibility",
                sum(item.role == "control" for item in view.entries) == 12,
                "controls remain visible",
            ),
            (
                "address-label",
                all(item.content_address.startswith("sha256:") for item in view.entries),
                "rows are addressable",
            ),
        )
    )
    return SequenceEffectAccessibilityReport(all(item["passed"] for item in criteria), criteria)


__all__ = ["SequenceEffectAccessibilityReport", "audit_sequence_effect_accessibility"]
