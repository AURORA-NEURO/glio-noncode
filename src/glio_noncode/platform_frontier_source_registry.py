"""Source registry for public platform aggregate receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierSourceRegistry:
    fixture_id: str
    source_ids: tuple[str, ...]
    uri_by_source: dict[str, str]
    all_https: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_source_registry(fixture: PlatformFrontierFixture) -> PlatformFrontierSourceRegistry:
    uri_by_source = {item.source_id: item.uri for item in fixture.sources}
    body = {"fixture_id": fixture.fixture_id, "source_ids": tuple(uri_by_source), "uri_by_source": uri_by_source, "all_https": all(item.startswith("https://") for item in uri_by_source.values()), "accepted": len(uri_by_source) == len(fixture.sources)}
    return PlatformFrontierSourceRegistry(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierSourceRegistry", "build_platform_frontier_source_registry"]
