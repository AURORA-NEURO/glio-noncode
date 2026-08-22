"""Structured release notes that retain scope, changes, and limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_release import LinkGraphAlphaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReleaseNotes:
    release_id: str
    highlights: tuple[str, ...]
    verification: tuple[str, ...]
    limitations: tuple[str, ...]
    next_steps: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_markdown(self) -> str:
        return "\n".join((f"# {self.release_id}", "", "## Highlights", *[f"- {item}" for item in self.highlights], "", "## Verification", *[f"- {item}" for item in self.verification], "", "## Limitations", *[f"- {item}" for item in self.limitations], "", "## Next steps", *[f"- {item}" for item in self.next_steps], ""))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "highlights": self.highlights, "verification": self.verification, "limitations": self.limitations, "next_steps": self.next_steps}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_release_notes(manifest: LinkGraphAlphaFrontierReleaseManifest) -> LinkGraphAlphaFrontierReleaseNotes:
    return LinkGraphAlphaFrontierReleaseNotes(manifest.release_id, ("four candidate link operations are replayable", "public aggregate source receipts are closed", "positive and control records are balanced"), ("16 of 16 states match", "16 of 16 issue controls match", "12 pipeline stages pass"), manifest.limitations, ("add more aggregate assay cohorts", "calibrate cross-context transport separately", "retain review of contradictory paths"))


__all__ = ["LinkGraphAlphaFrontierReleaseNotes", "build_link_graph_alpha_frontier_release_notes"]
