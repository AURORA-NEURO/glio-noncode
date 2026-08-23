"""Change-control contract for platform fixture and schema edits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PLATFORM_FRONTIER_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierChangeControl:
    change_id: str
    current_version: str
    required_review: tuple[str, ...]
    immutable_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_platform_frontier_change_control() -> PlatformFrontierChangeControl:
    body = {"change_id": "platform-frontier-change-control", "current_version": PLATFORM_FRONTIER_VERSION, "required_review": ("fixture_version", "state_vocabulary", "issue_codes", "boundary", "schema_fields"), "immutable_fields": ("record_id", "content_address", "source_id"), "accepted": True}
    return PlatformFrontierChangeControl(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierChangeControl", "default_platform_frontier_change_control"]
