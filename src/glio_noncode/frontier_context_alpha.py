"""Deep atlas, sequence, chromatin, and cell-state frontier capabilities.

The module provides bounded analysis contracts for domains D05-D08. Every
surface keeps context, source identity, thresholds, uncertainty, and review
states in the returned record so downstream consumers can inspect exactly what
was measured and what remains unresolved.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    FrontierIssue,
    FrontierState,
    _address,
    _bounded,
    _context,
    _float,
    _mapping,
    _required_text,
    _text,
    _tuple_text,
)
from .serialization import jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class BoundaryObservation:
    boundary_id: str
    context_key: str
    chromosome: str
    start: int
    end: int
    insulation_score: float
    boundary_support: float
    orientation: str
    state: FrontierState
    source_id: str
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BoundaryAtlasReport:
    observations: tuple[BoundaryObservation, ...]
    strong_boundary_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class InsulatorBoundaryAtlas:
    """Build a context-qualified insulator and boundary atlas."""

    def build(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        source_id: str,
        minimum_support: float = 0.7,
    ) -> BoundaryAtlasReport:
        context_key = require_non_empty(context_key, "context_key")
        source_id = require_non_empty(source_id, "source_id")
        minimum_support = _bounded(minimum_support, field="minimum_support")
        observations: list[BoundaryObservation] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"boundary {index}")
            boundary_id = (
                _text(row.get("boundary_id", row.get("id")), field="boundary_id")
                or f"boundary:{index}"
            )
            issues: list[FrontierIssue] = []
            try:
                start, end = int(row.get("start")), int(row.get("end"))
                if start < 1 or end < start:
                    raise ValueError
            except (TypeError, ValueError):
                start, end = 0, 0
                issues.append(
                    FrontierIssue(
                        "invalid_boundary_interval",
                        "boundary interval is invalid",
                        "blocking",
                        "start",
                        boundary_id,
                    )
                )
            insulation = _float(row.get("insulation_score"), field="insulation_score")
            support = _bounded(row.get("boundary_support", 0.0), field="boundary_support")
            orientation = (
                _text(row.get("orientation", "unknown"), field="orientation").lower() or "unknown"
            )
            if orientation not in {"convergent", "divergent", "unknown", "left", "right"}:
                issues.append(
                    FrontierIssue(
                        "unknown_boundary_orientation",
                        "boundary orientation is not recognized",
                        "review",
                        "orientation",
                        boundary_id,
                    )
                )
            if _context(row, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "boundary_context_mismatch",
                        "boundary context differs from atlas context",
                        "blocking",
                        "context_key",
                        boundary_id,
                    )
                )
            state = (
                FrontierState.ACCEPTED
                if not issues and support >= minimum_support
                else FrontierState.REVIEW
            )
            observations.append(
                BoundaryObservation(
                    boundary_id,
                    context_key,
                    _text(row.get("chromosome", "unknown"), field="chromosome") or "unknown",
                    start,
                    end,
                    insulation,
                    support,
                    orientation,
                    state,
                    source_id,
                    tuple(issues),
                )
            )
        strong = tuple(
            item.boundary_id for item in observations if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.boundary_id for item in observations if item.state != FrontierState.ACCEPTED
        )
        return BoundaryAtlasReport(tuple(observations), strong, review, _address(observations))


@dataclass(frozen=True, slots=True)
class HotspotObservation:
    hotspot_id: str
    context_key: str
    evidence_types: tuple[str, ...]
    source_ids: tuple[str, ...]
    support_count: int
    direction_concordance: float
    hotspot_score: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HotspotAtlasReport:
    observations: tuple[HotspotObservation, ...]
    supported_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryHotspotAtlas:
    """Aggregate independent regulatory signals into a reviewable hotspot atlas."""

    def build(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_support_count: int = 2,
        minimum_concordance: float = 0.7,
    ) -> HotspotAtlasReport:
        context_key = require_non_empty(context_key, "context_key")
        if minimum_support_count < 1:
            raise ValidationError("minimum_support_count must be positive")
        minimum_concordance = _bounded(minimum_concordance, field="minimum_concordance")
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"hotspot {index}")
            hotspot_id = _required_text(row.get("hotspot_id", row.get("id")), field="hotspot_id")
            grouped.setdefault(hotspot_id, []).append(row)
        observations: list[HotspotObservation] = []
        for hotspot_id in sorted(grouped):
            rows = grouped[hotspot_id]
            evidence_types = tuple(
                sorted(
                    {
                        _text(row.get("evidence_type"), field="evidence_type")
                        for row in rows
                        if _text(row.get("evidence_type"), field="evidence_type")
                    }
                )
            )
            source_ids = tuple(
                sorted({_required_text(row.get("source_id"), field="source_id") for row in rows})
            )
            directions = [
                _text(row.get("direction", "unknown"), field="direction").lower() for row in rows
            ]
            counts = Counter(directions)
            concordance = round(max(counts.values(), default=0) / max(1, len(directions)), 6)
            score = round(
                min(1.0, len(source_ids) / max(1, minimum_support_count)) * concordance, 6
            )
            issues: list[FrontierIssue] = []
            if len(source_ids) < minimum_support_count:
                issues.append(
                    FrontierIssue(
                        "insufficient_hotspot_sources",
                        "hotspot has fewer independent sources than required",
                        "review",
                        record_id=hotspot_id,
                    )
                )
            if concordance < minimum_concordance:
                issues.append(
                    FrontierIssue(
                        "hotspot_direction_disagreement",
                        "hotspot directions are not sufficiently concordant",
                        "review",
                        record_id=hotspot_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            observations.append(
                HotspotObservation(
                    hotspot_id,
                    context_key,
                    evidence_types,
                    source_ids,
                    len(rows),
                    concordance,
                    score,
                    state,
                    tuple(issues),
                )
            )
        supported = tuple(
            item.hotspot_id for item in observations if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.hotspot_id for item in observations if item.state != FrontierState.ACCEPTED
        )
        return HotspotAtlasReport(tuple(observations), supported, review, _address(observations))


@dataclass(frozen=True, slots=True)
class AtlasEvidenceTierDecision:
    atlas_id: str
    context_key: str
    evidence_tier: str
    source_count: int
    consistency: float
    reproducibility: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasEvidenceTierReport:
    decisions: tuple[AtlasEvidenceTierDecision, ...]
    high_confidence_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AtlasEvidenceTierAdjudicator:
    """Assign a transparent evidence tier from source and consistency metrics."""

    def adjudicate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        high_source_count: int = 3,
        high_consistency: float = 0.8,
        medium_consistency: float = 0.6,
    ) -> AtlasEvidenceTierReport:
        context_key = require_non_empty(context_key, "context_key")
        if high_source_count < 1:
            raise ValidationError("high_source_count must be positive")
        high_consistency = _bounded(high_consistency, field="high_consistency")
        medium_consistency = _bounded(medium_consistency, field="medium_consistency")
        decisions: list[AtlasEvidenceTierDecision] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"atlas evidence {index}")
            atlas_id = (
                _text(row.get("atlas_id", row.get("id")), field="atlas_id") or f"atlas:{index}"
            )
            source_count = int(row.get("source_count", 0))
            consistency = _bounded(row.get("consistency", 0.0), field="consistency")
            reproducibility = _bounded(
                row.get("reproducibility", consistency), field="reproducibility"
            )
            issues: list[FrontierIssue] = []
            if source_count < 1:
                issues.append(
                    FrontierIssue(
                        "no_evidence_sources",
                        "atlas item has no source count",
                        "blocking",
                        "source_count",
                        atlas_id,
                    )
                )
            if (
                source_count >= high_source_count
                and consistency >= high_consistency
                and reproducibility >= high_consistency
            ):
                tier = "high"
            elif consistency >= medium_consistency and reproducibility >= medium_consistency:
                tier = "medium"
            else:
                tier = "low"
            state = (
                FrontierState.ACCEPTED
                if not issues and tier in {"high", "medium"}
                else FrontierState.REVIEW
            )
            decisions.append(
                AtlasEvidenceTierDecision(
                    atlas_id,
                    context_key,
                    tier,
                    source_count,
                    consistency,
                    reproducibility,
                    state,
                    tuple(issues),
                )
            )
        high = tuple(
            item.atlas_id
            for item in decisions
            if item.state == FrontierState.ACCEPTED and item.evidence_tier == "high"
        )
        review = tuple(item.atlas_id for item in decisions if item.state != FrontierState.ACCEPTED)
        return AtlasEvidenceTierReport(tuple(decisions), high, review, _address(decisions))


@dataclass(frozen=True, slots=True)
class AtlasSnapshot:
    snapshot_id: str
    context_key: str
    atlas_type: str
    version: str
    record_count: int
    records_address: str
    schema_version: str
    snapshot_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AtlasSnapshotPublisher:
    """Publish a deterministic, versioned atlas snapshot manifest."""

    def publish(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        snapshot_id: str,
        atlas_type: str,
        version: str,
        context_key: str,
        schema_version: str = "atlas-frontier-v1",
    ) -> AtlasSnapshot:
        snapshot_id = require_non_empty(snapshot_id, "snapshot_id")
        atlas_type = require_non_empty(atlas_type, "atlas_type")
        version = require_non_empty(version, "version")
        context_key = require_non_empty(context_key, "context_key")
        schema_version = require_non_empty(schema_version, "schema_version")
        normalized = tuple(dict(_mapping(row, label="atlas record")) for row in records)
        for row in normalized:
            if _context(row, context_key) != context_key:
                raise ValidationError("atlas record context does not match snapshot")
        records_address = _address(normalized)
        manifest = {
            "snapshot_id": snapshot_id,
            "atlas_type": atlas_type,
            "version": version,
            "context_key": context_key,
            "records_address": records_address,
            "schema_version": schema_version,
        }
        return AtlasSnapshot(
            snapshot_id,
            context_key,
            atlas_type,
            version,
            len(normalized),
            records_address,
            schema_version,
            _address(manifest),
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class EnhancerGrammarResult:
    grammar_id: str
    context_key: str
    motif_ids: tuple[str, ...]
    pair_count: int
    compatible_pair_count: int
    coverage: float
    grammar_score: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EnhancerGrammarReport:
    results: tuple[EnhancerGrammarResult, ...]
    supported_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EnhancerGrammarModel:
    """Score motif spacing grammar using declared pair rules."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_coverage: float = 0.6,
    ) -> EnhancerGrammarReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_coverage = _bounded(minimum_coverage, field="minimum_coverage")
        results: list[EnhancerGrammarResult] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"grammar {index}")
            grammar_id = (
                _text(row.get("grammar_id", row.get("id")), field="grammar_id")
                or f"grammar:{index}"
            )
            hits = tuple(_mapping(item, label="motif hit") for item in row.get("motif_hits", ()))
            rules = tuple(_mapping(item, label="grammar rule") for item in row.get("rules", ()))
            motif_ids = tuple(
                sorted({_required_text(item.get("motif_id"), field="motif_id") for item in hits})
            )
            pair_count = len(rules)
            compatible = 0
            for rule in rules:
                left = _required_text(rule.get("left_motif"), field="left_motif")
                right = _required_text(rule.get("right_motif"), field="right_motif")
                min_gap = int(rule.get("min_gap", 0))
                max_gap = int(rule.get("max_gap", 10**9))
                candidates = [
                    item for item in hits if _text(item.get("motif_id"), field="motif_id") == left
                ]
                partners = [
                    item for item in hits if _text(item.get("motif_id"), field="motif_id") == right
                ]
                if any(
                    min_gap <= abs(int(b.get("start", 0)) - int(a.get("end", 0))) <= max_gap
                    for a in candidates
                    for b in partners
                ):
                    compatible += 1
            coverage = round(compatible / max(1, pair_count), 6)
            score = coverage
            issues: list[FrontierIssue] = []
            if not hits:
                issues.append(
                    FrontierIssue(
                        "no_motif_hits",
                        "grammar evaluation has no motif hits",
                        "review",
                        record_id=grammar_id,
                    )
                )
            state = (
                FrontierState.ACCEPTED
                if not issues and coverage >= minimum_coverage
                else FrontierState.REVIEW
            )
            results.append(
                EnhancerGrammarResult(
                    grammar_id,
                    context_key,
                    motif_ids,
                    pair_count,
                    compatible,
                    coverage,
                    score,
                    state,
                    tuple(issues),
                )
            )
        supported = tuple(
            item.grammar_id for item in results if item.state == FrontierState.ACCEPTED
        )
        review = tuple(item.grammar_id for item in results if item.state != FrontierState.ACCEPTED)
        return EnhancerGrammarReport(tuple(results), supported, review, _address(results))


@dataclass(frozen=True, slots=True)
class AlleleSaturationPoint:
    variant_id: str
    allele: str
    predicted_effect: float
    delta_from_reference: float
    uncertainty: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleSaturationReport:
    points: tuple[AlleleSaturationPoint, ...]
    positive_effect_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AlleleSaturationSimulator:
    """Simulate declared alternate alleles around a measured reference score."""

    def simulate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_effect: float = 0.2,
    ) -> AlleleSaturationReport:
        require_non_empty(context_key, "context_key")
        minimum_effect = _float(minimum_effect, field="minimum_effect")
        points: list[AlleleSaturationPoint] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"allele saturation {index}")
            variant_id = _required_text(row.get("variant_id", row.get("id")), field="variant_id")
            reference_score = _float(row.get("reference_score", 0.0), field="reference_score")
            alleles = row.get("alternate_alleles", row.get("alleles", ()))
            if isinstance(alleles, str):
                alleles = (alleles,)
            effects = row.get("alternate_scores", {})
            uncertainty = _float(row.get("uncertainty", 0.0), field="uncertainty")
            for allele in alleles:
                allele_text = _required_text(allele, field="alternate_allele")
                score = (
                    _float(effects.get(allele_text, reference_score), field="alternate_score")
                    if isinstance(effects, Mapping)
                    else reference_score
                )
                delta = round(score - reference_score, 6)
                state = (
                    FrontierState.ACCEPTED
                    if uncertainty <= max(abs(delta), minimum_effect)
                    else FrontierState.REVIEW
                )
                points.append(
                    AlleleSaturationPoint(variant_id, allele_text, score, delta, uncertainty, state)
                )
        positive = tuple(
            item.variant_id
            for item in points
            if item.state == FrontierState.ACCEPTED and item.delta_from_reference >= minimum_effect
        )
        review = tuple(
            sorted({item.variant_id for item in points if item.state != FrontierState.ACCEPTED})
        )
        return AlleleSaturationReport(tuple(points), positive, review, _address(points))


@dataclass(frozen=True, slots=True)
class EnsembleDisagreementResult:
    prediction_id: str
    context_key: str
    predictions: tuple[float, ...]
    mean: float
    standard_deviation: float
    lower_bound: float
    upper_bound: float
    disagreement: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EnsembleDisagreementReport:
    results: tuple[EnsembleDisagreementResult, ...]
    stable_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EnsembleDisagreementQuantifier:
    """Quantify ensemble spread and retain review states for high disagreement."""

    def quantify(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        disagreement_threshold: float = 0.25,
        interval_multiplier: float = 1.96,
    ) -> EnsembleDisagreementReport:
        context_key = require_non_empty(context_key, "context_key")
        disagreement_threshold = _float(disagreement_threshold, field="disagreement_threshold")
        interval_multiplier = _float(interval_multiplier, field="interval_multiplier")
        results: list[EnsembleDisagreementResult] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"ensemble {index}")
            prediction_id = (
                _text(row.get("prediction_id", row.get("id")), field="prediction_id")
                or f"prediction:{index}"
            )
            values = tuple(
                _float(value, field="prediction") for value in row.get("predictions", ())
            )
            if not values:
                raise ValidationError(f"{prediction_id} has no predictions")
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / max(1, len(values) - 1)
            standard_deviation = sqrt(variance)
            disagreement = max(values) - min(values)
            lower = mean - interval_multiplier * standard_deviation
            upper = mean + interval_multiplier * standard_deviation
            state = (
                FrontierState.ACCEPTED
                if disagreement <= disagreement_threshold
                else FrontierState.REVIEW
            )
            results.append(
                EnsembleDisagreementResult(
                    prediction_id,
                    context_key,
                    values,
                    round(mean, 6),
                    round(standard_deviation, 6),
                    round(lower, 6),
                    round(upper, 6),
                    round(disagreement, 6),
                    state,
                )
            )
        stable = tuple(
            item.prediction_id for item in results if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.prediction_id for item in results if item.state != FrontierState.ACCEPTED
        )
        return EnsembleDisagreementReport(tuple(results), stable, review, _address(results))


@dataclass(frozen=True, slots=True)
class SequenceEvidenceBundle:
    bundle_id: str
    context_key: str
    sequence_ids: tuple[str, ...]
    records_address: str
    model_ids: tuple[str, ...]
    bundle_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SequenceEvidencePublisher:
    """Publish sequence-model evidence with model and record receipts."""

    def publish(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        model_ids: Sequence[str],
    ) -> SequenceEvidenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        models = tuple(sorted({require_non_empty(str(item), "model_id") for item in model_ids}))
        if not models:
            raise ValidationError("model_ids must not be empty")
        normalized = tuple(dict(_mapping(row, label="sequence evidence")) for row in records)
        ids = tuple(
            sorted(
                {
                    _required_text(row.get("sequence_id", row.get("id")), field="sequence_id")
                    for row in normalized
                }
            )
        )
        if any(_context(row, context_key) != context_key for row in normalized):
            raise ValidationError("sequence evidence context does not match bundle")
        records_address = _address(normalized)
        bundle_address = _address(
            {
                "bundle_id": bundle_id,
                "context_key": context_key,
                "records_address": records_address,
                "model_ids": models,
            }
        )
        return SequenceEvidenceBundle(
            bundle_id,
            context_key,
            ids,
            records_address,
            models,
            bundle_address,
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class ImputedContextValue:
    feature_id: str
    context_key: str
    value: float
    source: str
    confidence: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextImputationReport:
    values: tuple[ImputedContextValue, ...]
    observed_ids: tuple[str, ...]
    imputed_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContextImputationWithConfidence:
    """Fill missing context values only from declared priors with confidence."""

    def impute(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        prior_values: Mapping[str, Any],
        prior_confidence: Mapping[str, Any] | None = None,
        minimum_confidence: float = 0.7,
    ) -> ContextImputationReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_confidence = _bounded(minimum_confidence, field="minimum_confidence")
        confidence_map = prior_confidence or {}
        values: list[ImputedContextValue] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"context value {index}")
            feature_id = _required_text(row.get("feature_id", row.get("id")), field="feature_id")
            issues: list[FrontierIssue] = []
            if row.get("value") is not None:
                value = _float(row.get("value"), field="value")
                source = "observed"
                confidence = _bounded(row.get("confidence", 1.0), field="confidence")
            elif feature_id in prior_values:
                value = _float(prior_values[feature_id], field="prior_value")
                source = "declared_prior"
                confidence = _bounded(confidence_map.get(feature_id, 0.0), field="prior_confidence")
            else:
                value = 0.0
                source = "unavailable"
                confidence = 0.0
                issues.append(
                    FrontierIssue(
                        "missing_context_prior",
                        "feature has neither observed value nor declared prior",
                        "review",
                        record_id=feature_id,
                    )
                )
            if source == "declared_prior" and confidence < minimum_confidence:
                issues.append(
                    FrontierIssue(
                        "low_imputation_confidence",
                        "declared prior confidence is below threshold",
                        "review",
                        record_id=feature_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            values.append(
                ImputedContextValue(
                    feature_id, context_key, value, source, confidence, state, tuple(issues)
                )
            )
        observed = tuple(item.feature_id for item in values if item.source == "observed")
        imputed = tuple(item.feature_id for item in values if item.source == "declared_prior")
        review = tuple(item.feature_id for item in values if item.state != FrontierState.ACCEPTED)
        return ContextImputationReport(tuple(values), observed, imputed, review, _address(values))


@dataclass(frozen=True, slots=True)
class AssayCoverageDecision:
    feature_id: str
    context_key: str
    required_assays: tuple[str, ...]
    observed_assays: tuple[str, ...]
    missing_assays: tuple[str, ...]
    coverage: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AssayCoverageReport:
    decisions: tuple[AssayCoverageDecision, ...]
    supported_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AssaySupportCoverageGate:
    """Gate chromatin interpretation on declared assay support and coverage."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        required_assays: Sequence[str],
        minimum_coverage: float = 0.75,
    ) -> AssayCoverageReport:
        context_key = require_non_empty(context_key, "context_key")
        assays = tuple(
            sorted({require_non_empty(str(item), "required_assay") for item in required_assays})
        )
        if not assays:
            raise ValidationError("required_assays must not be empty")
        minimum_coverage = _bounded(minimum_coverage, field="minimum_coverage")
        decisions: list[AssayCoverageDecision] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"assay support {index}")
            feature_id = _required_text(row.get("feature_id", row.get("id")), field="feature_id")
            observed = tuple(
                sorted(
                    set(
                        _tuple_text(
                            row.get("observed_assays", row.get("assays", ())),
                            field="observed_assays",
                        ),
                    )
                )
            )
            missing = tuple(item for item in assays if item not in observed)
            coverage = round((len(assays) - len(missing)) / len(assays), 6)
            state = FrontierState.ACCEPTED if coverage >= minimum_coverage else FrontierState.REVIEW
            decisions.append(
                AssayCoverageDecision(
                    feature_id, context_key, assays, observed, missing, coverage, state
                )
            )
        supported = tuple(
            item.feature_id for item in decisions if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.feature_id for item in decisions if item.state != FrontierState.ACCEPTED
        )
        return AssayCoverageReport(tuple(decisions), supported, review, _address(decisions))


@dataclass(frozen=True, slots=True)
class ConcordanceDecision:
    feature_id: str
    context_key: str
    directions: Mapping[str, str]
    concordant_direction: str
    concordance: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ConcordanceReport:
    decisions: tuple[ConcordanceDecision, ...]
    concordant_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CrossAssayConcordanceAdjudicator:
    """Adjudicate direction agreement across assay observations."""

    def adjudicate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_concordance: float = 0.75,
    ) -> ConcordanceReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_concordance = _bounded(minimum_concordance, field="minimum_concordance")
        decisions: list[ConcordanceDecision] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"concordance {index}")
            feature_id = _required_text(row.get("feature_id", row.get("id")), field="feature_id")
            observations = row.get("observations", row.get("assays", {}))
            if not isinstance(observations, Mapping):
                raise ValidationError("concordance observations must be an object")
            directions = {
                str(key): _text(value, field="direction").lower()
                for key, value in observations.items()
            }
            counts = Counter(directions.values())
            direction = max(counts, key=counts.get) if counts else "unknown"
            concordance = round(counts.get(direction, 0) / max(1, len(directions)), 6)
            issues: list[FrontierIssue] = []
            if len(directions) < 2:
                issues.append(
                    FrontierIssue(
                        "insufficient_assays",
                        "concordance requires at least two assay observations",
                        "review",
                        record_id=feature_id,
                    )
                )
            state = (
                FrontierState.ACCEPTED
                if not issues and concordance >= minimum_concordance
                else FrontierState.REVIEW
            )
            decisions.append(
                ConcordanceDecision(
                    feature_id,
                    context_key,
                    directions,
                    direction,
                    concordance,
                    state,
                    tuple(issues),
                )
            )
        concordant = tuple(
            item.feature_id for item in decisions if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.feature_id for item in decisions if item.state != FrontierState.ACCEPTED
        )
        return ConcordanceReport(tuple(decisions), concordant, review, _address(decisions))


@dataclass(frozen=True, slots=True)
class ChromatinEvidenceBundle:
    bundle_id: str
    context_key: str
    feature_ids: tuple[str, ...]
    assay_ids: tuple[str, ...]
    records_address: str
    bundle_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ChromatinEvidencePublisher:
    """Publish a chromatin evidence bundle after exact-context validation."""

    def publish(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        assay_ids: Sequence[str],
    ) -> ChromatinEvidenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        assays = tuple(sorted({require_non_empty(str(item), "assay_id") for item in assay_ids}))
        normalized = tuple(dict(_mapping(row, label="chromatin evidence")) for row in records)
        if not normalized or not assays:
            raise ValidationError("chromatin evidence and assay_ids must not be empty")
        if any(_context(row, context_key) != context_key for row in normalized):
            raise ValidationError("chromatin evidence context does not match bundle")
        feature_ids = tuple(
            sorted(
                {
                    _required_text(row.get("feature_id", row.get("id")), field="feature_id")
                    for row in normalized
                }
            )
        )
        records_address = _address(normalized)
        bundle_address = _address(
            {
                "bundle_id": bundle_id,
                "context_key": context_key,
                "feature_ids": feature_ids,
                "assay_ids": assays,
                "records_address": records_address,
            }
        )
        return ChromatinEvidenceBundle(
            bundle_id,
            context_key,
            feature_ids,
            assays,
            records_address,
            bundle_address,
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class CellStateAbundanceEstimate:
    sample_id: str
    context_key: str
    state_id: str
    count: int
    total_cells: int
    abundance: float
    standard_error: float
    lower_bound: float
    upper_bound: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateAbundanceReport:
    estimates: tuple[CellStateAbundanceEstimate, ...]
    stable_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CellStateAbundanceUncertaintyModel:
    """Estimate cell-state abundance with binomial uncertainty intervals."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        interval_multiplier: float = 1.96,
    ) -> CellStateAbundanceReport:
        context_key = require_non_empty(context_key, "context_key")
        interval_multiplier = _float(interval_multiplier, field="interval_multiplier")
        estimates: list[CellStateAbundanceEstimate] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"cell abundance {index}")
            sample_id = _required_text(row.get("sample_id", row.get("id")), field="sample_id")
            state_id = _required_text(row.get("state_id"), field="state_id")
            count = int(row.get("count", 0))
            total = int(row.get("total_cells", 0))
            issues: list[FrontierIssue] = []
            if total < 1 or count < 0 or count > total:
                issues.append(
                    FrontierIssue(
                        "invalid_cell_count",
                        "cell count must be between zero and total cells",
                        "blocking",
                        "count",
                        sample_id,
                    )
                )
                count, total = max(0, count), max(1, total)
            abundance = count / total
            standard_error = sqrt(abundance * (1 - abundance) / total)
            lower = max(0.0, abundance - interval_multiplier * standard_error)
            upper = min(1.0, abundance + interval_multiplier * standard_error)
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            estimates.append(
                CellStateAbundanceEstimate(
                    sample_id,
                    context_key,
                    state_id,
                    round(count, 6),
                    total,
                    round(abundance, 6),
                    round(standard_error, 6),
                    round(lower, 6),
                    round(upper, 6),
                    state,
                    tuple(issues),
                )
            )
        stable = tuple(
            f"{item.sample_id}:{item.state_id}"
            for item in estimates
            if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            f"{item.sample_id}:{item.state_id}"
            for item in estimates
            if item.state != FrontierState.ACCEPTED
        )
        return CellStateAbundanceReport(tuple(estimates), stable, review, _address(estimates))


@dataclass(frozen=True, slots=True)
class SingleCellMapping:
    cell_id: str
    context_key: str
    reference_state_id: str | None
    top_score: float
    second_score: float
    margin: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SingleCellMappingReport:
    mappings: tuple[SingleCellMapping, ...]
    mapped_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SingleCellReferenceMapper:
    """Map cells to a supplied reference score table with a margin gate."""

    def map(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_score: float = 0.6,
        minimum_margin: float = 0.1,
    ) -> SingleCellMappingReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_score = _bounded(minimum_score, field="minimum_score")
        minimum_margin = _float(minimum_margin, field="minimum_margin")
        mappings: list[SingleCellMapping] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"single cell {index}")
            cell_id = _required_text(row.get("cell_id", row.get("id")), field="cell_id")
            scores_raw = row.get("reference_scores", {})
            if not isinstance(scores_raw, Mapping):
                raise ValidationError("reference_scores must be an object")
            scores = sorted(
                (
                    (str(key), _float(value, field="reference_score"))
                    for key, value in scores_raw.items()
                ),
                key=lambda item: (-item[1], item[0]),
            )
            top = scores[0] if scores else (None, 0.0)
            second = scores[1][1] if len(scores) > 1 else 0.0
            margin = top[1] - second
            issues: list[FrontierIssue] = []
            if top[0] is None:
                issues.append(
                    FrontierIssue(
                        "no_reference_scores",
                        "cell has no reference state scores",
                        "review",
                        record_id=cell_id,
                    )
                )
            elif top[1] < minimum_score or margin < minimum_margin:
                issues.append(
                    FrontierIssue(
                        "ambiguous_reference_mapping",
                        "top reference score or margin is below threshold",
                        "review",
                        record_id=cell_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            mappings.append(
                SingleCellMapping(
                    cell_id,
                    context_key,
                    top[0],
                    round(top[1], 6),
                    round(second, 6),
                    round(margin, 6),
                    state,
                    tuple(issues),
                )
            )
        mapped = tuple(item.cell_id for item in mappings if item.state == FrontierState.ACCEPTED)
        review = tuple(item.cell_id for item in mappings if item.state != FrontierState.ACCEPTED)
        return SingleCellMappingReport(tuple(mappings), mapped, review, _address(mappings))


@dataclass(frozen=True, slots=True)
class CellStateOODFinding:
    cell_id: str
    context_key: str
    distance: float
    support_score: float
    support_boundary: float
    in_domain: bool
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateOODReport:
    findings: tuple[CellStateOODFinding, ...]
    in_domain_ids: tuple[str, ...]
    ood_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CellStateOODDetector:
    """Detect out-of-domain cell states against declared support boundaries."""

    def detect(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        maximum_distance: float = 3.0,
        minimum_support: float = 0.5,
    ) -> CellStateOODReport:
        context_key = require_non_empty(context_key, "context_key")
        maximum_distance = _float(maximum_distance, field="maximum_distance")
        minimum_support = _bounded(minimum_support, field="minimum_support")
        findings: list[CellStateOODFinding] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"cell OOD {index}")
            cell_id = _required_text(row.get("cell_id", row.get("id")), field="cell_id")
            distance = _float(row.get("distance"), field="distance")
            support = _bounded(row.get("support_score", 0.0), field="support_score")
            boundary = _float(
                row.get("support_boundary", maximum_distance), field="support_boundary"
            )
            in_domain = distance <= min(maximum_distance, boundary) and support >= minimum_support
            issues: list[FrontierIssue] = []
            if not in_domain:
                issues.append(
                    FrontierIssue(
                        "cell_state_out_of_domain",
                        "cell is outside the declared state support boundary",
                        "review",
                        record_id=cell_id,
                    )
                )
            state = FrontierState.ACCEPTED if in_domain else FrontierState.REVIEW
            findings.append(
                CellStateOODFinding(
                    cell_id,
                    context_key,
                    distance,
                    support,
                    boundary,
                    in_domain,
                    state,
                    tuple(issues),
                )
            )
        inside = tuple(item.cell_id for item in findings if item.in_domain)
        ood = tuple(item.cell_id for item in findings if not item.in_domain)
        review = tuple(item.cell_id for item in findings if item.state != FrontierState.ACCEPTED)
        return CellStateOODReport(tuple(findings), inside, ood, review, _address(findings))


@dataclass(frozen=True, slots=True)
class CellStateContextEnvelope:
    envelope_id: str
    context_key: str
    cell_ids: tuple[str, ...]
    mapping_address: str
    abundance_address: str
    ood_address: str
    envelope_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CellStateContextPublisher:
    """Publish an exact-context cell-state envelope from three receipts."""

    def publish(
        self,
        *,
        envelope_id: str,
        context_key: str,
        cell_ids: Sequence[str],
        mapping_address: str,
        abundance_address: str,
        ood_address: str,
    ) -> CellStateContextEnvelope:
        envelope_id = require_non_empty(envelope_id, "envelope_id")
        context_key = require_non_empty(context_key, "context_key")
        ids = tuple(sorted({require_non_empty(str(item), "cell_id") for item in cell_ids}))
        if not ids:
            raise ValidationError("cell_ids must not be empty")
        mapping_address = require_non_empty(mapping_address, "mapping_address")
        abundance_address = require_non_empty(abundance_address, "abundance_address")
        ood_address = require_non_empty(ood_address, "ood_address")
        address = _address(
            {
                "envelope_id": envelope_id,
                "context_key": context_key,
                "cell_ids": ids,
                "mapping_address": mapping_address,
                "abundance_address": abundance_address,
                "ood_address": ood_address,
            }
        )
        return CellStateContextEnvelope(
            envelope_id,
            context_key,
            ids,
            mapping_address,
            abundance_address,
            ood_address,
            address,
            FrontierState.PUBLISHED,
        )


def run_context_frontier_operation(
    operation: str, payload: Mapping[str, Any], *, context_key: str | None = None
) -> Any:
    """Run a D05-D08 frontier operation from a JSON payload."""

    operation = require_non_empty(operation, "operation")
    data = _mapping(payload, label="payload")
    context = context_key or _text(data.get("context_key"), field="context_key")
    if operation == "build-insulator-boundary-atlas":
        return InsulatorBoundaryAtlas().build(
            data.get("records", ()),
            context_key=context,
            source_id=_required_text(data.get("source_id"), field="source_id"),
            minimum_support=_float(data.get("minimum_support", 0.7), field="minimum_support"),
        )
    if operation == "build-regulatory-hotspot-atlas":
        return RegulatoryHotspotAtlas().build(
            data.get("records", ()),
            context_key=context,
            minimum_support_count=int(data.get("minimum_support_count", 2)),
            minimum_concordance=_float(
                data.get("minimum_concordance", 0.7), field="minimum_concordance"
            ),
        )
    if operation == "adjudicate-atlas-evidence-tier":
        return AtlasEvidenceTierAdjudicator().adjudicate(
            data.get("records", ()),
            context_key=context,
            high_source_count=int(data.get("high_source_count", 3)),
            high_consistency=_float(data.get("high_consistency", 0.8), field="high_consistency"),
            medium_consistency=_float(
                data.get("medium_consistency", 0.6), field="medium_consistency"
            ),
        )
    if operation == "publish-atlas-snapshot":
        return AtlasSnapshotPublisher().publish(
            data.get("records", ()),
            snapshot_id=_required_text(data.get("snapshot_id"), field="snapshot_id"),
            atlas_type=_required_text(data.get("atlas_type"), field="atlas_type"),
            version=_required_text(data.get("version"), field="version"),
            context_key=context,
            schema_version=_text(
                data.get("schema_version", "atlas-frontier-v1"), field="schema_version"
            )
            or "atlas-frontier-v1",
        )
    if operation == "evaluate-enhancer-grammar":
        return EnhancerGrammarModel().evaluate(
            data.get("records", ()),
            context_key=context,
            minimum_coverage=_float(data.get("minimum_coverage", 0.6), field="minimum_coverage"),
        )
    if operation == "simulate-allele-saturation":
        return AlleleSaturationSimulator().simulate(
            data.get("records", ()),
            context_key=context,
            minimum_effect=_float(data.get("minimum_effect", 0.2), field="minimum_effect"),
        )
    if operation == "quantify-ensemble-disagreement":
        return EnsembleDisagreementQuantifier().quantify(
            data.get("records", ()),
            context_key=context,
            disagreement_threshold=_float(
                data.get("disagreement_threshold", 0.25), field="disagreement_threshold"
            ),
            interval_multiplier=_float(
                data.get("interval_multiplier", 1.96), field="interval_multiplier"
            ),
        )
    if operation == "publish-sequence-evidence":
        return SequenceEvidencePublisher().publish(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            model_ids=_tuple_text(data.get("model_ids"), field="model_ids"),
        )
    if operation == "impute-context-confidence":
        return ContextImputationWithConfidence().impute(
            data.get("records", ()),
            context_key=context,
            prior_values=_mapping(data.get("prior_values", {}), label="prior_values"),
            prior_confidence=_mapping(data.get("prior_confidence", {}), label="prior_confidence"),
            minimum_confidence=_float(
                data.get("minimum_confidence", 0.7), field="minimum_confidence"
            ),
        )
    if operation == "gate-assay-support":
        return AssaySupportCoverageGate().evaluate(
            data.get("records", ()),
            context_key=context,
            required_assays=_tuple_text(data.get("required_assays"), field="required_assays"),
            minimum_coverage=_float(data.get("minimum_coverage", 0.75), field="minimum_coverage"),
        )
    if operation == "adjudicate-assay-concordance":
        return CrossAssayConcordanceAdjudicator().adjudicate(
            data.get("records", ()),
            context_key=context,
            minimum_concordance=_float(
                data.get("minimum_concordance", 0.75), field="minimum_concordance"
            ),
        )
    if operation == "publish-chromatin-evidence":
        return ChromatinEvidencePublisher().publish(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            assay_ids=_tuple_text(data.get("assay_ids"), field="assay_ids"),
        )
    if operation == "estimate-cell-state-abundance":
        return CellStateAbundanceUncertaintyModel().estimate(
            data.get("records", ()),
            context_key=context,
            interval_multiplier=_float(
                data.get("interval_multiplier", 1.96), field="interval_multiplier"
            ),
        )
    if operation == "map-single-cell-reference":
        return SingleCellReferenceMapper().map(
            data.get("records", ()),
            context_key=context,
            minimum_score=_float(data.get("minimum_score", 0.6), field="minimum_score"),
            minimum_margin=_float(data.get("minimum_margin", 0.1), field="minimum_margin"),
        )
    if operation == "detect-cell-state-ood":
        return CellStateOODDetector().detect(
            data.get("records", ()),
            context_key=context,
            maximum_distance=_float(data.get("maximum_distance", 3.0), field="maximum_distance"),
            minimum_support=_float(data.get("minimum_support", 0.5), field="minimum_support"),
        )
    if operation == "publish-cell-state-context":
        return CellStateContextPublisher().publish(
            envelope_id=_required_text(data.get("envelope_id"), field="envelope_id"),
            context_key=context,
            cell_ids=_tuple_text(data.get("cell_ids"), field="cell_ids"),
            mapping_address=_required_text(data.get("mapping_address"), field="mapping_address"),
            abundance_address=_required_text(
                data.get("abundance_address"), field="abundance_address"
            ),
            ood_address=_required_text(data.get("ood_address"), field="ood_address"),
        )
    raise ValidationError(f"unknown context frontier operation: {operation}")


CONTEXT_FRONTIER_OPERATIONS = (
    "build-insulator-boundary-atlas",
    "build-regulatory-hotspot-atlas",
    "adjudicate-atlas-evidence-tier",
    "publish-atlas-snapshot",
    "evaluate-enhancer-grammar",
    "simulate-allele-saturation",
    "quantify-ensemble-disagreement",
    "publish-sequence-evidence",
    "impute-context-confidence",
    "gate-assay-support",
    "adjudicate-assay-concordance",
    "publish-chromatin-evidence",
    "estimate-cell-state-abundance",
    "map-single-cell-reference",
    "detect-cell-state-ood",
    "publish-cell-state-context",
)
