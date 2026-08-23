"""Artifact inventory for workbench release outputs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseArtifactInventory:
    artifacts: tuple[dict[str, Any], ...]
    complete: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_artifact_inventory(fixture: Any, evaluation: Any, run_id: str) -> WorkbenchReleaseArtifactInventory:
    artifacts = (("fixture", fixture.content_address), ("evaluation", evaluation.content_address), ("run", content_hash({"run_id": run_id})), ("sources", tuple(source.content_address for source in fixture.sources)))
    rows = tuple({"artifact_type": kind, "content_address": address, "required": True} for kind, address in artifacts)
    def closed(value: Any) -> bool:
        if isinstance(value, (list, tuple)):
            return bool(value) and all(str(item).startswith("sha256:") for item in value)
        return str(value).startswith("sha256:")
    body = {"artifacts": rows, "complete": all(closed(row["content_address"]) for row in rows)}
    return WorkbenchReleaseArtifactInventory(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseArtifactInventory", "build_workbench_release_artifact_inventory"]
