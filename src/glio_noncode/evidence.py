"""Append-only evidence graph and dependence-aware aggregation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .errors import ValidationError
from .models import EvidenceClaim, EvidenceState, EvidenceTier, HypothesisEdge


@dataclass(frozen=True, slots=True)
class AggregateSupport:
    """Transparent aggregate with source grouping and negative evidence."""

    score: float
    uncertainty: float
    context_support: float
    supported_claim_ids: tuple[str, ...]
    negative_claim_ids: tuple[str, ...]
    missing_claim_ids: tuple[str, ...]
    channel_groups: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "uncertainty": self.uncertainty,
            "context_support": self.context_support,
            "supported_claim_ids": list(self.supported_claim_ids),
            "negative_claim_ids": list(self.negative_claim_ids),
            "missing_claim_ids": list(self.missing_claim_ids),
            "channel_groups": list(self.channel_groups),
            "rationale": self.rationale,
        }


class EvidenceGraph:
    """In-memory append-only graph used by a single case run."""

    def __init__(self) -> None:
        self._claims: dict[str, EvidenceClaim] = {}
        self._edge_claims: dict[str, list[str]] = defaultdict(list)

    def append(self, claim: EvidenceClaim) -> None:
        if claim.evidence_id in self._claims:
            raise ValidationError(f"evidence ID already exists: {claim.evidence_id}")
        if claim.supersedes and claim.supersedes not in self._claims:
            raise ValidationError(f"superseded evidence is not present: {claim.supersedes}")
        self._claims[claim.evidence_id] = claim
        self._edge_claims[claim.edge_id].append(claim.evidence_id)

    def extend(self, claims: Iterable[EvidenceClaim]) -> None:
        for claim in claims:
            self.append(claim)

    def get(self, evidence_id: str) -> EvidenceClaim:
        return self._claims[evidence_id]

    def for_edge(self, edge_id: str) -> tuple[EvidenceClaim, ...]:
        return tuple(self._claims[item] for item in self._edge_claims.get(edge_id, ()))

    def all_claims(self) -> tuple[EvidenceClaim, ...]:
        return tuple(self._claims.values())

    def aggregate(self, edge: HypothesisEdge) -> AggregateSupport:
        claims = self.for_edge(edge.edge_id)
        if not claims:
            return AggregateSupport(
                score=0.0,
                uncertainty=1.0,
                context_support=0.0,
                supported_claim_ids=(),
                negative_claim_ids=(),
                missing_claim_ids=(f"{edge.edge_id}:missing",),
                channel_groups=(),
                rationale="No claim objects were available for this edge.",
            )
        supported = [claim for claim in claims if claim.state == EvidenceState.SUPPORTED]
        negative = [
            claim
            for claim in claims
            if claim.state in (EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY)
        ]
        missing = [
            claim
            for claim in claims
            if claim.state
            in (EvidenceState.ABSENT, EvidenceState.UNSUPPORTED, EvidenceState.OUT_OF_DOMAIN, EvidenceState.ABSTAINED)
        ]
        groups = self._group_channels(claims)
        group_scores: list[float] = []
        for group in groups:
            group_claims = [claim for claim in supported if self._channel_group(claim.channel) == group]
            if group_claims:
                group_scores.append(max(self._claim_value(claim) for claim in group_claims))
        positive = self._dependence_adjusted_mean(group_scores)
        negative_penalty = min(0.45, sum(self._claim_value(claim) for claim in negative) * 0.22)
        score = round(max(0.0, min(1.0, positive - negative_penalty)), 6)
        context_support = round(
            sum(claim.confidence for claim in claims) / max(1, len(claims)),
            6,
        )
        uncertainty = round(
            max(
                0.0,
                min(
                    1.0,
                    1.0
                    - (0.65 * context_support)
                    - (0.25 * min(1.0, len(groups) / 3.0))
                    + (0.15 if missing else 0.0),
                ),
            ),
            6,
        )
        rationale = (
            f"{len(supported)} supported, {len(negative)} negative, {len(missing)} missing/unsupported; "
            f"{len(groups)} independent channel groups with dependence-adjusted aggregation."
        )
        return AggregateSupport(
            score=score,
            uncertainty=uncertainty,
            context_support=context_support,
            supported_claim_ids=tuple(claim.evidence_id for claim in supported),
            negative_claim_ids=tuple(claim.evidence_id for claim in negative),
            missing_claim_ids=tuple(claim.evidence_id for claim in missing),
            channel_groups=tuple(groups),
            rationale=rationale,
        )

    @staticmethod
    def _channel_group(channel: str) -> str:
        mapping = {
            "motif_delta": "sequence",
            "sequence_model": "sequence",
            "conservation": "sequence",
            "accessibility": "chromatin",
            "histone_activity": "chromatin",
            "methylation": "chromatin",
            "contact": "topology",
            "boundary": "topology",
            "qtl": "linking",
            "coaccessibility": "linking",
            "perturbation": "functional",
            "cohort": "cohort",
        }
        return mapping.get(channel, channel)

    def _group_channels(self, claims: Iterable[EvidenceClaim]) -> list[str]:
        return sorted({self._channel_group(claim.channel) for claim in claims})

    @staticmethod
    def _claim_value(claim: EvidenceClaim) -> float:
        tier_weight = {
            EvidenceTier.REFERENCE: 0.72,
            EvidenceTier.COMPUTED: 0.74,
            EvidenceTier.EXPERIMENTAL: 0.95,
            EvidenceTier.COHORT: 0.82,
            EvidenceTier.REVIEWED: 1.00,
        }[claim.tier]
        return (claim.score or 0.0) * claim.confidence * tier_weight

    @staticmethod
    def _dependence_adjusted_mean(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values, reverse=True)
        weights = [1.0 / (index + 1) for index in range(len(ordered))]
        denominator = sum(weights)
        return sum(value * weight for value, weight in zip(ordered, weights)) / denominator
