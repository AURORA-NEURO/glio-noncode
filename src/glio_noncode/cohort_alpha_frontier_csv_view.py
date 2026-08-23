"""CSV projection for review-safe result rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCsvView:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    text: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_csv_view(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierCsvView:
    header = ("record_id", "operation", "state", "disposition", "content_address")
    rows = tuple((row.record_id, row.operation, row.observed_state.value, policy.for_record(row.record_id).disposition.value, row.content_address) for row in evaluation.rows)
    text = "\n".join((",".join(header), *(",".join(row) for row in rows))) + "\n"
    return CohortAlphaFrontierCsvView(header, rows, text, len(rows) == 16 and all(len(row) == len(header) for row in rows), content_hash({"header": header, "rows": rows}, prefix="alpha-csv-view"))


__all__ = ["CohortAlphaFrontierCsvView", "build_cohort_alpha_frontier_csv_view"]
