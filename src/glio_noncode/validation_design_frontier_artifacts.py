"""Artifact inventory for a reproducible validation-design run."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignArtifactInventory:
    artifacts: tuple[dict[str, Any], ...]
    complete: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_artifact_inventory(fixture: Any, evaluation: Any, run_id: str) -> ValidationDesignArtifactInventory:
    values = (("fixture", fixture.content_address), ("evaluation", evaluation.content_address), ("run", content_hash({"run_id": run_id})), ("sources", tuple(source.content_address for source in fixture.sources)), ("rows", tuple(row.content_address for row in evaluation.executions)))
    rows = tuple({"artifact_type": name, "content_address": address, "required": True} for name, address in values)
    def closed(value: Any) -> bool: return all(str(item).startswith("sha256:") for item in value) if isinstance(value, (list, tuple)) else str(value).startswith("sha256:")
    body = {"artifacts": rows, "complete": all(closed(row["content_address"]) for row in rows)}
    return ValidationDesignArtifactInventory(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignArtifactInventory", "build_validation_design_artifact_inventory"]
