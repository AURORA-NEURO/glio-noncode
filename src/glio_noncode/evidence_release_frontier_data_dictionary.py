"""Field dictionary for public evidence-release artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseDataDictionary:
    fields: tuple[dict[str, Any], ...]
    version: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def default_evidence_release_data_dictionary() -> EvidenceReleaseDataDictionary:
    fields = (("context_key", "string", "exact cohort and treatment boundary"), ("source_ids", "array[string]", "public receipt joins"), ("payload", "object", "operation input projection"), ("expected_state", "enum", "fixture contract"), ("issue_codes", "array[string]", "review reason vocabulary"), ("content_address", "sha256 string", "immutable receipt"), ("signature", "HMAC receipt", "verification output; no key material"))
    body = {"fields": fields, "version": "evidence-release-data-dictionary-v1"}
    return EvidenceReleaseDataDictionary(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseDataDictionary", "default_evidence_release_data_dictionary"]
