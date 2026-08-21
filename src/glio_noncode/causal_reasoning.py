"""Typed causal-evidence structures with explicit research-use boundaries.

Domain 11 assembles evidence factors into immutable, replayable lineage and
combines context-conditioned prior and measurement-likelihood proxies.  The
module never presents a score as a clinical probability or a causal effect;
missing, contradictory, superseded, and out-of-domain evidence remain visible.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


class CausalState(StrEnum):
    """State used by causal-evidence components."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"
    MEASURED_NEGATIVE = "measured_negative"


class FactorType(StrEnum):
    """Evidence factor families used for dependence-aware grouping."""

    SEQUENCE = "sequence"
    CHROMATIN = "chromatin"
    TOPOLOGY = "topology"
    LINK = "link"
    STATE = "state"
    NEGATIVE = "negative"
    PRIOR = "prior"
    LIKELIHOOD = "likelihood"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class FactorObservation:
    """One append-only factor with parent and supersession lineage."""

    factor_id: str
    edge_id: str
    factor_type: FactorType
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    state: CausalState
    support: float | None
    uncertainty: float
    parent_factor_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    supersedes: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "factor_id",
            "edge_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"factor {name} is required")
        if self.support is not None and not 0.0 <= self.support <= 1.0:
            raise ValidationError("factor support must be between 0 and 1")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("factor uncertainty must be between 0 and 1")
        if self.supersedes == self.factor_id:
            raise ValidationError("a factor cannot supersede itself")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_id: str,
        context_key: str,
    ) -> FactorObservation:
        if not isinstance(raw, Mapping):
            raise ValidationError("factor input must be a mapping")
        support_raw = raw.get("support")
        return cls(
            factor_id=str(raw.get("factor_id", fallback_id)),
            edge_id=str(raw.get("edge_id", "")),
            factor_type=FactorType(str(raw.get("factor_type", FactorType.LINK.value))),
            context_key=str(raw.get("context_key", context_key)),
            source_id=str(raw.get("source_id", "declared_input")),
            source_version=str(raw.get("source_version", "unspecified")),
            raw_hash=str(raw.get("raw_hash", content_hash(raw))),
            state=CausalState(str(raw.get("state", CausalState.SUPPORTED.value))),
            support=None if support_raw is None else float(support_raw),
            uncertainty=float(raw.get("uncertainty", 1.0)),
            parent_factor_ids=tuple(str(item) for item in raw.get("parent_factor_ids", ())),
            claim_ids=tuple(str(item) for item in raw.get("claim_ids", ())),
            supersedes=(None if raw.get("supersedes") is None else str(raw["supersedes"])),
            attributes=dict(raw.get("attributes", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FactorGraph:
    """Immutable factor graph snapshot with replay diagnostics."""

    graph_id: str
    context_key: str
    factors: tuple[FactorObservation, ...]
    active_factor_ids: tuple[str, ...]
    superseded_factor_ids: tuple[str, ...]
    orphan_factor_ids: tuple[str, ...]
    contradictory_edge_ids: tuple[str, ...]
    state: CausalState
    warnings: tuple[str, ...]
    content_address: str

    def active_factors(self) -> tuple[FactorObservation, ...]:
        active = set(self.active_factor_ids)
        return tuple(factor for factor in self.factors if factor.factor_id in active)

    def replay(self) -> FactorGraph:
        """Return a byte-equivalent reconstruction of this snapshot."""

        return FactorGraphConstructor().construct(
            self.factors,
            context_key=self.context_key,
            graph_id=self.graph_id,
        )

    def append(self, factor: FactorObservation) -> FactorGraph:
        """Return a new graph snapshot without mutating this one."""

        if factor.context_key != self.context_key:
            raise ValidationError("factor context does not match graph context")
        return FactorGraphConstructor().construct(
            self.factors + (factor,),
            context_key=self.context_key,
            graph_id=self.graph_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FactorGraphConstructor:
    """Construct append-only factor snapshots with structural diagnostics."""

    def construct(
        self,
        factors: Iterable[FactorObservation],
        *,
        context_key: str,
        graph_id: str = "factor-graph",
    ) -> FactorGraph:
        if not context_key.strip() or not graph_id.strip():
            raise ValidationError("factor graph ID and context key are required")
        values = tuple(factors)
        ids = tuple(factor.factor_id for factor in values)
        if len(ids) != len(set(ids)):
            raise ValidationError("factor IDs must be unique")
        mismatched = tuple(
            factor.factor_id for factor in values if factor.context_key != context_key
        )
        if mismatched:
            raise ValidationError("all factors must share the graph context")
        known = set(ids)
        orphan_ids = tuple(
            factor.factor_id
            for factor in values
            if any(parent not in known for parent in factor.parent_factor_ids)
            or (factor.supersedes is not None and factor.supersedes not in known)
        )
        superseded = tuple(
            sorted({factor.supersedes for factor in values if factor.supersedes is not None})
        )
        edge_states: dict[str, set[CausalState]] = defaultdict(set)
        for factor in values:
            edge_states[factor.edge_id].add(factor.state)
        contradictory = tuple(
            sorted(
                edge_id
                for edge_id, states in edge_states.items()
                if CausalState.CONTRADICTORY in states
                or {
                    CausalState.SUPPORTED,
                    CausalState.MEASURED_NEGATIVE,
                }.issubset(states)
            )
        )
        if orphan_ids:
            state = CausalState.PARTIAL
        elif contradictory:
            state = CausalState.CONTRADICTORY
        elif not values:
            state = CausalState.ABSTAINED
        elif any(factor.state == CausalState.OUT_OF_DOMAIN for factor in values):
            state = CausalState.OUT_OF_DOMAIN
        elif any(factor.state == CausalState.ABSTAINED for factor in values):
            state = CausalState.ABSTAINED
        elif all(factor.state == CausalState.SUPPORTED for factor in values):
            state = CausalState.SUPPORTED
        else:
            state = CausalState.PARTIAL
        active_ids = tuple(item for item in ids if item not in set(superseded))
        warnings: list[str] = []
        if orphan_ids:
            warnings.append("orphan or invalid lineage references were retained for review")
        if contradictory:
            warnings.append("contradictory factors remain attached to one or more edges")
        if superseded:
            warnings.append(
                "superseded factors remain in history and are excluded only from active views"
            )
        body = {
            "graph_id": graph_id,
            "context_key": context_key,
            "factors": values,
            "active_factor_ids": active_ids,
            "superseded_factor_ids": superseded,
            "orphan_factor_ids": orphan_ids,
            "contradictory_edge_ids": contradictory,
            "state": state,
        }
        return FactorGraph(
            graph_id=graph_id,
            context_key=context_key,
            factors=values,
            active_factor_ids=active_ids,
            superseded_factor_ids=superseded,
            orphan_factor_ids=orphan_ids,
            contradictory_edge_ids=contradictory,
            state=state,
            warnings=tuple(warnings),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ContextPriorProfile:
    """Versioned bounded prior profile for one exact context."""

    profile_id: str
    context_key: str
    base_score: float
    feature_weights: Mapping[str, float]
    feature_ranges: Mapping[str, tuple[float, float]]
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        if (
            not self.profile_id.strip()
            or not self.context_key.strip()
            or not self.source_version.strip()
        ):
            raise ValidationError("prior profile identifiers are required")
        if not 0.0 <= self.base_score <= 1.0:
            raise ValidationError("prior base_score must be between 0 and 1")
        if not self.feature_weights:
            raise ValidationError("prior profile requires feature weights")
        for feature, bounds in self.feature_ranges.items():
            if feature not in self.feature_weights:
                raise ValidationError(f"prior range has no weight: {feature}")
            if bounds[1] <= bounds[0]:
                raise ValidationError(f"prior feature range is invalid: {feature}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextPriorEstimate:
    """Bounded context prior score with missing/OOD diagnostics."""

    profile_id: str
    context_key: str
    state: CausalState
    prior_score: float | None
    feature_contributions: Mapping[str, float]
    missing_features: tuple[str, ...]
    out_of_range_features: tuple[str, ...]
    uncertainty: float
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContextConditionedPriorModel:
    """Apply a declared linear prior profile without fitting or probability claims."""

    def estimate(
        self,
        context: ReferenceContext,
        features: Mapping[str, float],
        profile: ContextPriorProfile,
    ) -> ContextPriorEstimate:
        if profile.context_key != context.key:
            return self._result(
                profile,
                context,
                CausalState.OUT_OF_DOMAIN,
                None,
                {},
                (),
                tuple(sorted(profile.feature_weights)),
                1.0,
                "prior profile context does not match the requested context",
            )
        missing = tuple(
            sorted(feature for feature in profile.feature_weights if feature not in features)
        )
        out_of_range: list[str] = []
        contributions: dict[str, float] = {}
        for feature, weight in profile.feature_weights.items():
            if feature not in features:
                continue
            value = float(features[feature])
            bounds = profile.feature_ranges.get(feature)
            if bounds is not None and not bounds[0] <= value <= bounds[1]:
                out_of_range.append(feature)
            center = (bounds[0] + bounds[1]) / 2 if bounds is not None else 0.0
            scale = (bounds[1] - bounds[0]) / 2 if bounds is not None else 1.0
            contributions[feature] = round(weight * (value - center) / max(scale, 1e-12), 9)
        if missing:
            state = CausalState.ABSTAINED
            score = None
            uncertainty = 1.0
            reason = "required prior features are missing"
        elif out_of_range:
            state = CausalState.OUT_OF_DOMAIN
            score = None
            uncertainty = 1.0
            reason = "prior features fall outside the declared profile support"
        else:
            score = max(0.0, min(1.0, profile.base_score + sum(contributions.values())))
            state = CausalState.SUPPORTED
            uncertainty = min(1.0, 0.25 + 0.05 * len(contributions))
            reason = "bounded context prior proxy evaluated from declared feature contributions"
        return self._result(
            profile,
            context,
            state,
            None if score is None else round(score, 9),
            contributions,
            missing,
            tuple(sorted(out_of_range)),
            uncertainty,
            reason,
        )

    @staticmethod
    def _result(
        profile: ContextPriorProfile,
        context: ReferenceContext,
        state: CausalState,
        score: float | None,
        contributions: Mapping[str, float],
        missing: tuple[str, ...],
        out_of_range: tuple[str, ...],
        uncertainty: float,
        reason: str,
    ) -> ContextPriorEstimate:
        body = {
            "profile": profile,
            "context": context,
            "state": state,
            "score": score,
            "contributions": dict(contributions),
            "missing": missing,
            "out_of_range": out_of_range,
        }
        return ContextPriorEstimate(
            profile_id=profile.profile_id,
            context_key=context.key,
            state=state,
            prior_score=score,
            feature_contributions=dict(contributions),
            missing_features=missing,
            out_of_range_features=out_of_range,
            uncertainty=round(uncertainty, 9),
            reason=reason,
            limitations=(
                "This is a hand-declared prior score, not a calibrated probability or "
                "clinical risk.",
                "External benchmark, calibration, negative-control, transport, and OOD "
                "evaluation remain required.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class MeasurementObservation:
    """Context-qualified measurement used by the likelihood proxy."""

    measurement_id: str
    edge_id: str
    channel: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    state: CausalState
    score: float | None
    confidence: float
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "measurement_id",
            "edge_id",
            "channel",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"measurement {name} is required")
        for name in ("score", "confidence"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValidationError(f"measurement {name} must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MeasurementLikelihoodEstimate:
    """Dependence-aware likelihood proxy, never a posterior probability."""

    edge_id: str
    context_key: str
    state: CausalState
    likelihood_proxy: float | None
    channel_groups: tuple[str, ...]
    measurement_ids: tuple[str, ...]
    missing_measurement_ids: tuple[str, ...]
    uncertainty: float
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MeasurementLikelihoodModel:
    """Aggregate measured channels with one contribution per dependence group."""

    _GROUPS = {
        "sequence_model": "sequence",
        "motif_delta": "sequence",
        "accessibility": "chromatin",
        "histone_activity": "chromatin",
        "contact": "topology",
        "boundary": "topology",
        "nearest_gene": "linking",
        "coaccessibility": "linking",
        "qtl": "linking",
        "perturbation": "functional",
    }

    def estimate(
        self,
        context: ReferenceContext,
        observations: Iterable[MeasurementObservation],
        *,
        edge_id: str,
    ) -> MeasurementLikelihoodEstimate:
        values = tuple(item for item in observations if item.edge_id == edge_id)
        matched = tuple(item for item in values if item.context_key == context.key)
        if not matched:
            state = CausalState.OUT_OF_DOMAIN if values else CausalState.ABSTAINED
            reason = (
                "measurement rows exist only outside the requested context"
                if values
                else "no measurement rows were supplied"
            )
            return self._result(edge_id, context, state, None, (), (), (), 1.0, reason)
        contradictory = any(item.state == CausalState.CONTRADICTORY for item in matched)
        groups: dict[str, list[MeasurementObservation]] = defaultdict(list)
        for item in matched:
            group = self._GROUPS.get(item.channel, item.channel)
            groups[group].append(item)
        group_scores: list[float] = []
        used_ids: list[str] = []
        missing_ids: list[str] = []
        for _group, rows in sorted(groups.items()):
            usable = [
                row
                for row in rows
                if row.state == CausalState.SUPPORTED and row.score is not None
            ]
            missing_ids.extend(row.measurement_id for row in rows if row.score is None)
            if not usable:
                continue
            best = max(usable, key=lambda row: row.score * row.confidence)
            group_scores.append(best.score * best.confidence)
            used_ids.append(best.measurement_id)
        if contradictory:
            state = CausalState.CONTRADICTORY
            proxy = None
            uncertainty = 1.0
            reason = "contradictory measurement evidence was supplied"
        elif not group_scores:
            state = CausalState.ABSTAINED
            proxy = None
            uncertainty = 1.0
            reason = "matched measurements contain no usable positive scores"
        else:
            weights = [1.0 / (index + 1) for index in range(len(group_scores))]
            proxy = sum(
                score * weight
                for score, weight in zip(
                    sorted(group_scores, reverse=True), weights, strict=True
                )
            ) / sum(weights)
            state = CausalState.SUPPORTED if len(group_scores) > 1 else CausalState.PARTIAL
            uncertainty = min(
                1.0,
                1.0
                - fmean(matched_item.confidence for matched_item in matched)
                + 0.1 / len(group_scores),
            )
            reason = "dependence-adjusted measurement likelihood proxy evaluated by channel group"
        return self._result(
            edge_id,
            context,
            state,
            None if proxy is None else round(proxy, 9),
            tuple(sorted(groups)),
            tuple(sorted(used_ids)),
            tuple(sorted(set(missing_ids))),
            uncertainty,
            reason,
        )

    @staticmethod
    def _result(
        edge_id: str,
        context: ReferenceContext,
        state: CausalState,
        proxy: float | None,
        groups: Iterable[str],
        measurement_ids: Iterable[str],
        missing_ids: Iterable[str],
        uncertainty: float,
        reason: str,
    ) -> MeasurementLikelihoodEstimate:
        group_values = tuple(sorted(groups))
        used_values = tuple(sorted(measurement_ids))
        missing_values = tuple(sorted(missing_ids))
        body = {
            "edge_id": edge_id,
            "context": context,
            "state": state,
            "proxy": proxy,
            "groups": group_values,
            "measurement_ids": used_values,
            "missing": missing_values,
        }
        return MeasurementLikelihoodEstimate(
            edge_id=edge_id,
            context_key=context.key,
            state=state,
            likelihood_proxy=proxy,
            channel_groups=group_values,
            measurement_ids=used_values,
            missing_measurement_ids=missing_values,
            uncertainty=round(min(1.0, max(0.0, uncertainty)), 9),
            reason=reason,
            limitations=(
                "This is a dependence-adjusted measurement proxy, not a calibrated "
                "likelihood or clinical probability.",
                "Measurement error, sampling, model-form, transport, and OOD uncertainty "
                "remain explicit release gates.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class RegulatoryCausalHypothesis:
    """Typed research hypothesis assembled from factor, prior, and likelihood evidence."""

    hypothesis_id: str
    variant_id: str
    element_id: str
    gene_id: str
    state_id: str
    mechanism: str
    context_key: str
    state: CausalState
    support_proxy: float | None
    uncertainty: float
    factor_graph_id: str
    factor_ids: tuple[str, ...]
    prior_profile_id: str | None
    measurement_edge_id: str | None
    missing_evidence: tuple[str, ...]
    contradictory_edges: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "hypothesis_id",
            "variant_id",
            "element_id",
            "gene_id",
            "state_id",
            "mechanism",
            "context_key",
            "factor_graph_id",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"hypothesis {name} is required")
        if self.support_proxy is not None and not 0.0 <= self.support_proxy <= 1.0:
            raise ValidationError("hypothesis support_proxy must be between 0 and 1")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("hypothesis uncertainty must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TypedHypothesisObjectBuilder:
    """Build a typed hypothesis without promoting proxy scores to posteriors."""

    def build(
        self,
        *,
        hypothesis_id: str,
        variant_id: str,
        element_id: str,
        gene_id: str,
        state_id: str,
        mechanism: str,
        context: ReferenceContext,
        factor_graph: FactorGraph,
        prior: ContextPriorEstimate | None = None,
        likelihood: MeasurementLikelihoodEstimate | None = None,
    ) -> RegulatoryCausalHypothesis:
        if factor_graph.context_key != context.key:
            raise ValidationError("hypothesis context does not match factor graph")
        factors = factor_graph.active_factors()
        missing: list[str] = []
        if prior is None or prior.prior_score is None:
            missing.append("context_prior")
        if likelihood is None or likelihood.likelihood_proxy is None:
            missing.append("measurement_likelihood")
        if factor_graph.orphan_factor_ids:
            missing.append("factor_lineage")
        if factor_graph.contradictory_edge_ids:
            state = CausalState.CONTRADICTORY
            support = None
        elif factor_graph.state == CausalState.OUT_OF_DOMAIN:
            state = CausalState.OUT_OF_DOMAIN
            support = None
        elif (
            not prior
            or not likelihood
            or prior.prior_score is None
            or likelihood.likelihood_proxy is None
        ):
            state = CausalState.ABSTAINED
            support = None
        elif factor_graph.state == CausalState.PARTIAL:
            state = CausalState.PARTIAL
            support = prior.prior_score * likelihood.likelihood_proxy
        else:
            state = CausalState.SUPPORTED
            support = prior.prior_score * likelihood.likelihood_proxy
        uncertainties = [
            prior.uncertainty if prior else 1.0,
            likelihood.uncertainty if likelihood else 1.0,
        ]
        uncertainty = fmean(uncertainties)
        if factor_graph.orphan_factor_ids or factor_graph.contradictory_edge_ids:
            uncertainty = 1.0
        body = {
            "hypothesis_id": hypothesis_id,
            "variant_id": variant_id,
            "element_id": element_id,
            "gene_id": gene_id,
            "state_id": state_id,
            "mechanism": mechanism,
            "context": context,
            "factor_graph": factor_graph,
            "prior": prior,
            "likelihood": likelihood,
            "state": state,
            "support": support,
        }
        return RegulatoryCausalHypothesis(
            hypothesis_id=hypothesis_id,
            variant_id=variant_id,
            element_id=element_id,
            gene_id=gene_id,
            state_id=state_id,
            mechanism=mechanism,
            context_key=context.key,
            state=state,
            support_proxy=None if support is None else round(max(0.0, min(1.0, support)), 9),
            uncertainty=round(min(1.0, max(0.0, uncertainty)), 9),
            factor_graph_id=factor_graph.graph_id,
            factor_ids=tuple(factor.factor_id for factor in factors),
            prior_profile_id=prior.profile_id if prior else None,
            measurement_edge_id=likelihood.edge_id if likelihood else None,
            missing_evidence=tuple(dict.fromkeys(missing)),
            contradictory_edges=factor_graph.contradictory_edge_ids,
            limitations=(
                "Support is a transparent research proxy and is not a posterior probability.",
                "This object is not a clinical diagnosis, prognosis, treatment, or "
                "actionability claim.",
                "External benchmark, calibration, matched negative controls, transport, "
                "and OOD evaluation remain required.",
            ),
            content_address=content_hash(body),
        )


__all__ = [
    "CausalState",
    "ContextConditionedPriorModel",
    "ContextPriorEstimate",
    "ContextPriorProfile",
    "FactorGraph",
    "FactorGraphConstructor",
    "FactorObservation",
    "FactorType",
    "MeasurementLikelihoodEstimate",
    "MeasurementLikelihoodModel",
    "MeasurementObservation",
    "RegulatoryCausalHypothesis",
    "TypedHypothesisObjectBuilder",
]
