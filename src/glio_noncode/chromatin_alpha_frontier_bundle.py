"""Portable content-addressed result bundle for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierFixture
from .chromatin_alpha_frontier_release import ChromatinAlphaFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    record_count: int
    result_addresses: tuple[str, ...]
    root_address: str
    accepted: bool

    def __post_init__(self) -> None:
        if (
            not self.bundle_id
            or not self.fixture_id
            or not self.release_id
            or not self.result_addresses
        ):
            raise ValidationError("bundle is incomplete")
        if not self.root_address.startswith("sha256:"):
            raise ValidationError("bundle root must be addressed")

    @property
    def content_address(self) -> str:
        return self.root_address

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_bundle(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
    release: ChromatinAlphaFrontierReleaseManifest,
) -> ChromatinAlphaFrontierBundle:
    addresses = tuple(item.adapter.content_address for item in evaluation.records)
    body = {
        "fixture_id": fixture.fixture_id,
        "release_id": release.release_id,
        "addresses": addresses,
    }
    return ChromatinAlphaFrontierBundle(
        bundle_id="bundle:chromatin-alpha-frontier",
        fixture_id=fixture.fixture_id,
        release_id=release.release_id,
        record_count=len(addresses),
        result_addresses=addresses,
        root_address=content_hash(body),
        accepted=release.accepted
        and len(addresses) == len(fixture.records)
        and all(address.startswith("sha256:") for address in addresses),
    )


__all__ = ["ChromatinAlphaFrontierBundle", "build_chromatin_alpha_frontier_bundle"]
