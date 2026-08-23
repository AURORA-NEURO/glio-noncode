"""Change-control record for fixture and policy updates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierChangeControl:
    change_id: str
    previous_version: str
    proposed_version: str
    changed_surfaces: tuple[str, ...]
    reviewer_roles: tuple[str, ...]
    migration_required: bool
    accepted: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_lifecycle_beta_frontier_change_control() -> LifecycleBetaFrontierChangeControl:
    body = {"change_id": "lifecycle-beta-frontier-change-2026-08", "previous_version": "2026.08.d14-c01-c04.v1", "proposed_version": "2026.08.d14-c05-c12.v1", "changed_surfaces": ("tier_adjudication", "provenance_lineage", "uncertainty_ledger", "review_routing", "blinded_adjudication", "comment_change_log", "release_decision", "evidence_delta"), "reviewer_roles": ("domain_expert", "data_provenance", "computational_methods"), "migration_required": False, "accepted": True, "reason": "new aggregate records are additive and preserve prior receipts"}
    return LifecycleBetaFrontierChangeControl(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierChangeControl", "default_lifecycle_beta_frontier_change_control"]
