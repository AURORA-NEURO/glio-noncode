"""Content-addressed comparison of two control frontier evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierDeltaRow:
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
class ControlFrontierDeltaReport:
    before_fixture_id: str
    after_fixture_id: str
    rows: tuple[ControlFrontierDeltaRow, ...]
    changed_count: int
    added_count: int
    removed_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compare_control_frontier_evaluations(before: ControlFrontierEvaluation, after: ControlFrontierEvaluation) -> ControlFrontierDeltaReport:
    """Compare row identity and observed outcomes without comparing payloads."""

    before_by_id = {item.record_id: item for item in before.executions}
    after_by_id = {item.record_id: item for item in after.executions}
    rows = []
    for record_id in sorted(set(before_by_id) | set(after_by_id)):
        left = before_by_id.get(record_id)
        right = after_by_id.get(record_id)
        body = {
            "record_id": record_id,
            "before_state": left.state.value if left else None,
            "after_state": right.state.value if right else None,
            "before_issues": left.issue_codes if left else (),
            "after_issues": right.issue_codes if right else (),
            "before_accepted": left.accepted if left else None,
            "after_accepted": right.accepted if right else None,
        }
        body["changed"] = body["before_state"] != body["after_state"] or body["before_issues"] != body["after_issues"] or body["before_accepted"] != body["after_accepted"]
        rows.append(ControlFrontierDeltaRow(**body, content_address=content_hash(body)))
    added = len(set(after_by_id) - set(before_by_id))
    removed = len(set(before_by_id) - set(after_by_id))
    body = {
        "before_fixture_id": before.fixture_id,
        "after_fixture_id": after.fixture_id,
        "rows": tuple(rows),
        "changed_count": sum(item.changed for item in rows),
        "added_count": added,
        "removed_count": removed,
        "accepted": all(item.content_address.startswith("sha256:") for item in rows),
    }
    return ControlFrontierDeltaReport(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierDeltaReport", "ControlFrontierDeltaRow", "compare_control_frontier_evaluations"]
