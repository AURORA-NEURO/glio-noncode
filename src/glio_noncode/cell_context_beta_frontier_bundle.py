"""Content-addressed bundle inventory for release and review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .cell_context_beta_frontier_release import CellContextBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierBundle:
    bundle_id: str
    fixture_id: str
    members: tuple[CellContextBetaFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.bundle_id or not self.members:
            raise ValueError("beta bundle is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def required_count(self) -> int:
        return sum(item.required for item in self.members)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"required_count": self.required_count}


def build_cell_context_beta_frontier_bundle(
    fixture: CellContextBetaFrontierFixture,
    release: CellContextBetaFrontierReleaseManifest,
    *members: Any,
) -> CellContextBetaFrontierBundle:
    values = [
        CellContextBetaFrontierBundleMember(
            "fixture", "fixture", fixture.content_address, True, "aggregate fixture"
        ),
        CellContextBetaFrontierBundleMember(
            "release", "release", release.content_address, True, "release policy"
        ),
    ]
    for index, member in enumerate(members, 1):
        address = str(getattr(member, "content_address", content_hash(member)))
        values.append(
            CellContextBetaFrontierBundleMember(
                f"member-{index:02d}",
                type(member).__name__,
                address,
                False,
                "derived review surface",
            )
        )
    return CellContextBetaFrontierBundle(
        "cell-context-beta-frontier-bundle", fixture.fixture_id, tuple(values), release.publishable
    )


__all__ = [
    "CellContextBetaFrontierBundle",
    "CellContextBetaFrontierBundleMember",
    "build_cell_context_beta_frontier_bundle",
]
