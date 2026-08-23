"""Read-only query views over sanitized D02 receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import (
    StructuralArchitectureEvaluation,
    StructuralArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureQueryResult:
    query: str
    matched_case_ids: tuple[str, ...]
    matched_operation_ids: tuple[str, ...]
    states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "matched_case_ids": list(self.matched_case_ids),
            "matched_operation_ids": list(self.matched_operation_ids),
            "states": list(self.states),
            "issue_codes": list(self.issue_codes),
            "content_address": self.content_address,
        }


def query_structural_architecture(
    evaluation: StructuralArchitectureEvaluation,
    *,
    operation_id: str | None = None,
    state: StructuralArchitectureState | None = None,
    issue_code: str | None = None,
) -> StructuralArchitectureQueryResult:
    """Filter receipts without returning their original payloads."""

    query_parts = []
    if operation_id:
        query_parts.append(f"operation={operation_id}")
    if state:
        query_parts.append(f"state={state.value}")
    if issue_code:
        query_parts.append(f"issue={issue_code}")
    query = " AND ".join(query_parts) or "all"
    matches = tuple(
        item
        for item in evaluation.receipts
        if (operation_id is None or item.operation_id == operation_id)
        and (state is None or item.observed_state is state)
        and (issue_code is None or issue_code in item.observed_issue_codes)
    )
    body = {
        "query": query,
        "matched_case_ids": tuple(item.case_id for item in matches),
        "matched_operation_ids": tuple(sorted({item.operation_id for item in matches})),
        "states": tuple(sorted({item.observed_state.value for item in matches})),
        "issue_codes": tuple(
            sorted({code for item in matches for code in item.observed_issue_codes})
        ),
    }
    return StructuralArchitectureQueryResult(
        **body, content_address=addressed(body, "structural-query")
    )


__all__ = ["StructuralArchitectureQueryResult", "query_structural_architecture"]
