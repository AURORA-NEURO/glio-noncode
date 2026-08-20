"""Evidence-delta analysis for selective recomputation and supersession."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import EvidenceClaim, Hypothesis
from .serialization import content_hash


class ImpactLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class EvidenceDelta:
    """A change to one evidence claim or source version."""

    delta_id: str
    evidence_id: str
    previous_state: str
    current_state: str
    previous_score: float | None
    current_score: float | None
    reason: str
    source_version_before: str
    source_version_after: str

    @property
    def score_delta(self) -> float:
        return round((self.current_score or 0.0) - (self.previous_score or 0.0), 6)


@dataclass(frozen=True, slots=True)
class ReclassificationRecord:
    """Impact result for a hypothesis after evidence changes."""

    record_id: str
    hypothesis_id: str
    impact: ImpactLevel
    affected_edge_ids: tuple[str, ...]
    delta_ids: tuple[str, ...]
    recompute_required: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "hypothesis_id": self.hypothesis_id,
            "impact": self.impact.value,
            "affected_edge_ids": list(self.affected_edge_ids),
            "delta_ids": list(self.delta_ids),
            "recompute_required": self.recompute_required,
            "reason_codes": list(self.reason_codes),
        }


class ReclassificationEngine:
    """Find hypotheses affected by a set of append-only evidence deltas."""

    def compare(self, previous: Iterable[EvidenceClaim], current: Iterable[EvidenceClaim], *, source_version_before: str, source_version_after: str, reason: str) -> tuple[EvidenceDelta, ...]:
        before = {claim.evidence_id: claim for claim in previous}
        after = {claim.evidence_id: claim for claim in current}
        deltas: list[EvidenceDelta] = []
        for evidence_id in sorted(set(before) | set(after)):
            old = before.get(evidence_id)
            new = after.get(evidence_id)
            if old is not None and new is not None and old.state == new.state and old.score == new.score:
                continue
            delta_id = "delta-" + content_hash({"evidence_id": evidence_id, "before": old.to_dict() if old else None, "after": new.to_dict() if new else None}).split(":", 1)[1][:20]
            deltas.append(
                EvidenceDelta(
                    delta_id=delta_id,
                    evidence_id=evidence_id,
                    previous_state=old.state.value if old else "absent",
                    current_state=new.state.value if new else "removed",
                    previous_score=old.score if old else None,
                    current_score=new.score if new else None,
                    reason=reason,
                    source_version_before=source_version_before,
                    source_version_after=source_version_after,
                )
            )
        return tuple(deltas)

    def impact_for(self, hypothesis: Hypothesis, deltas: Iterable[EvidenceDelta]) -> ReclassificationRecord:
        delta_list = tuple(deltas)
        claim_to_edge = {claim_id: edge.edge_id for edge in hypothesis.edges for claim_id in edge.claim_ids}
        affected = tuple(sorted({claim_to_edge[delta.evidence_id] for delta in delta_list if delta.evidence_id in claim_to_edge}))
        magnitude = max((abs(delta.score_delta) for delta in delta_list), default=0.0)
        if not affected:
            impact = ImpactLevel.NONE
        elif magnitude >= 0.5 or len(affected) >= max(2, len(hypothesis.edges) // 2):
            impact = ImpactLevel.HIGH
        elif magnitude >= 0.2:
            impact = ImpactLevel.MODERATE
        else:
            impact = ImpactLevel.LOW
        reasons = ["evidence_changed"]
        if any(delta.current_state in {"contradictory", "measured_negative", "out_of_domain"} for delta in delta_list):
            reasons.append("negative_or_transport_state_changed")
        return ReclassificationRecord(
            record_id="reclass-" + content_hash({"hypothesis": hypothesis.hypothesis_id, "deltas": [delta.delta_id for delta in delta_list]}).split(":", 1)[1][:20],
            hypothesis_id=hypothesis.hypothesis_id,
            impact=impact,
            affected_edge_ids=affected,
            delta_ids=tuple(delta.delta_id for delta in delta_list),
            recompute_required=impact in {ImpactLevel.MODERATE, ImpactLevel.HIGH},
            reason_codes=tuple(reasons),
        )
