"""Explicit hash helpers for replay-sensitive planning dimensions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class DeterministicAddress:
    namespace: str
    dimensions: tuple[tuple[str, Any], ...]
    address: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def address_dimensions(namespace: str, **dimensions: Any) -> DeterministicAddress:
    values = tuple(sorted((str(key), value) for key, value in dimensions.items()))
    address = content_hash({"namespace": namespace, "dimensions": values}, prefix=namespace)
    body = {"namespace": namespace, "dimensions": values, "address": address}
    return DeterministicAddress(**body, content_address=content_hash(body, prefix="deterministic-address"))
__all__ = ["DeterministicAddress", "address_dimensions"]
