"""Assurance summary across data, policy, replay, and release planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_diagnostics import CohortFoundationDiagnosticReport
from .cohort_foundation_frontier_depth import CohortFoundationDepthAudit
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest
from .cohort_foundation_frontier_replay import CohortFoundationReplayReceipt


@dataclass(frozen=True, slots=True)
class CohortFoundationAssurance:
    assurance_id: str
    release_ready: bool
    depth_accepted: bool
    replay_deterministic: bool
    diagnostics_accepted: bool
    review_count: int
    quarantine_count: int
    accepted: bool
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_assurance(release: CohortFoundationReleaseManifest, depth: CohortFoundationDepthAudit, replay: CohortFoundationReplayReceipt, diagnostics: CohortFoundationDiagnosticReport, review_count: int, quarantine_count: int) -> CohortFoundationAssurance:
    body = {"release": release.ready, "depth": depth.accepted, "replay": replay.deterministic, "diagnostics": diagnostics.accepted, "review_count": review_count, "quarantine_count": quarantine_count}
    accepted = release.ready and depth.accepted and replay.deterministic and diagnostics.accepted and review_count > 0 and quarantine_count > 0
    return CohortFoundationAssurance("cohort-foundation-frontier-assurance", release.ready, depth.accepted, replay.deterministic, diagnostics.accepted, review_count, quarantine_count, accepted, ("aggregate-only", "research-use", "no clinical or causal claim"), content_hash(body))


__all__ = ["CohortFoundationAssurance", "build_cohort_foundation_frontier_assurance"]
