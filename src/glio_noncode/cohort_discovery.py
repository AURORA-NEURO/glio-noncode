"""Context-matched cohort discovery and negative-control structures.

Domain 12 builds explicit cohort queries, a local callable-space mutation-rate
summary, and sequence/chromatin matched control sets.  These objects preserve
selection criteria, context transport, callable-space boundaries, and control
distances.  They do not turn recurrence or a control comparison into a
clinical, causal, or statistical significance claim.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite, sqrt
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable


class CohortState(StrEnum):
    """State for cohort selections, controls, and background summaries."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class CohortVariantRecord:
    """One pseudonymous cohort variant with optional matching features."""

    record_id: str
    variant: VariantIdentity
    context_key: str
    source_id: str
    sample_id: str
    callable: bool = True
    sequence_context: str | None = None
    chromatin_features: Mapping[str, float] = field(default_factory=dict)
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "source_id", "sample_id"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"cohort record {name} is required")
        if self.sequence_context is not None and not self.sequence_context.strip():
            raise ValidationError("sequence_context must be non-empty when supplied")
        for name, value in self.chromatin_features.items():
            if not isfinite(float(value)):
                raise ValidationError(f"chromatin feature is not finite: {name}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortQuery:
    """Immutable cohort selection contract."""

    query_id: str
    context_key: str
    variant_kinds: tuple[str, ...] = ()
    origins: tuple[str, ...] = ()
    chromosomes: tuple[str, ...] = ()
    sample_ids: tuple[str, ...] = ()
    require_callable: bool = True

    def __post_init__(self) -> None:
        if not self.query_id.strip() or not self.context_key.strip():
            raise ValidationError("cohort query ID and context key are required")

    def matches(self, record: CohortVariantRecord) -> bool:
        variant = record.variant
        return (
            record.context_key == self.context_key
            and (not self.variant_kinds or variant.kind.value in self.variant_kinds)
            and (not self.origins or variant.origin.value in self.origins)
            and (
                not self.chromosomes
                or normalize_chromosome(variant.chromosome)
                in {normalize_chromosome(item) for item in self.chromosomes}
            )
            and (not self.sample_ids or record.sample_id in self.sample_ids)
            and (not self.require_callable or record.callable)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortQueryResult:
    """Selection result with excluded counts and transport diagnostics."""

    query: CohortQuery
    state: CohortState
    records: tuple[CohortVariantRecord, ...]
    excluded_count: int
    excluded_reasons: Mapping[str, int]
    source_ids: tuple[str, ...]
    reason: str
    content_address: str

    @property
    def variant_ids(self) -> tuple[str, ...]:
        return tuple(record.variant.variant_id for record in self.records)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"variant_ids": list(self.variant_ids)}


class CohortQueryBuilder:
    """Build exact-context cohort selections without cross-context transport."""

    def build(
        self,
        query: CohortQuery,
        records: Iterable[CohortVariantRecord],
    ) -> CohortQueryResult:
        values = tuple(records)
        exact = tuple(record for record in values if record.context_key == query.context_key)
        matched = tuple(record for record in exact if query.matches(record))
        reasons: dict[str, int] = {}
        for record in exact:
            if record not in matched:
                reason = self._exclusion_reason(query, record)
                reasons[reason] = reasons.get(reason, 0) + 1
        if not exact and values:
            state = CohortState.OUT_OF_DOMAIN
            reason = "cohort records exist only outside the requested context"
        elif not matched:
            state = CohortState.ABSENT
            reason = "no records satisfy the declared cohort criteria"
        elif reasons:
            state = CohortState.PARTIAL
            reason = "cohort records were selected with explicit exclusion accounting"
        else:
            state = CohortState.SUPPORTED
            reason = "all supplied records satisfy the declared cohort criteria"
        body = {
            "query": query,
            "state": state,
            "records": matched,
            "excluded_count": len(exact) - len(matched),
            "excluded_reasons": reasons,
        }
        return CohortQueryResult(
            query=query,
            state=state,
            records=matched,
            excluded_count=len(exact) - len(matched),
            excluded_reasons=dict(sorted(reasons.items())),
            source_ids=tuple(sorted({record.source_id for record in matched})),
            reason=reason,
            content_address=content_hash(body),
        )

    @staticmethod
    def _exclusion_reason(query: CohortQuery, record: CohortVariantRecord) -> str:
        variant = record.variant
        if query.require_callable and not record.callable:
            return "not_callable"
        if query.variant_kinds and variant.kind.value not in query.variant_kinds:
            return "variant_kind"
        if query.origins and variant.origin.value not in query.origins:
            return "origin"
        if query.chromosomes and normalize_chromosome(variant.chromosome) not in {
            normalize_chromosome(item) for item in query.chromosomes
        }:
            return "chromosome"
        if query.sample_ids and record.sample_id not in query.sample_ids:
            return "sample"
        return "criteria"


@dataclass(frozen=True, slots=True)
class CallableInterval:
    """Callable bases available for a context and genomic interval."""

    interval_id: str
    chromosome: str
    start: int
    end: int
    callable_bases: int
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        if (
            not self.interval_id.strip()
            or not self.context_key.strip()
            or not self.source_id.strip()
        ):
            raise ValidationError("callable interval identifiers are required")
        if self.start < 1 or self.end < self.start or self.callable_bases < 1:
            raise ValidationError("callable interval coordinates or base count are invalid")

    def contains(self, variant: VariantIdentity) -> bool:
        return (
            normalize_chromosome(self.chromosome) == normalize_chromosome(variant.chromosome)
            and self.start <= variant.start
            and variant.end <= self.end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LocalMutationEstimate:
    """Local rate summary with callable-space and sample-size accounting."""

    context_key: str
    state: CohortState
    observed_count: int
    callable_bases: int
    target_callable_bases: int
    background_rate: float | None
    expected_count: float | None
    record_ids: tuple[str, ...]
    interval_ids: tuple[str, ...]
    uncertainty: float
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LocalBackgroundMutationModel:
    """Estimate a descriptive local mutation rate from callable bases."""

    def estimate(
        self,
        context: ReferenceContext,
        background_records: Iterable[CohortVariantRecord],
        callable_intervals: Iterable[CallableInterval],
        *,
        target_callable_bases: int,
    ) -> LocalMutationEstimate:
        if target_callable_bases < 1:
            raise ValidationError("target_callable_bases must be positive")
        records = tuple(background_records)
        all_intervals = tuple(callable_intervals)
        intervals = tuple(item for item in all_intervals if item.context_key == context.key)
        wrong_context_intervals = tuple(
            item for item in all_intervals if item.context_key != context.key
        )
        if not intervals:
            state = CohortState.OUT_OF_DOMAIN if wrong_context_intervals else CohortState.ABSTAINED
            return self._result(
                context,
                state,
                0,
                0,
                target_callable_bases,
                None,
                None,
                (),
                (),
                1.0,
                "no callable intervals match the requested context",
            )
        matched_records = tuple(
            record
            for record in records
            if record.context_key == context.key
            and record.callable
            and any(interval.contains(record.variant) for interval in intervals)
        )
        unique_records = {record.variant.variant_id: record for record in matched_records}
        observed_count = len(unique_records)
        callable_bases = sum(interval.callable_bases for interval in intervals)
        rate = observed_count / callable_bases
        expected = rate * target_callable_bases
        state = CohortState.PARTIAL if observed_count == 0 else CohortState.SUPPORTED
        uncertainty = min(1.0, 0.35 + 1.0 / sqrt(max(1, observed_count)))
        reason = (
            "callable-space rate is zero but is not interpreted as negative evidence"
            if observed_count == 0
            else "local background rate estimated from context-matched callable intervals"
        )
        return self._result(
            context,
            state,
            observed_count,
            callable_bases,
            target_callable_bases,
            rate,
            expected,
            tuple(sorted(unique_records)),
            tuple(sorted(interval.interval_id for interval in intervals)),
            uncertainty,
            reason,
        )

    @staticmethod
    def _result(
        context: ReferenceContext,
        state: CohortState,
        observed_count: int,
        callable_bases: int,
        target_callable_bases: int,
        rate: float | None,
        expected: float | None,
        record_ids: Iterable[str],
        interval_ids: Iterable[str],
        uncertainty: float,
        reason: str,
    ) -> LocalMutationEstimate:
        record_values = tuple(sorted(record_ids))
        interval_values = tuple(sorted(interval_ids))
        body = {
            "context": context,
            "state": state,
            "observed_count": observed_count,
            "callable_bases": callable_bases,
            "target_callable_bases": target_callable_bases,
            "rate": rate,
            "expected": expected,
            "record_ids": record_values,
            "interval_ids": interval_values,
        }
        return LocalMutationEstimate(
            context_key=context.key,
            state=state,
            observed_count=observed_count,
            callable_bases=callable_bases,
            target_callable_bases=target_callable_bases,
            background_rate=None if rate is None else round(rate, 12),
            expected_count=None if expected is None else round(expected, 9),
            record_ids=record_values,
            interval_ids=interval_values,
            uncertainty=round(uncertainty, 9),
            reason=reason,
            limitations=(
                "This is a descriptive callable-space mutation-rate summary, not a "
                "significance test or clinical risk.",
                "Callable-space definition, sampling, recurrence, and cohort transport "
                "require external validation.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class MatchedControl:
    """One selected negative-control candidate and its feature distance."""

    control_id: str
    target_id: str
    candidate_id: str
    control_type: str
    context_key: str
    distance: float
    matched_dimensions: tuple[str, ...]
    source_id: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MatchedControlResult:
    """Control set with candidate pool, cutoff, and explicit abstention."""

    target_id: str
    control_type: str
    context_key: str
    state: CohortState
    controls: tuple[MatchedControl, ...]
    candidate_count: int
    max_distance: float
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SequenceContextControlMatcher:
    """Match controls by normalized Hamming distance in sequence context."""

    def match(
        self,
        target: CohortVariantRecord,
        candidates: Iterable[CohortVariantRecord],
        context: ReferenceContext,
        *,
        max_controls: int = 3,
        max_distance: float = 0.0,
    ) -> MatchedControlResult:
        if max_controls < 1 or not 0.0 <= max_distance <= 1.0:
            raise ValidationError("sequence control count or distance bound is invalid")
        values = tuple(candidates)
        context_pool = tuple(
            candidate
            for candidate in values
            if candidate.record_id != target.record_id
            and candidate.sequence_context is not None
            and target.sequence_context is not None
        )
        pool = tuple(
            candidate
            for candidate in values
            if candidate.record_id != target.record_id
            and candidate.context_key == context.key
            and candidate.sequence_context is not None
            and target.sequence_context is not None
        )
        scored = tuple(
            (
                candidate,
                self._distance(target.sequence_context or "", candidate.sequence_context or ""),
            )
            for candidate in pool
        )
        usable = tuple(
            sorted(
                (item for item in scored if item[1] <= max_distance),
                key=lambda item: (item[1], item[0].record_id),
            )
        )
        selected = usable[:max_controls]
        controls = tuple(
            MatchedControl(
                control_id=content_hash(
                    {
                        "target": target.record_id,
                        "candidate": candidate.record_id,
                        "type": "sequence",
                    },
                    prefix="control",
                ),
                target_id=target.record_id,
                candidate_id=candidate.record_id,
                control_type="sequence",
                context_key=context.key,
                distance=round(distance, 9),
                matched_dimensions=("sequence_context",),
                source_id=candidate.source_id,
            )
            for candidate, distance in selected
        )
        if not pool:
            state = CohortState.OUT_OF_DOMAIN if context_pool else CohortState.ABSTAINED
            reason = (
                "sequence contexts exist only outside the requested context"
                if context_pool
                else "no context-matched sequence contexts were supplied"
            )
        elif not selected:
            state = CohortState.ABSENT
            reason = "no sequence-context candidate satisfies the distance bound"
        elif len(selected) < max_controls:
            state = CohortState.PARTIAL
            reason = "fewer sequence controls than requested satisfy the distance bound"
        else:
            state = CohortState.SUPPORTED
            reason = "sequence-context controls selected by bounded Hamming distance"
        return self._result(
            target.record_id, context, state, controls, len(pool), max_distance, reason
        )

    @staticmethod
    def _distance(left: str, right: str) -> float:
        if len(left) != len(right) or not left:
            return 1.0
        return sum(a != b for a, b in zip(left, right, strict=True)) / len(left)

    @staticmethod
    def _result(
        target_id: str,
        context: ReferenceContext,
        state: CohortState,
        controls: tuple[MatchedControl, ...],
        candidate_count: int,
        max_distance: float,
        reason: str,
    ) -> MatchedControlResult:
        body = {
            "target_id": target_id,
            "context": context,
            "state": state,
            "controls": controls,
            "candidate_count": candidate_count,
            "max_distance": max_distance,
        }
        return MatchedControlResult(
            target_id=target_id,
            control_type="sequence",
            context_key=context.key,
            state=state,
            controls=controls,
            candidate_count=candidate_count,
            max_distance=max_distance,
            reason=reason,
            limitations=(
                "Sequence matching is a negative-control construction, not a causal null proof.",
                "Composition, callable space, and cohort transport require external calibration.",
            ),
            content_address=content_hash(body),
        )


class ChromatinContextControlMatcher:
    """Match controls by RMS distance over declared chromatin features."""

    def match(
        self,
        target: CohortVariantRecord,
        candidates: Iterable[CohortVariantRecord],
        context: ReferenceContext,
        *,
        feature_ranges: Mapping[str, tuple[float, float]],
        max_controls: int = 3,
        max_distance: float = 0.25,
    ) -> MatchedControlResult:
        if max_controls < 1 or max_distance < 0:
            raise ValidationError("chromatin control count or distance bound is invalid")
        if not feature_ranges:
            raise ValidationError("chromatin feature_ranges are required")
        values = tuple(candidates)
        target_features = target.chromatin_features
        context_pool = tuple(
            candidate
            for candidate in values
            if candidate.record_id != target.record_id
            and all(
                feature in target_features and feature in candidate.chromatin_features
                for feature in feature_ranges
            )
        )
        pool = tuple(
            candidate
            for candidate in values
            if candidate.record_id != target.record_id
            and candidate.context_key == context.key
            and all(
                feature in target_features and feature in candidate.chromatin_features
                for feature in feature_ranges
            )
        )
        scored = tuple(
            (
                candidate,
                self._distance(target_features, candidate.chromatin_features, feature_ranges),
            )
            for candidate in pool
        )
        usable = tuple(
            sorted(
                (item for item in scored if item[1] <= max_distance),
                key=lambda item: (item[1], item[0].record_id),
            )
        )
        selected = usable[:max_controls]
        controls = tuple(
            MatchedControl(
                control_id=content_hash(
                    {
                        "target": target.record_id,
                        "candidate": candidate.record_id,
                        "type": "chromatin",
                    },
                    prefix="control",
                ),
                target_id=target.record_id,
                candidate_id=candidate.record_id,
                control_type="chromatin",
                context_key=context.key,
                distance=round(distance, 9),
                matched_dimensions=tuple(sorted(feature_ranges)),
                source_id=candidate.source_id,
            )
            for candidate, distance in selected
        )
        if not pool:
            state = CohortState.OUT_OF_DOMAIN if context_pool else CohortState.ABSTAINED
            reason = (
                "chromatin feature vectors exist only outside the requested context"
                if context_pool
                else "no complete context-matched chromatin feature vectors were supplied"
            )
        elif not selected:
            state = CohortState.ABSENT
            reason = "no chromatin candidate satisfies the distance bound"
        elif len(selected) < max_controls:
            state = CohortState.PARTIAL
            reason = "fewer chromatin controls than requested satisfy the distance bound"
        else:
            state = CohortState.SUPPORTED
            reason = "chromatin-context controls selected by bounded RMS distance"
        body = {
            "target": target.record_id,
            "context": context,
            "state": state,
            "controls": controls,
            "candidate_count": len(pool),
            "max_distance": max_distance,
        }
        return MatchedControlResult(
            target_id=target.record_id,
            control_type="chromatin",
            context_key=context.key,
            state=state,
            controls=controls,
            candidate_count=len(pool),
            max_distance=max_distance,
            reason=reason,
            limitations=(
                "Chromatin matching is a negative-control construction, not a causal null proof.",
                "Feature scaling, assay calibration, and context transport require "
                "external evaluation.",
            ),
            content_address=content_hash(body),
        )

    @staticmethod
    def _distance(
        target: Mapping[str, float],
        candidate: Mapping[str, float],
        ranges: Mapping[str, tuple[float, float]],
    ) -> float:
        values = []
        for feature, bounds in ranges.items():
            span = max(1e-12, bounds[1] - bounds[0])
            values.append(((float(target[feature]) - float(candidate[feature])) / span) ** 2)
        return sqrt(fmean(values))


@dataclass(frozen=True, slots=True)
class CohortDiscoveryEvidence:
    """Combined cohort query, background, and negative-control evidence."""

    evidence_id: str
    context_key: str
    state: CohortState
    query: CohortQueryResult
    background: LocalMutationEstimate | None
    sequence_controls: tuple[MatchedControlResult, ...]
    chromatin_controls: tuple[MatchedControlResult, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CohortDiscoveryEvidenceBuilder:
    """Assemble cohort components while retaining the weakest state."""

    def build(
        self,
        evidence_id: str,
        query: CohortQueryResult,
        *,
        background: LocalMutationEstimate | None = None,
        sequence_controls: Iterable[MatchedControlResult] = (),
        chromatin_controls: Iterable[MatchedControlResult] = (),
    ) -> CohortDiscoveryEvidence:
        sequence = tuple(sequence_controls)
        chromatin = tuple(chromatin_controls)
        states = [query.state]
        if background is not None:
            states.append(background.state)
        states.extend(item.state for item in sequence + chromatin)
        if CohortState.OUT_OF_DOMAIN in states:
            state = CohortState.OUT_OF_DOMAIN
        elif CohortState.ABSTAINED in states:
            state = CohortState.ABSTAINED
        elif CohortState.AMBIGUOUS in states:
            state = CohortState.AMBIGUOUS
        elif CohortState.PARTIAL in states:
            state = CohortState.PARTIAL
        elif all(item == CohortState.SUPPORTED for item in states):
            state = CohortState.SUPPORTED
        else:
            state = CohortState.ABSENT
        body = {
            "evidence_id": evidence_id,
            "query": query,
            "background": background,
            "sequence_controls": sequence,
            "chromatin_controls": chromatin,
            "state": state,
        }
        return CohortDiscoveryEvidence(
            evidence_id=evidence_id,
            context_key=query.query.context_key,
            state=state,
            query=query,
            background=background,
            sequence_controls=sequence,
            chromatin_controls=chromatin,
            limitations=(
                "Cohort discovery evidence is research-only and is not a clinical or "
                "causal conclusion.",
                "Recurrence, controls, mutation rates, and transport require "
                "preregistered external validation.",
            ),
            content_address=content_hash(body),
        )


__all__ = [
    "CallableInterval",
    "ChromatinContextControlMatcher",
    "CohortDiscoveryEvidence",
    "CohortDiscoveryEvidenceBuilder",
    "CohortQuery",
    "CohortQueryBuilder",
    "CohortQueryResult",
    "CohortState",
    "CohortVariantRecord",
    "LocalBackgroundMutationModel",
    "LocalMutationEstimate",
    "MatchedControl",
    "MatchedControlResult",
    "SequenceContextControlMatcher",
]
