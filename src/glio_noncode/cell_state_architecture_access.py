"""Artifact access rules for public aggregate D08 outputs."""

from __future__ import annotations

from .cell_state_architecture_contracts import CellStateArchitectureArtifact, addressed


def cell_state_architecture_access_policy(
    artifacts: tuple[CellStateArchitectureArtifact, ...],
) -> dict[str, object]:
    decisions = tuple(
        {
            "artifact_id": item.artifact_id,
            "visibility": item.visibility,
            "review_safe": item.review_safe,
            "grant": item.visibility == "public_aggregate" and item.review_safe,
            "content_address": item.content_address,
        }
        for item in artifacts
    )
    body = {
        "decisions": decisions,
        "accepted": len(decisions) == 6 and all(item["grant"] for item in decisions),
    }
    return body | {"content_address": addressed(body, "cell-state-access")}


__all__ = ["cell_state_architecture_access_policy"]
