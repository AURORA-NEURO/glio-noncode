"""Assurance summary joining independent control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_claim_boundary import ControlFrontierClaimBoundaryReport
from .control_frontier_contracts import ControlFrontierEvaluation
from .control_frontier_integrity import ControlFrontierIntegrityReport
from .control_frontier_quality_gate import ControlFrontierQualityReport
from .control_frontier_replay import ControlFrontierReplayReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierAssuranceSummary:
    fixture_id: str
    evaluation: bool
    quality: bool
    replay: bool
    integrity: bool
    claim_boundary: bool
    accepted: bool
    receipt_addresses: dict[str, str]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_assurance_summary(evaluation: ControlFrontierEvaluation, quality: ControlFrontierQualityReport, replay: ControlFrontierReplayReport, integrity: ControlFrontierIntegrityReport, claim_boundary: ControlFrontierClaimBoundaryReport) -> ControlFrontierAssuranceSummary:
    addresses = {"evaluation": evaluation.content_address, "quality": quality.content_address, "replay": replay.content_address, "integrity": integrity.content_address, "claim_boundary": claim_boundary.content_address}
    accepted = bool(evaluation.accepted and quality.accepted and replay.deterministic and integrity.accepted and claim_boundary.accepted)
    return ControlFrontierAssuranceSummary(evaluation.fixture_id, evaluation.accepted, quality.accepted, replay.deterministic, integrity.accepted, claim_boundary.accepted, accepted, addresses, content_hash({"fixture_id": evaluation.fixture_id, "accepted": accepted, "receipt_addresses": addresses}))


__all__ = ["ControlFrontierAssuranceSummary", "build_control_frontier_assurance_summary"]
