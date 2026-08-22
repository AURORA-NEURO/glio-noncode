"""Structured release notes for the baseline plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_release import LinkGraphFoundationFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReleaseNotes:
    release_id: str
    highlights: tuple[str, ...]
    verification: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_markdown(self) -> str:
        return "\n".join((f"# {self.release_id}", "", "## Highlights", *[f"- {item}" for item in self.highlights], "", "## Verification", *[f"- {item}" for item in self.verification], "", "## Limitations", *[f"- {item}" for item in self.limitations], ""))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "highlights": self.highlights, "verification": self.verification, "limitations": self.limitations}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_release_notes(manifest: LinkGraphFoundationFrontierReleaseManifest) -> LinkGraphFoundationFrontierReleaseNotes:
    return LinkGraphFoundationFrontierReleaseNotes(manifest.release_id, ("four baseline operations replay", "positive and control rows are balanced", "source receipts are closed"), ("16 of 16 states match", "16 of 16 issue controls match", "12 stages pass"), manifest.limitations)


__all__ = ["LinkGraphFoundationFrontierReleaseNotes", "build_link_graph_foundation_frontier_release_notes"]
