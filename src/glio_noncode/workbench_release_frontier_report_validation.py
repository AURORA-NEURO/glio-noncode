"""Deep report validation receipt for workbench release review.

The plane preserves ordered public observations and a content address. It can be
replayed independently of the full runtime and never changes the source fixture.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseReportValidation:
    observations: tuple[dict[str, Any], ...]
    accepted: bool
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def observation_count(self) -> int:
        return len(self.observations)


def build_workbench_release_report_validation(values: Iterable[Any] = (), *, require_non_empty: bool = True) -> WorkbenchReleaseReportValidation:
    rows = tuple(
        {
            "sequence": index,
            "value": jsonable(value),
            "content_address": content_hash(jsonable(value)),
        }
        for index, value in enumerate(tuple(values), start=1)
    )
    accepted = bool(rows) if require_non_empty else True
    next_action = "retain receipt" if accepted else "route for review"
    body = {"observations": rows, "accepted": accepted, "next_action": next_action}
    return WorkbenchReleaseReportValidation(**body, content_address=content_hash(body))


def validate_workbench_release_report_validation(receipt: WorkbenchReleaseReportValidation) -> bool:
    if not receipt.content_address.startswith("sha256:"):
        return False
    if receipt.accepted is False and receipt.next_action != "route for review":
        return False
    return all(
        isinstance(row.get("content_address"), str)
        and row["content_address"].startswith("sha256:")
        for row in receipt.observations
    )


__all__ = ["WorkbenchReleaseReportValidation", "build_workbench_release_report_validation", "validate_workbench_release_report_validation"]
