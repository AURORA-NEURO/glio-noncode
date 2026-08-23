"""Independent workbench runbook assurance plane.

This module keeps one workbench concern independently addressable. Its receipt
preserves ordered observations, content addresses, count boundaries, and an
explicit next action. It is deterministic over supplied public aggregate inputs.
It does not mutate the fixture or infer a missing review decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseWorkbenchRunbook:
    count: int
    accepted: bool
    observations: tuple[dict[str, Any], ...]
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def closed(self) -> bool:
        return self.accepted and self.content_address.startswith("sha256:")


def build_workbench_release_workbench_runbook(values: Iterable[Any] = (), *, required: int = 1) -> WorkbenchReleaseWorkbenchRunbook:
    """Build an immutable receipt for this assurance plane."""
    materialized = tuple(values)
    observations = tuple(
        {
            "sequence": index,
            "value": jsonable(value),
            "address": content_hash(jsonable(value)),
        }
        for index, value in enumerate(materialized, start=1)
    )
    count = len(observations)
    accepted = count >= required
    next_action = "retain receipt" if accepted else "route for review"
    body = {
        "count": count,
        "accepted": accepted,
        "observations": observations,
        "next_action": next_action,
    }
    return WorkbenchReleaseWorkbenchRunbook(**body, content_address=content_hash(body))


def validate_workbench_release_workbench_runbook(receipt: WorkbenchReleaseWorkbenchRunbook, *, expected: int | None = None) -> bool:
    """Validate closure without changing the receipt."""
    if not receipt.closed:
        return False
    if expected is not None and receipt.count != expected:
        return False
    return all(
        isinstance(item.get("address"), str)
        and item["address"].startswith("sha256:")
        for item in receipt.observations
    )


def summarize_workbench_release_workbench_runbook(receipt: WorkbenchReleaseWorkbenchRunbook) -> Mapping[str, Any]:
    """Return the stable handoff projection."""
    return {
        "count": receipt.count,
        "accepted": receipt.accepted,
        "closed": receipt.closed,
        "next_action": receipt.next_action,
        "content_address": receipt.content_address,
    }


__all__ = ["WorkbenchReleaseWorkbenchRunbook", "validate_workbench_release_workbench_runbook", "build_workbench_release_workbench_runbook", "summarize_workbench_release_workbench_runbook"]
