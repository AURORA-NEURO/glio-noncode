"""Explicit migration table; no implicit field renaming is performed."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseContractMigration:
    from_version: str
    to_version: str
    changes: tuple[str, ...]
    reversible: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def current_evidence_release_migration() -> EvidenceReleaseContractMigration:
    body = {"from_version": "evidence-release-schema-v0", "to_version": "evidence-release-schema-v1", "changes": ("add capability", "add plane to checks", "require source receipt"), "reversible": False}
    return EvidenceReleaseContractMigration(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseContractMigration", "current_evidence_release_migration"]
