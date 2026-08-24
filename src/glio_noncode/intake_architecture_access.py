"""Aggregate-only access manifest for D01 runtime artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureRuntime, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitectureAccessEntry:
    artifact_id: str
    scope: str
    read_allowed: bool
    write_allowed: bool
    network_allowed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "scope": self.scope,
            "read_allowed": self.read_allowed,
            "write_allowed": self.write_allowed,
            "network_allowed": self.network_allowed,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class IntakeArchitectureAccessManifest:
    manifest_id: str
    entries: tuple[IntakeArchitectureAccessEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "entries": [item.to_dict() for item in self.entries],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def build_intake_architecture_access_manifest(
    runtime: IntakeArchitectureRuntime,
) -> IntakeArchitectureAccessManifest:
    entries = []
    for artifact in runtime.artifacts:
        body = {
            "artifact_id": artifact.artifact_id,
            "scope": "public_aggregate",
            "read_allowed": True,
            "write_allowed": False,
            "network_allowed": False,
        }
        entries.append(
            IntakeArchitectureAccessEntry(
                **body, content_address=addressed(body, "intake-access-entry")
            )
        )
    body = {
        "manifest_id": "intake-access-d02",
        "entries": tuple(entries),
        "accepted": len(entries) == 8
        and all(
            item.scope == "public_aggregate" and not item.write_allowed and not item.network_allowed
            for item in entries
        ),
    }
    return IntakeArchitectureAccessManifest(
        **body, content_address=addressed(body, "intake-access")
    )


__all__ = [
    "IntakeArchitectureAccessEntry",
    "IntakeArchitectureAccessManifest",
    "build_intake_architecture_access_manifest",
]
