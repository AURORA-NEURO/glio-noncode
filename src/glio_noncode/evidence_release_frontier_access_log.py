"""Public artifact access log that excludes private request values."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseAccessLog:
    events: tuple[dict[str, Any], ...]
    public_only: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_access_log(artifacts: Iterable[str]) -> EvidenceReleaseAccessLog:
    events = tuple({"sequence": index, "artifact_address": address, "access": "public aggregate"} for index, address in enumerate(artifacts, start=1))
    body = {"events": events, "public_only": all(item["access"] == "public aggregate" for item in events)}
    return EvidenceReleaseAccessLog(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseAccessLog", "build_evidence_release_access_log"]
