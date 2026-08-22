"""Content-addressed release bundle for context-alpha evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .cell_context_alpha_frontier_release import CellContextAlphaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierBundle:
    bundle_id: str
    fixture_id: str
    members: tuple[CellContextAlphaFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def required_count(self) -> int:
        return sum(item.required for item in self.members)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"required_count": self.required_count}


def build_cell_context_alpha_frontier_bundle(
    fixture: CellContextAlphaFrontierFixture,
    release: CellContextAlphaFrontierReleaseManifest,
    *members: Any,
) -> CellContextAlphaFrontierBundle:
    values = [
        CellContextAlphaFrontierBundleMember(
            "fixture", "fixture", fixture.content_address, True, "aggregate fixture"
        ),
        CellContextAlphaFrontierBundleMember(
            "release", "release", release.content_address, True, "bounded release manifest"
        ),
    ]
    values.extend(
        CellContextAlphaFrontierBundleMember(
            f"member-{index:02d}",
            type(member).__name__,
            str(getattr(member, "content_address", content_hash(member))),
            False,
            "derived review surface",
        )
        for index, member in enumerate(members, 1)
    )
    return CellContextAlphaFrontierBundle(
        "cell-context-alpha-frontier-bundle", fixture.fixture_id, tuple(values), release.publishable
    )


__all__ = [
    "CellContextAlphaFrontierBundle",
    "CellContextAlphaFrontierBundleMember",
    "build_cell_context_alpha_frontier_bundle",
]
