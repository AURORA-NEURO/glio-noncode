"""Accessible labels and plain-text fallbacks for release reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_report import CohortAlphaFrontierReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAccessibilityLabel:
    element_id: str
    label: str
    description: str
    reading_order: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAccessibilityReport:
    labels: tuple[CohortAlphaFrontierAccessibilityLabel, ...]
    plain_text: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_accessibility(
    report: CohortAlphaFrontierReport,
) -> CohortAlphaFrontierAccessibilityReport:
    labels = tuple(
        CohortAlphaFrontierAccessibilityLabel(
            section.section_id,
            section.title,
            section.body,
            section.order,
            content_hash(
                {
                    "id": section.section_id,
                    "label": section.title,
                    "description": section.body,
                    "order": section.order,
                },
                prefix="alpha-accessibility",
            ),
        )
        for section in report.sections
        if section.visible
    )
    plain = "\n".join(f"{item.reading_order}. {item.label}: {item.description}" for item in labels)
    expected_visible_count = sum(section.visible for section in report.sections)
    complete_order = tuple(item.reading_order for item in labels) == tuple(
        range(1, len(labels) + 1)
    )
    accepted = len(labels) == expected_visible_count and complete_order
    body = {
        "labels": labels,
        "plain": plain,
        "expected_visible_count": expected_visible_count,
        "accepted": accepted,
    }
    return CohortAlphaFrontierAccessibilityReport(
        labels, plain, accepted, content_hash(body, prefix="alpha-accessibility-report")
    )


__all__ = [
    "CohortAlphaFrontierAccessibilityLabel",
    "CohortAlphaFrontierAccessibilityReport",
    "build_cohort_alpha_frontier_accessibility",
]
