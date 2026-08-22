"""Final assurance statement over the alpha frontier release planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_artifacts import CausalAlphaFrontierArtifactInventory
from .causal_alpha_frontier_claim_boundary import CausalAlphaFrontierClaimBoundaryReport
from .causal_alpha_frontier_integrity import CausalAlphaFrontierIntegrityReport
from .causal_alpha_frontier_operational import CausalAlphaFrontierOperationalMatrix
from .causal_alpha_frontier_release import CausalAlphaFrontierReleaseManifest
from .causal_alpha_frontier_replay import CausalAlphaFrontierReplayReceipt
from .causal_alpha_frontier_exports import CausalAlphaFrontierExportInventory
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierAssurance:
    assurance_id: str
    claims: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_addresses: tuple[str, ...]
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"assurance_id": self.assurance_id, "claims": self.claims, "limitations": self.limitations, "evidence_addresses": self.evidence_addresses, "checks": self.checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_assurance(release: CausalAlphaFrontierReleaseManifest, replay: CausalAlphaFrontierReplayReceipt, integrity: CausalAlphaFrontierIntegrityReport, operational: CausalAlphaFrontierOperationalMatrix, boundary: CausalAlphaFrontierClaimBoundaryReport, exports: CausalAlphaFrontierExportInventory, artifacts: CausalAlphaFrontierArtifactInventory) -> CausalAlphaFrontierAssurance:
    checks = (
        {"check_id": "release", "passed": release.accepted, "detail": "release manifest accepted"},
        {"check_id": "replay", "passed": replay.deterministic and replay.accepted, "detail": "replay is deterministic"},
        {"check_id": "integrity", "passed": integrity.accepted, "detail": "integrity checks accepted"},
        {"check_id": "operational", "passed": operational.accepted, "detail": "operational matrix accepted"},
        {"check_id": "boundary", "passed": boundary.accepted, "detail": "claim boundaries accepted"},
        {"check_id": "exports", "passed": exports.accepted, "detail": "six canonical exports accepted"},
        {"check_id": "artifacts", "passed": artifacts.accepted, "detail": "artifact inventory is complete"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    addresses = (release.content_address, replay.content_address, integrity.content_address, operational.content_address, boundary.content_address, exports.content_address, artifacts.content_address)
    limitations = ("aggregate public evidence is not patient data", "bounded summaries do not establish causal identification", "negative paths do not prove absence", "review and assay limitations remain active")
    claims = ("source-omission sensitivity is reproducible", "confounder disposition is explicit", "dependent paths are grouped", "negative and positive paths remain separate")
    return CausalAlphaFrontierAssurance("causal-alpha-frontier-assurance", claims, limitations, addresses, checks, all(item["passed"] for item in checks) and all(addresses))


__all__ = ["CausalAlphaFrontierAssurance", "build_causal_alpha_frontier_assurance"]
