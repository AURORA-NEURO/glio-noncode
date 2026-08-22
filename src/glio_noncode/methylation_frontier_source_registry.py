"""Declared public source registry for the methylation frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_public_data import MethylationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierSourceEntry:
    source_id: str
    uri: str
    source_version: str
    checksum: str
    context_key: str
    declared_role: str
    retrieval_policy: str
    public_aggregate: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.uri.startswith("https://") or not self.source_version:
            raise ValidationError("source entry identity is invalid")
        if not self.checksum or not self.context_key or not self.declared_role:
            raise ValidationError("source entry receipt is incomplete")
        if not self.public_aggregate:
            raise ValidationError("source entry must be aggregate")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierSourceRegistry:
    entries: tuple[MethylationFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValidationError("source registry cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, source_id: str) -> MethylationFrontierSourceEntry:
        for entry in self.entries:
            if entry.source_id == source_id:
                return entry
        raise KeyError(source_id)

    def for_context(self, context_key: str) -> tuple[MethylationFrontierSourceEntry, ...]:
        return tuple(entry for entry in self.entries if entry.context_key == context_key)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_methylation_frontier_source_registry(
    fixture: MethylationFrontierFixture,
) -> MethylationFrontierSourceRegistry:
    entries = tuple(
        MethylationFrontierSourceEntry(
            source_id=source.source_id,
            uri=source.uri,
            source_version=source.source_version,
            checksum=source.checksum,
            context_key=source.context_key,
            declared_role=(
                "methylation measurement"
                if "methylation" in source.source_id
                else "reference and motif context"
            ),
            retrieval_policy="public aggregate receipt; preserve version and checksum",
            public_aggregate=source.public_aggregate,
        )
        for source in fixture.sources
    )
    return MethylationFrontierSourceRegistry(
        entries,
        len(entries) == 4
        and all(entry.context_key == fixture.context_key for entry in entries)
        and all(entry.public_aggregate for entry in entries),
    )


__all__ = [
    "MethylationFrontierSourceEntry",
    "MethylationFrontierSourceRegistry",
    "build_methylation_frontier_source_registry",
]
