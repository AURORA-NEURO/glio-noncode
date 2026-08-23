"""Access manifest for local public aggregate coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationRuntime, addressed


@dataclass(frozen=True, slots=True)
class CoordinationAccessManifest:
    manifest_id: str
    scope: str
    network_allowed: bool
    private_fields_allowed: bool
    filesystem_classes: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "scope": self.scope,
            "network_allowed": self.network_allowed,
            "private_fields_allowed": self.private_fields_allowed,
            "filesystem_classes": self.filesystem_classes,
            "allowed_operations": self.allowed_operations,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def build_coordination_access_manifest(runtime: CoordinationRuntime) -> CoordinationAccessManifest:
    body = {
        "manifest_id": f"{runtime.run_id}:access",
        "scope": "public_aggregate",
        "network_allowed": False,
        "private_fields_allowed": False,
        "filesystem_classes": ("checked_in_fixture", "temporary_projection", "addressed_release"),
        "allowed_operations": tuple(node.operation_id for node in runtime.plan.nodes),
        "accepted": runtime.state.value == "accepted" and not runtime.tools.tools[0].network_allowed,
    }
    return CoordinationAccessManifest(**body, content_address=addressed(body, "coordination-access"))


__all__ = ["CoordinationAccessManifest", "build_coordination_access_manifest"]
