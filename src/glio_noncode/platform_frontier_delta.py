"""Outcome delta comparison for two platform evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierDeltaRow:
    record_id: str
    before_state: str | None
    after_state: str | None
    before_issues: tuple[str, ...]
    after_issues: tuple[str, ...]
    before_accepted: bool | None
    after_accepted: bool | None
    changed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierDeltaReport:
    before_fixture_id: str
    after_fixture_id: str
    rows: tuple[PlatformFrontierDeltaRow, ...]
    changed_count: int
    added_count: int
    removed_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compare_platform_frontier_evaluations(before: PlatformFrontierEvaluation, after: PlatformFrontierEvaluation) -> PlatformFrontierDeltaReport:
    left = {item.record_id: item for item in before.executions}
    right = {item.record_id: item for item in after.executions}
    rows = []
    for record_id in sorted(set(left) | set(right)):
        old, new = left.get(record_id), right.get(record_id)
        body = {"record_id": record_id, "before_state": old.state.value if old else None, "after_state": new.state.value if new else None, "before_issues": old.issue_codes if old else (), "after_issues": new.issue_codes if new else (), "before_accepted": old.accepted if old else None, "after_accepted": new.accepted if new else None}
        body["changed"] = body["before_state"] != body["after_state"] or body["before_issues"] != body["after_issues"] or body["before_accepted"] != body["after_accepted"]
        rows.append(PlatformFrontierDeltaRow(**body, content_address=content_hash(body)))
    body = {"before_fixture_id": before.fixture_id, "after_fixture_id": after.fixture_id, "rows": tuple(rows), "changed_count": sum(item.changed for item in rows), "added_count": len(set(right) - set(left)), "removed_count": len(set(left) - set(right)), "accepted": all(item.content_address.startswith("sha256:") for item in rows)}
    return PlatformFrontierDeltaReport(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierDeltaReport", "PlatformFrontierDeltaRow", "compare_platform_frontier_evaluations"]
