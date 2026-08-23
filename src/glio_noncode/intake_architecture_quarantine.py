"""Lineage-preserving quarantine controls for malformed or ambiguous input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureCase, IntakeArchitectureState, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitectureQuarantineItem:
    item_id: str
    case_id: str
    issue_codes: tuple[str, ...]
    input_address: str
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "case_id": self.case_id,
            "issue_codes": list(self.issue_codes),
            "input_address": self.input_address,
            "disposition": self.disposition,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class IntakeArchitectureQuarantineReport:
    report_id: str
    items: tuple[IntakeArchitectureQuarantineItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, "items": [item.to_dict() for item in self.items], "accepted": self.accepted, "content_address": self.content_address}


def build_intake_quarantine(cases: tuple[IntakeArchitectureCase, ...]) -> IntakeArchitectureQuarantineReport:
    items = []
    for case in cases:
        if case.scenario.value == "positive":
            continue
        issue = case.expected_issue_codes or ("review_required",)
        body = {"item_id": f"quarantine:{case.case_id}", "case_id": case.case_id, "issue_codes": issue, "input_address": addressed(case.payload, "quarantine-input"), "disposition": "held_for_review"}
        items.append(IntakeArchitectureQuarantineItem(**body, content_address=addressed(body, "quarantine-item")))
    body = {"report_id": "intake-quarantine-d01", "items": tuple(items), "accepted": all(item.disposition == "held_for_review" for item in items)}
    return IntakeArchitectureQuarantineReport(**body, content_address=addressed(body, "quarantine-report"))


__all__ = ["IntakeArchitectureQuarantineItem", "IntakeArchitectureQuarantineReport", "build_intake_quarantine"]
