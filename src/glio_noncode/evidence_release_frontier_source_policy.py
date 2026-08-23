"""Source receipt policy for public aggregate provenance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseSourcePolicy:
    required_source_count: int
    required_scheme: str
    accepted_scopes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_release_source_policy() -> EvidenceReleaseSourcePolicy:
    body = {"required_source_count": 5, "required_scheme": "https", "accepted_scopes": ("public literature and citation index", "public indexed article metadata", "public aggregate disease and genomic reference", "public functional assay reference", "public interoperability and data-use reference")}
    return EvidenceReleaseSourcePolicy(**body, content_address=content_hash(body))


def evaluate_evidence_release_sources(fixture: Any, policy: EvidenceReleaseSourcePolicy | None = None) -> bool:
    policy = policy or default_evidence_release_source_policy()
    return len(fixture.sources) == policy.required_source_count and all(source.uri.startswith(policy.required_scheme + "://") and source.scope in policy.accepted_scopes for source in fixture.sources)


__all__ = ["EvidenceReleaseSourcePolicy", "default_evidence_release_source_policy", "evaluate_evidence_release_sources"]
