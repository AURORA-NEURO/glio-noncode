"""Compact assurance statement assembled from the C05-C08 release planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_claim_boundary import CausalBetaFrontierClaimBoundaryReport
from .causal_beta_frontier_exports import CausalBetaFrontierExportInventory
from .causal_beta_frontier_integrity import CausalBetaFrontierIntegrityReport
from .causal_beta_frontier_operational import CausalBetaFrontierOperationalMatrix
from .causal_beta_frontier_replay import CausalBetaFrontierReplayReceipt
from .causal_beta_frontier_release import CausalBetaFrontierReleaseManifest
from .serialization import content_hash

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .causal_beta_frontier_runtime import CausalBetaFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierAssurance:
    assurance_id: str
    fixture_id: str
    release_state: str
    runtime_accepted: bool
    replay_deterministic: bool
    integrity_accepted: bool
    operational_accepted: bool
    boundary_accepted: bool
    exports_accepted: bool
    headline: str
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"assurance_id": self.assurance_id, "fixture_id": self.fixture_id, "release_state": self.release_state, "runtime_accepted": self.runtime_accepted, "replay_deterministic": self.replay_deterministic, "integrity_accepted": self.integrity_accepted, "operational_accepted": self.operational_accepted, "boundary_accepted": self.boundary_accepted, "exports_accepted": self.exports_accepted, "headline": self.headline, "limitations": self.limitations, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_assurance(runtime: CausalBetaFrontierRuntimeReport, replay: CausalBetaFrontierReplayReceipt, integrity: CausalBetaFrontierIntegrityReport, operational: CausalBetaFrontierOperationalMatrix, boundary: CausalBetaFrontierClaimBoundaryReport, exports: CausalBetaFrontierExportInventory, release: CausalBetaFrontierReleaseManifest) -> CausalBetaFrontierAssurance:
    flags = (runtime.accepted, replay.deterministic, integrity.accepted, operational.accepted, boundary.accepted, exports.accepted, release.accepted)
    headline = "C05-C08 public aggregate frontier is ready for bounded method validation." if all(flags) else "C05-C08 public aggregate frontier is held pending failed assurance checks."
    limitations = tuple(sorted(set(runtime.bundle.excluded_uses + tuple(item["statement"] for item in boundary.to_dict(False)["excluded"]))))
    if not limitations:
        limitations = ("No patient-level, diagnostic, treatment, or outcome inference.",)
    return CausalBetaFrontierAssurance("causal-beta-frontier-assurance", runtime.fixture.fixture_id, release.state.value, runtime.accepted, replay.deterministic, integrity.accepted, operational.accepted, boundary.accepted, exports.accepted, headline, limitations, bool(flags and all(flags)))


__all__ = ["CausalBetaFrontierAssurance", "build_causal_beta_frontier_assurance"]
