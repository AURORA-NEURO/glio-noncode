"""Structured release notes for reviewers of the beta package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_pipeline import TopologyBetaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReleaseNote:
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
class TopologyBetaFrontierReleaseNotes:
    release_id: str
    version: str
    notes: tuple[TopologyBetaFrontierReleaseNote, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_category(self, category: str) -> tuple[TopologyBetaFrontierReleaseNote, ...]:
        return tuple(item for item in self.notes if item.category == category)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "version": self.version, "notes": [item.to_dict() for item in self.notes], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_release_notes(pipeline: TopologyBetaFrontierPipelineReport) -> TopologyBetaFrontierReleaseNotes:
    notes = (
        TopologyBetaFrontierReleaseNote("note-01", "scope", "Aggregate boundary", "The package contains public aggregate records and source receipts.", (pipeline.fixture.content_address,), "retain the scope boundary when reusing outputs"),
        TopologyBetaFrontierReleaseNote("note-02", "coverage", "Four operations", "Loop and stripe, promoter capture, enhancer promoter contact, and activity by contact are replayed.", tuple(item.record_id for item in pipeline.evaluation.rows if item.role == "positive"), "inspect the operation-specific contract"),
        TopologyBetaFrontierReleaseNote("note-03", "controls", "Control paths retained", "Twelve controls cover metadata gaps, disagreement, missingness, and foreign context.", tuple(item.record_id for item in pipeline.evaluation.controls()), "keep controls in downstream review"),
        TopologyBetaFrontierReleaseNote("note-04", "reproducibility", "Content addresses", "Fixture, result, bundle, artifact, and trace outputs carry content addresses.", (pipeline.content_address, pipeline.bundle.content_address, pipeline.artifacts.content_address), "compare addresses across replay runs"),
        TopologyBetaFrontierReleaseNote("note-05", "limitations", "Descriptive scope", "Bounded contact and activity products do not establish probability, causality, or clinical effect.", tuple(item.adapter.content_address for item in pipeline.evaluation.rows[:4]), "apply external calibration before broader interpretation"),
        TopologyBetaFrontierReleaseNote("note-06", "operations", "Review queue", "Every control and non-supported path has a review disposition and next action.", (pipeline.review_queue.content_address, pipeline.view.content_address), "resolve or retain review items explicitly"),
    )
    return TopologyBetaFrontierReleaseNotes(pipeline.release.release_id, pipeline.fixture.version, notes, pipeline.accepted and all(item.public and item.evidence_refs for item in notes))


def render_topology_beta_frontier_release_notes(notes: TopologyBetaFrontierReleaseNotes) -> str:
    lines = [f"# {notes.release_id}", "", f"Version: {notes.version}", "", "| Category | Title | Reviewer action |", "|---|---|---|"]
    lines.extend(f"| {item.category} | {item.title} | {item.reviewer_action} |" for item in notes.notes)
    return "\n".join(lines) + "\n"


__all__ = ["TopologyBetaFrontierReleaseNote", "TopologyBetaFrontierReleaseNotes", "build_topology_beta_frontier_release_notes", "render_topology_beta_frontier_release_notes"]
