"""Declared source registry for the C09-C12 public aggregate plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierSourceEntry:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    context_key: str
    retrieval_policy: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or not self.title
            or not self.uri.startswith("https://")
            or not self.release
            or not self.scope
            or not self.context_key
            or not self.retrieval_policy
        ):
            raise ValidationError("source entry is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierSourceRegistry:
    entries: tuple[ChromatinAlphaFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.entries) != 5:
            raise ValidationError("source registry requires five entries")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, source_id: str) -> ChromatinAlphaFrontierSourceEntry:
        for entry in self.entries:
            if entry.source_id == source_id:
                return entry
        raise KeyError(source_id)

    def for_context(self, context_key: str) -> tuple[ChromatinAlphaFrontierSourceEntry, ...]:
        return tuple(entry for entry in self.entries if entry.context_key == context_key)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_source_registry(
    fixture: ChromatinAlphaFrontierFixture,
) -> ChromatinAlphaFrontierSourceRegistry:
    entries = tuple(
        ChromatinAlphaFrontierSourceEntry(
            source_id=source.source_id,
            title=source.title,
            uri=source.uri,
            source_kind=source.source_kind,
            release=source.release,
            scope=source.scope,
            context_key=source.context_key,
            retrieval_policy=(
                "public aggregate receipt; preserve source release and content address"
            ),
        )
        for source in fixture.sources
    )
    return ChromatinAlphaFrontierSourceRegistry(
        entries,
        all(entry.context_key == fixture.context_key for entry in entries)
        and all(entry.uri.startswith("https://") for entry in entries),
    )


__all__ = [
    "ChromatinAlphaFrontierSourceEntry",
    "ChromatinAlphaFrontierSourceRegistry",
    "build_chromatin_alpha_frontier_source_registry",
]
