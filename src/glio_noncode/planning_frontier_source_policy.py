"""Source receipt policy for public aggregate planning."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class SourcePolicyDecision:
    source_id: str
    uri: str
    public: bool
    https: bool
    accepted: bool
    reason: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def decide_source(source_id: str, uri: str, public: bool = True) -> SourcePolicyDecision:
    https = str(uri).startswith("https://")
    accepted = bool(source_id and public and https)
    body = {"source_id": source_id, "uri": uri, "public": public, "https": https, "accepted": accepted, "reason": "public HTTPS receipt" if accepted else "source receipt policy failed"}
    return SourcePolicyDecision(**body, content_address=content_hash(body, prefix="source-policy"))
__all__ = ["SourcePolicyDecision", "decide_source"]
