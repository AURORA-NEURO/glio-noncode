"""Cross-plane assurance score for a release candidate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_depth import CohortBetaFrontierDepthAudit
from .cohort_beta_frontier_diagnostics import CohortBetaFrontierDiagnosticReport
from .cohort_beta_frontier_release import CohortBetaFrontierReleaseManifest
from .cohort_beta_frontier_replay import CohortBetaFrontierReplayReceipt
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAssurance:
    release_ready: bool
    depth_accepted: bool
    replay_deterministic: bool
    diagnostic_accepted: bool
    review_count: int
    quarantine_count: int
    assurance_percent: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_assurance(release: CohortBetaFrontierReleaseManifest, depth: CohortBetaFrontierDepthAudit, replay: CohortBetaFrontierReplayReceipt, diagnostics: CohortBetaFrontierDiagnosticReport, review_count: int, quarantine_count: int) -> CohortBetaFrontierAssurance:
    flags = (release.ready, depth.accepted, replay.deterministic, diagnostics.accepted)
    accepted = all(flags)
    body = {"release_ready": release.ready, "depth_accepted": depth.accepted, "replay_deterministic": replay.deterministic, "diagnostic_accepted": diagnostics.accepted, "review_count": review_count, "quarantine_count": quarantine_count}
    return CohortBetaFrontierAssurance(release.ready, depth.accepted, replay.deterministic, diagnostics.accepted, review_count, quarantine_count, round(100 * sum(flags) / len(flags), 2), accepted, content_hash(body, prefix="assurance"))


__all__ = ["CohortBetaFrontierAssurance", "build_cohort_beta_frontier_assurance"]
