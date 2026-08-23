"""Rollback and supersession plan for platform release artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_release import PlatformFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierRollbackAction:
    action_id: str
    trigger: str
    target_release_id: str
    preserve_addresses: tuple[str, ...]
    requires_review: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierRollbackPlan:
    current_release_id: str
    actions: tuple[PlatformFrontierRollbackAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_rollback_plan(release: PlatformFrontierReleaseManifest, *, prior_release_id: str = "none") -> PlatformFrontierRollbackPlan:
    body = {"action_id": "supersede", "trigger": "material receipt or policy change", "target_release_id": prior_release_id, "preserve_addresses": (release.content_address, release.evaluation_address, release.quality_address), "requires_review": True}
    action = PlatformFrontierRollbackAction(**body, content_address=content_hash(body))
    return PlatformFrontierRollbackPlan(release.release_id, (action,), bool(release.release_id), content_hash((action,)))


__all__ = ["PlatformFrontierRollbackAction", "PlatformFrontierRollbackPlan", "build_platform_frontier_rollback_plan"]
