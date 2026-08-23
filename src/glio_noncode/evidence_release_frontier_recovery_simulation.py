"""Recovery simulation for every control issue in the public fixture."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseRecoverySimulation:
    control_count: int
    issue_codes: tuple[str, ...]
    recoverable_count: int
    quarantined_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def simulate_evidence_release_recovery(fixture: Any) -> EvidenceReleaseRecoverySimulation:
    evaluation = evaluate_evidence_release_fixture(fixture)
    controls = tuple(item for item in evaluation.executions if item.role.value == "control")
    issues = tuple(sorted({issue for item in controls for issue in item.issue_codes}))
    quarantined = sum(item.observed_state.value == "blocked" for item in controls)
    body = {"control_count": len(controls), "issue_codes": issues, "recoverable_count": len(controls) - quarantined, "quarantined_count": quarantined, "accepted": len(controls) == 12 and bool(issues)}
    return EvidenceReleaseRecoverySimulation(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseRecoverySimulation", "simulate_evidence_release_recovery"]
