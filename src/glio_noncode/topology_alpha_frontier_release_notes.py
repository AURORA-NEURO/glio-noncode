"""Structured release notes for reviewers of the alpha package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReleaseNote:
    note_id: str
    category: str
    title: str
    detail: str
    evidence_refs: tuple[str, ...]
    reviewer_action: str
    public: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReleaseNotes:
    release_id: str
    version: str
    notes: tuple[TopologyAlphaFrontierReleaseNote, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_category(self, category: str) -> tuple[TopologyAlphaFrontierReleaseNote, ...]:
        return tuple(item for item in self.notes if item.category == category)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "version": self.version, "notes": [item.to_dict() for item in self.notes], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_release_notes(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierReleaseNotes:
    notes = (
        TopologyAlphaFrontierReleaseNote("note-01", "scope", "Aggregate boundary", "The package contains public aggregate records and source receipts.", (pipeline.fixture.content_address,), "retain the scope boundary when reusing outputs"),
        TopologyAlphaFrontierReleaseNote("note-02", "coverage", "Four operations", "Boundary motif orientation, CTCF-cohesin disruption, IDH insulator dysfunction, and SV topology rewiring are replayed.", tuple(item.record_id for item in pipeline.evaluation.rows if item.role == "positive"), "inspect the operation-specific contract"),
        TopologyAlphaFrontierReleaseNote("note-03", "controls", "Control paths retained", "Twelve controls cover incomplete fields, disagreement, invalid values, missing edges, and foreign context.", tuple(item.record_id for item in pipeline.evaluation.controls()), "keep controls in downstream review"),
        TopologyAlphaFrontierReleaseNote("note-04", "reproducibility", "Content addresses", "Fixture, result, bundle, artifact, and trace outputs carry content addresses.", (pipeline.content_address, pipeline.bundle.content_address, pipeline.artifacts.content_address), "compare addresses across replay runs"),
        TopologyAlphaFrontierReleaseNote("note-05", "limitations", "Descriptive scope", "Orientation, channel, state, and edge outputs do not establish mechanism, probability, or clinical effect.", tuple(item.adapter.content_address for item in pipeline.evaluation.rows[:4]), "apply external calibration before broader interpretation"),
        TopologyAlphaFrontierReleaseNote("note-06", "operations", "Review queue", "Every control and non-supported path has a review disposition and next action.", (pipeline.review_queue.content_address, pipeline.view.content_address), "resolve or retain review items explicitly"),
    )
    accepted = pipeline.accepted and all(item.public and item.evidence_refs for item in notes)
    return TopologyAlphaFrontierReleaseNotes(pipeline.release.release_id, pipeline.fixture.version, notes, accepted)


def render_topology_alpha_frontier_release_notes(notes: TopologyAlphaFrontierReleaseNotes) -> str:
    lines = [f"# {notes.release_id}", "", f"Version: {notes.version}", "", "| Category | Title | Reviewer action |", "|---|---|---|"]
    lines.extend(f"| {item.category} | {item.title} | {item.reviewer_action} |" for item in notes.notes)
    return "\n".join(lines) + "\n"


__all__ = ["TopologyAlphaFrontierReleaseNote", "TopologyAlphaFrontierReleaseNotes", "build_topology_alpha_frontier_release_notes", "render_topology_alpha_frontier_release_notes"]
