"""Scientific-beta cohort recurrence, burden, and convergence contracts.

This module extends the context-qualified cohort foundation with four
replayable research summaries:

* regulatory recurrence and local hotspot clustering;
* regional burden against an explicitly supplied callable-space comparator;
* convergence across declared functional features;
* convergence across declared pathway and regulon memberships.

Every analyzer keeps sample and variant identities, exact context, source
lineage, comparator availability, and disagreement state. The returned values
are descriptive evidence summaries. They are not p-values, clinical risk
estimates, causal null proofs, treatment signals, or claims that an observed
pattern generalizes beyond the supplied cohort and context.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty


class CohortBetaState(StrEnum):
    """State for cohort beta summaries."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class FunctionalDirection(StrEnum):
    """Declared direction for a functional observation."""

    GAIN = "gain"
    LOSS = "loss"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class SetDirection(StrEnum):
    """Declared direction for pathway or regulon evidence."""

    ACTIVATED = "activated"
    REPRESSED = "repressed"
    UNKNOWN = "unknown"


class SetKind(StrEnum):
    """Namespace for a convergence set."""

    PATHWAY = "pathway"
    REGULON = "regulon"


@dataclass(frozen=True, slots=True)
class CohortBetaIssue:
    """A quarantined input row or a non-fatal cohort contract warning."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "cohort beta issue code")
        require_non_empty(self.message, "cohort beta issue message")
        require_non_empty(self.raw_hash, "cohort beta issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("cohort beta issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RecurrenceObservation:
    """One callable or observed regulatory variant in a pseudonymous cohort."""

    record_id: str
    variant_id: str
    sample_id: str
    chromosome: str
    position: int
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    callable: bool = True
    region_id: str | None = None
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "variant_id",
            "sample_id",
            "chromosome",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.position < 1:
            raise ValidationError("recurrence observation position must be positive")
        if self.region_id is not None:
            require_non_empty(self.region_id, "recurrence observation region_id")

    @property
    def normalized_chromosome(self) -> str:
        return normalize_chromosome(self.chromosome)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RecurrenceBatch:
    """Parsed recurrence observations with row-level quarantine."""

    source_id: str
    input_hash: str
    records: tuple[RecurrenceObservation, ...]
    issues: tuple[CohortBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryRecurrenceParser:
    """Parse recurrence records from JSON or tab-separated text."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> RecurrenceBatch:
        require_non_empty(source_id, "recurrence source_id")
        rows, json_mode = _rows(text, input_format, ("records", "observations"))
        records: list[RecurrenceObservation] = []
        issues: list[CohortBetaIssue] = []
        for row_number, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    CohortBetaIssue(
                        "invalid_recurrence_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=row_number,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                records.append(_recurrence_from_mapping(row, source_id, source_version, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CohortBetaIssue(
                        "invalid_recurrence_row",
                        str(exc),
                        raw_hash,
                        row_number=row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return RecurrenceBatch(
            source_id=source_id,
            input_hash=input_hash,
            records=tuple(records),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "records": records,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class HotspotSummary:
    """A local cluster of distinct variants and samples."""

    hotspot_id: str
    chromosome: str
    start: int
    end: int
    variant_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    window_bp: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryRecurrenceResult:
    """Descriptive recurrence and hotspot summary."""

    context_key: str
    target_region_id: str | None
    state: CohortBetaState
    observed_variant_count: int
    observed_sample_count: int
    recurrent_variant_ids: tuple[str, ...]
    hotspots: tuple[HotspotSummary, ...]
    variant_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    recurrence_fraction: float | None
    source_ids: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryRecurrenceTester:
    """Deduplicate cohort observations and identify local recurrence clusters."""

    def test(
        self,
        observations: Iterable[RecurrenceObservation | Mapping[str, Any]],
        *,
        context_key: str,
        target_region_id: str | None = None,
        minimum_recurrent_samples: int = 2,
        hotspot_window_bp: int = 50,
        minimum_hotspot_variants: int = 2,
        minimum_hotspot_samples: int = 2,
    ) -> RegulatoryRecurrenceResult:
        require_non_empty(context_key, "recurrence context_key")
        if minimum_recurrent_samples < 2:
            raise ValidationError("minimum_recurrent_samples must be at least two")
        if hotspot_window_bp < 0:
            raise ValidationError("hotspot_window_bp cannot be negative")
        if minimum_hotspot_variants < 2 or minimum_hotspot_samples < 2:
            raise ValidationError("hotspot thresholds must be at least two")
        values = tuple(_coerce_recurrence(item) for item in observations)
        scoped = tuple(
            item
            for item in values
            if target_region_id is None or item.region_id == target_region_id
        )
        exact = tuple(item for item in scoped if item.context_key == context_key)
        if not exact:
            state = CohortBetaState.OUT_OF_DOMAIN if scoped else CohortBetaState.ABSTAINED
            reason = (
                "recurrence observations exist only outside the requested context"
                if scoped
                else "no recurrence observations were supplied"
            )
            return self._result(
                context_key,
                target_region_id,
                state,
                (),
                (),
                (),
                (),
                (),
                None,
                (),
                reason,
            )
        callable_rows = tuple(item for item in exact if item.callable)
        if not callable_rows:
            return self._result(
                context_key,
                target_region_id,
                CohortBetaState.PARTIAL,
                (),
                (),
                (),
                (),
                (),
                None,
                tuple(sorted({item.source_id for item in exact})),
                "all exact-context recurrence rows are non-callable",
            )
        by_variant: dict[str, list[RecurrenceObservation]] = defaultdict(list)
        for item in callable_rows:
            by_variant[item.variant_id].append(item)
        variant_ids = tuple(sorted(by_variant))
        sample_ids = tuple(sorted({item.sample_id for item in callable_rows}))
        record_ids = tuple(sorted({item.record_id for item in callable_rows}))
        recurrent = tuple(
            sorted(
                variant_id
                for variant_id, rows in by_variant.items()
                if len({item.sample_id for item in rows}) >= minimum_recurrent_samples
            )
        )
        hotspots = self._hotspots(
            callable_rows,
            hotspot_window_bp=hotspot_window_bp,
            minimum_variants=minimum_hotspot_variants,
            minimum_samples=minimum_hotspot_samples,
        )
        if recurrent or hotspots:
            state = CohortBetaState.SUPPORTED
            reason = "distinct samples support recurrence or a local regulatory hotspot"
        else:
            state = CohortBetaState.ABSENT
            reason = "no variant recurrence or hotspot met the declared thresholds"
        return self._result(
            context_key,
            target_region_id,
            state,
            variant_ids,
            sample_ids,
            record_ids,
            recurrent,
            hotspots,
            round(len(recurrent) / len(variant_ids), 9) if variant_ids else None,
            tuple(sorted({item.source_id for item in callable_rows})),
            reason,
        )

    @staticmethod
    def _hotspots(
        rows: tuple[RecurrenceObservation, ...],
        *,
        hotspot_window_bp: int,
        minimum_variants: int,
        minimum_samples: int,
    ) -> tuple[HotspotSummary, ...]:
        ordered = sorted(
            rows, key=lambda item: (item.normalized_chromosome, item.position, item.variant_id)
        )
        clusters: list[list[RecurrenceObservation]] = []
        for row in ordered:
            if (
                not clusters
                or row.normalized_chromosome != clusters[-1][-1].normalized_chromosome
                or row.position - clusters[-1][-1].position > hotspot_window_bp
            ):
                clusters.append([row])
            else:
                clusters[-1].append(row)
        summaries: list[HotspotSummary] = []
        for cluster in clusters:
            variants = tuple(sorted({item.variant_id for item in cluster}))
            samples = tuple(sorted({item.sample_id for item in cluster}))
            if len(variants) < minimum_variants or len(samples) < minimum_samples:
                continue
            chromosome = cluster[0].normalized_chromosome
            start = min(item.position for item in cluster)
            end = max(item.position for item in cluster)
            record_ids = tuple(sorted({item.record_id for item in cluster}))
            source_ids = tuple(sorted({item.source_id for item in cluster}))
            hotspot_id = content_hash(
                {
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "variant_ids": variants,
                    "sample_ids": samples,
                },
                prefix="hotspot",
            )
            summaries.append(
                HotspotSummary(
                    hotspot_id=hotspot_id,
                    chromosome=chromosome,
                    start=start,
                    end=end,
                    variant_ids=variants,
                    sample_ids=samples,
                    record_ids=record_ids,
                    source_ids=source_ids,
                    window_bp=hotspot_window_bp,
                )
            )
        return tuple(summaries)

    @staticmethod
    def _result(
        context_key: str,
        target_region_id: str | None,
        state: CohortBetaState,
        variant_ids: tuple[str, ...],
        sample_ids: tuple[str, ...],
        record_ids: tuple[str, ...],
        recurrent_variant_ids: tuple[str, ...],
        hotspots: tuple[HotspotSummary, ...],
        recurrence_fraction: float | None,
        source_ids: tuple[str, ...],
        reason: str,
    ) -> RegulatoryRecurrenceResult:
        body = {
            "context_key": context_key,
            "target_region_id": target_region_id,
            "state": state,
            "variant_ids": variant_ids,
            "sample_ids": sample_ids,
            "recurrent_variant_ids": recurrent_variant_ids,
            "hotspots": hotspots,
        }
        return RegulatoryRecurrenceResult(
            context_key=context_key,
            target_region_id=target_region_id,
            state=state,
            observed_variant_count=len(variant_ids),
            observed_sample_count=len(sample_ids),
            recurrent_variant_ids=recurrent_variant_ids,
            hotspots=hotspots,
            variant_ids=variant_ids,
            sample_ids=sample_ids,
            record_ids=record_ids,
            recurrence_fraction=recurrence_fraction,
            source_ids=source_ids,
            reason=reason,
            warnings=(
                "Recurrence counts distinct supplied samples and are not a calibrated "
                "enrichment test.",
                "Callable-space, cohort composition, ancestry, batch, and ascertainment "
                "can change recurrence.",
                "A hotspot is a local descriptive cluster and is not proof of a regulatory driver.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class RegionalBurdenRegion:
    """A context-qualified genomic region with callable-base accounting."""

    region_id: str
    chromosome: str
    start: int
    end: int
    callable_bases: int
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "region_id",
            "chromosome",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("regional burden coordinates are invalid")
        if self.callable_bases < 1:
            raise ValidationError("regional burden callable_bases must be positive")

    def contains(self, observation: RecurrenceObservation) -> bool:
        return (
            self.context_key == observation.context_key
            and self.chromosome == observation.chromosome
            and self.start <= observation.position <= self.end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegionalBurdenBatch:
    """Parsed region and observation bundle."""

    source_id: str
    input_hash: str
    regions: tuple[RegionalBurdenRegion, ...]
    observations: tuple[RecurrenceObservation, ...]
    issues: tuple[CohortBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegionalBurdenParser:
    """Parse a JSON bundle containing regions and recurrence-shaped observations."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
    ) -> RegionalBurdenBatch:
        require_non_empty(source_id, "regional burden source_id")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid regional burden JSON: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ValidationError("regional burden JSON must be an object")
        regions_raw = payload.get("regions", ())
        records_raw = payload.get("observations", payload.get("records", ()))
        if not isinstance(regions_raw, list) or not isinstance(records_raw, list):
            raise ValidationError("regional burden JSON needs regions and observations lists")
        regions: list[RegionalBurdenRegion] = []
        observations: list[RecurrenceObservation] = []
        issues: list[CohortBetaIssue] = []
        for index, row in enumerate(regions_raw, start=1):
            try:
                if not isinstance(row, Mapping):
                    raise ValidationError("region row must be an object")
                regions.append(
                    _region_from_mapping(row, source_id, source_version, content_hash(row))
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raw = row if isinstance(row, Mapping) else {"value": row}
                issues.append(
                    CohortBetaIssue(
                        "invalid_regional_region",
                        str(exc),
                        content_hash(raw),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(raw),
                    )
                )
        for index, row in enumerate(records_raw, start=1):
            try:
                if not isinstance(row, Mapping):
                    raise ValidationError("observation row must be an object")
                observations.append(
                    _recurrence_from_mapping(row, source_id, source_version, content_hash(row))
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raw = row if isinstance(row, Mapping) else {"value": row}
                issues.append(
                    CohortBetaIssue(
                        "invalid_regional_observation",
                        str(exc),
                        content_hash(raw),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(raw),
                    )
                )
        input_hash = content_hash(text)
        return RegionalBurdenBatch(
            source_id=source_id,
            input_hash=input_hash,
            regions=tuple(regions),
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "regions": regions,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class RegionalBurdenResult:
    """Descriptive regional burden and callable-space comparator summary."""

    region_id: str
    context_key: str
    state: CohortBetaState
    callable_bases: int
    observed_variant_count: int
    observed_sample_count: int
    variant_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    background_rate: float | None
    expected_count: float | None
    burden_per_kb: float | None
    excess_ratio: float | None
    source_ids: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegionalBurdenTester:
    """Compare regional observations with an explicit callable-space rate."""

    def test(
        self,
        regions: Iterable[RegionalBurdenRegion | Mapping[str, Any]],
        observations: Iterable[RecurrenceObservation | Mapping[str, Any]],
        *,
        region_id: str,
        context_key: str,
        background_rate: float | None = None,
    ) -> RegionalBurdenResult:
        require_non_empty(region_id, "regional burden region_id")
        require_non_empty(context_key, "regional burden context_key")
        if background_rate is not None and (not isfinite(background_rate) or background_rate < 0):
            raise ValidationError("regional burden background_rate must be finite and non-negative")
        region_values = tuple(_coerce_region(item) for item in regions)
        candidates = tuple(item for item in region_values if item.region_id == region_id)
        exact_regions = tuple(item for item in candidates if item.context_key == context_key)
        if not exact_regions:
            state = CohortBetaState.OUT_OF_DOMAIN if candidates else CohortBetaState.ABSTAINED
            return self._result(
                region_id,
                context_key,
                state,
                0,
                (),
                (),
                background_rate,
                None,
                None,
                None,
                (),
                "no region matches the requested exact context",
            )
        if len(exact_regions) > 1:
            raise ValidationError(
                "regional burden region_id must resolve to one exact-context region"
            )
        region = exact_regions[0]
        values = tuple(_coerce_recurrence(item) for item in observations)
        scoped = tuple(item for item in values if item.context_key == context_key)
        overlapping = tuple(item for item in scoped if item.callable and region.contains(item))
        variant_ids = tuple(sorted({item.variant_id for item in overlapping}))
        sample_ids = tuple(sorted({item.sample_id for item in overlapping}))
        expected = None if background_rate is None else background_rate * region.callable_bases
        burden = len(variant_ids) / region.callable_bases * 1000
        excess = None
        if expected is not None:
            excess = len(variant_ids) / max(expected, 1e-12)
        if not scoped and values:
            state = CohortBetaState.OUT_OF_DOMAIN
            reason = "observations exist only outside the requested context"
        elif not overlapping:
            state = (
                CohortBetaState.ABSENT if background_rate is not None else CohortBetaState.PARTIAL
            )
            reason = (
                "no callable observations overlap the region"
                if background_rate is not None
                else "no callable observations overlap and no comparator was supplied"
            )
        elif background_rate is None:
            state = CohortBetaState.PARTIAL
            reason = "regional burden is described but no callable-space comparator was supplied"
        elif len(variant_ids) > expected:
            state = CohortBetaState.SUPPORTED
            reason = "observed regional burden exceeds the supplied descriptive comparator"
        else:
            state = CohortBetaState.ABSENT
            reason = "observed regional burden does not exceed the supplied descriptive comparator"
        return self._result(
            region_id,
            context_key,
            state,
            region.callable_bases,
            variant_ids,
            sample_ids,
            background_rate,
            expected,
            burden,
            excess,
            tuple(sorted({item.source_id for item in overlapping})),
            reason,
        )

    @staticmethod
    def _result(
        region_id: str,
        context_key: str,
        state: CohortBetaState,
        callable_bases: int,
        variant_ids: tuple[str, ...],
        sample_ids: tuple[str, ...],
        background_rate: float | None,
        expected_count: float | None,
        burden_per_kb: float | None,
        excess_ratio: float | None,
        source_ids: tuple[str, ...],
        reason: str,
    ) -> RegionalBurdenResult:
        body = {
            "region_id": region_id,
            "context_key": context_key,
            "state": state,
            "callable_bases": callable_bases,
            "variant_ids": variant_ids,
            "sample_ids": sample_ids,
            "background_rate": background_rate,
        }
        return RegionalBurdenResult(
            region_id=region_id,
            context_key=context_key,
            state=state,
            callable_bases=callable_bases,
            observed_variant_count=len(variant_ids),
            observed_sample_count=len(sample_ids),
            variant_ids=variant_ids,
            sample_ids=sample_ids,
            background_rate=background_rate,
            expected_count=None if expected_count is None else round(expected_count, 9),
            burden_per_kb=None if burden_per_kb is None else round(burden_per_kb, 9),
            excess_ratio=None if excess_ratio is None else round(excess_ratio, 9),
            source_ids=source_ids,
            reason=reason,
            warnings=(
                "Regional burden is a callable-space descriptive comparison, not a p-value "
                "or significance claim.",
                "Variant deduplication, cohort composition, callable intervals, and "
                "ascertainment affect the summary.",
                "A burden excess does not establish a driver mechanism or clinical relevance.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class FunctionalConvergenceObservation:
    """A declared functional annotation for an observed or control variant."""

    observation_id: str
    variant_id: str
    sample_id: str
    feature_id: str
    feature_class: str
    support: float
    direction: FunctionalDirection
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    is_control: bool = False
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "sample_id",
            "feature_id",
            "feature_class",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1:
            raise ValidationError("functional support must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FunctionalConvergenceFeature:
    """Aggregated observed/control feature contrast."""

    feature_id: str
    feature_class: str
    observed_variant_count: int
    observed_sample_count: int
    control_variant_count: int
    control_sample_count: int
    observed_support: float
    control_support: float | None
    contrast: float | None
    gain_count: int
    loss_count: int
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FunctionalConvergenceBatch:
    """Parsed functional observations with row-level quarantine."""

    source_id: str
    input_hash: str
    observations: tuple[FunctionalConvergenceObservation, ...]
    issues: tuple[CohortBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FunctionalConvergenceParser:
    """Parse functional convergence observations from JSON or TSV."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> FunctionalConvergenceBatch:
        require_non_empty(source_id, "functional source_id")
        rows, json_mode = _rows(text, input_format, ("observations", "records"))
        observations: list[FunctionalConvergenceObservation] = []
        issues: list[CohortBetaIssue] = []
        for row_number, row in enumerate(rows, start=1 if json_mode else 2):
            raw = row if isinstance(row, Mapping) else {"value": row}
            raw_hash = content_hash(raw)
            try:
                if not isinstance(row, Mapping):
                    raise ValidationError("functional convergence row must be an object")
                observations.append(
                    _functional_from_mapping(row, source_id, source_version, raw_hash)
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CohortBetaIssue(
                        "invalid_functional_row",
                        str(exc),
                        raw_hash,
                        row_number=row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(raw),
                    )
                )
        input_hash = content_hash(text)
        return FunctionalConvergenceBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class FunctionalConvergenceResult:
    """Feature-level convergence contrast with comparator and tie accounting."""

    context_key: str
    state: CohortBetaState
    features: tuple[FunctionalConvergenceFeature, ...]
    leading_feature_ids: tuple[str, ...]
    convergence_score: float | None
    control_available: bool
    observed_variant_count: int
    observed_sample_count: int
    source_ids: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FunctionalConvergenceTester:
    """Measure feature convergence using an optional matched-control comparator."""

    def test(
        self,
        observations: Iterable[FunctionalConvergenceObservation | Mapping[str, Any]],
        *,
        context_key: str,
        minimum_observed_variants: int = 1,
        ambiguity_margin: float = 0.05,
    ) -> FunctionalConvergenceResult:
        require_non_empty(context_key, "functional convergence context_key")
        if minimum_observed_variants < 1 or ambiguity_margin < 0:
            raise ValidationError("functional convergence thresholds are invalid")
        values = tuple(_coerce_functional(item) for item in observations)
        exact = tuple(item for item in values if item.context_key == context_key)
        if not exact:
            state = CohortBetaState.OUT_OF_DOMAIN if values else CohortBetaState.ABSTAINED
            return self._result(
                context_key,
                state,
                (),
                (),
                None,
                False,
                (),
                (),
                (),
                "no functional observations match the exact context",
            )
        observed = tuple(item for item in exact if not item.is_control)
        controls = tuple(item for item in exact if item.is_control)
        if not observed:
            return self._result(
                context_key,
                CohortBetaState.ABSENT,
                (),
                (),
                None,
                bool(controls),
                (),
                (),
                tuple(sorted({item.source_id for item in exact})),
                "no observed functional variants were supplied",
            )
        observed_variant_ids = {item.variant_id for item in observed}
        if len(observed_variant_ids) < minimum_observed_variants:
            state = CohortBetaState.PARTIAL
            reason = "observed functional cohort is smaller than the declared minimum"
        else:
            state = CohortBetaState.PARTIAL if not controls else CohortBetaState.SUPPORTED
            reason = (
                "functional convergence is contrasted with matched controls"
                if controls
                else "functional convergence is summarized without a control comparator"
            )
        features = self._features(observed, controls)
        ranked = tuple(
            sorted(
                features,
                key=lambda item: (
                    -(item.contrast if item.contrast is not None else item.observed_support),
                    item.feature_class,
                    item.feature_id,
                ),
            )
        )
        leading: tuple[str, ...] = ()
        score: float | None = None
        if ranked:
            score = (
                ranked[0].contrast if ranked[0].contrast is not None else ranked[0].observed_support
            )
            leading = tuple(
                item.feature_id
                for item in ranked
                if abs(
                    (item.contrast if item.contrast is not None else item.observed_support) - score
                )
                <= ambiguity_margin
            )
            if len(leading) > 1 and controls:
                state = CohortBetaState.AMBIGUOUS
                reason = "multiple functional features lead within the declared ambiguity margin"
        return self._result(
            context_key,
            state,
            ranked,
            leading,
            score,
            bool(controls),
            tuple(sorted(observed_variant_ids)),
            tuple(sorted({item.sample_id for item in observed})),
            tuple(sorted({item.source_id for item in exact})),
            reason,
        )

    @staticmethod
    def _features(
        observed: tuple[FunctionalConvergenceObservation, ...],
        controls: tuple[FunctionalConvergenceObservation, ...],
    ) -> tuple[FunctionalConvergenceFeature, ...]:
        keys = sorted({(item.feature_id, item.feature_class) for item in observed + controls})
        output: list[FunctionalConvergenceFeature] = []
        for feature_id, feature_class in keys:
            observed_rows = tuple(
                item
                for item in observed
                if item.feature_id == feature_id and item.feature_class == feature_class
            )
            control_rows = tuple(
                item
                for item in controls
                if item.feature_id == feature_id and item.feature_class == feature_class
            )
            observed_by_variant = _max_support_by_variant(observed_rows)
            control_by_variant = _max_support_by_variant(control_rows)
            observed_support = fmean(observed_by_variant.values()) if observed_by_variant else 0.0
            control_support = fmean(control_by_variant.values()) if control_by_variant else None
            contrast = observed_support - control_support if control_support is not None else None
            output.append(
                FunctionalConvergenceFeature(
                    feature_id=feature_id,
                    feature_class=feature_class,
                    observed_variant_count=len(observed_by_variant),
                    observed_sample_count=len({item.sample_id for item in observed_rows}),
                    control_variant_count=len(control_by_variant),
                    control_sample_count=len({item.sample_id for item in control_rows}),
                    observed_support=round(observed_support, 9),
                    control_support=None if control_support is None else round(control_support, 9),
                    contrast=None if contrast is None else round(contrast, 9),
                    gain_count=sum(
                        item.direction == FunctionalDirection.GAIN for item in observed_rows
                    ),
                    loss_count=sum(
                        item.direction == FunctionalDirection.LOSS for item in observed_rows
                    ),
                    source_ids=tuple(
                        sorted({item.source_id for item in observed_rows + control_rows})
                    ),
                )
            )
        return tuple(output)

    @staticmethod
    def _result(
        context_key: str,
        state: CohortBetaState,
        features: tuple[FunctionalConvergenceFeature, ...],
        leading_feature_ids: tuple[str, ...],
        convergence_score: float | None,
        control_available: bool,
        observed_variant_ids: tuple[str, ...],
        observed_sample_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        reason: str,
    ) -> FunctionalConvergenceResult:
        body = {
            "context_key": context_key,
            "state": state,
            "features": features,
            "leading_feature_ids": leading_feature_ids,
            "convergence_score": convergence_score,
        }
        return FunctionalConvergenceResult(
            context_key=context_key,
            state=state,
            features=features,
            leading_feature_ids=leading_feature_ids,
            convergence_score=convergence_score,
            control_available=control_available,
            observed_variant_count=len(observed_variant_ids),
            observed_sample_count=len(observed_sample_ids),
            source_ids=source_ids,
            reason=reason,
            warnings=(
                "Functional convergence is a bounded feature contrast, not a p-value or "
                "causal effect estimate.",
                "Feature definitions, matched controls, source dependence, and cohort "
                "transport require validation.",
                "Leading features remain alternatives when scores are tied or comparator "
                "coverage is incomplete.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class PathwayRegulonObservation:
    """A gene-to-set membership observation for an observed or control variant."""

    observation_id: str
    variant_id: str
    sample_id: str
    gene_id: str
    set_id: str
    set_kind: SetKind
    support: float
    direction: SetDirection
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    is_control: bool = False
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "sample_id",
            "gene_id",
            "set_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1:
            raise ValidationError("pathway/regulon support must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PathwayRegulonSetSummary:
    """Aggregated pathway/regulon coverage and direction summary."""

    set_id: str
    set_kind: SetKind
    observed_gene_count: int
    observed_variant_count: int
    control_gene_count: int
    control_variant_count: int
    observed_support: float
    control_support: float | None
    contrast: float | None
    activated_fraction: float
    repressed_fraction: float
    directional_conflict: bool
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PathwayRegulonBatch:
    """Parsed pathway/regulon observations with row-level quarantine."""

    source_id: str
    input_hash: str
    observations: tuple[PathwayRegulonObservation, ...]
    issues: tuple[CohortBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PathwayRegulonParser:
    """Parse pathway/regulon membership observations."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> PathwayRegulonBatch:
        require_non_empty(source_id, "pathway source_id")
        rows, json_mode = _rows(text, input_format, ("observations", "records"))
        observations: list[PathwayRegulonObservation] = []
        issues: list[CohortBetaIssue] = []
        for row_number, row in enumerate(rows, start=1 if json_mode else 2):
            raw = row if isinstance(row, Mapping) else {"value": row}
            raw_hash = content_hash(raw)
            try:
                if not isinstance(row, Mapping):
                    raise ValidationError("pathway/regulon row must be an object")
                observations.append(_pathway_from_mapping(row, source_id, source_version, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CohortBetaIssue(
                        "invalid_pathway_regulon_row",
                        str(exc),
                        raw_hash,
                        row_number=row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(raw),
                    )
                )
        input_hash = content_hash(text)
        return PathwayRegulonBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class PathwayRegulonConvergenceResult:
    """Set-level convergence result with direction conflicts retained."""

    context_key: str
    state: CohortBetaState
    sets: tuple[PathwayRegulonSetSummary, ...]
    leading_set_ids: tuple[str, ...]
    convergence_score: float | None
    control_available: bool
    observed_gene_count: int
    observed_variant_count: int
    source_ids: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PathwayRegulonConvergenceTester:
    """Measure convergence over declared pathway or regulon memberships."""

    def test(
        self,
        observations: Iterable[PathwayRegulonObservation | Mapping[str, Any]],
        *,
        context_key: str,
        set_kind: SetKind | str | None = None,
        minimum_genes: int = 2,
        ambiguity_margin: float = 0.05,
    ) -> PathwayRegulonConvergenceResult:
        require_non_empty(context_key, "pathway convergence context_key")
        if minimum_genes < 1 or ambiguity_margin < 0:
            raise ValidationError("pathway convergence thresholds are invalid")
        requested_kind = None if set_kind is None else SetKind(str(set_kind))
        values = tuple(_coerce_pathway(item) for item in observations)
        kind_values = tuple(
            item for item in values if requested_kind is None or item.set_kind == requested_kind
        )
        exact = tuple(item for item in kind_values if item.context_key == context_key)
        if not exact:
            state = CohortBetaState.OUT_OF_DOMAIN if kind_values else CohortBetaState.ABSTAINED
            return self._result(
                context_key,
                state,
                (),
                (),
                None,
                False,
                (),
                (),
                (),
                "no pathway/regulon observations match the requested context",
            )
        observed = tuple(item for item in exact if not item.is_control)
        controls = tuple(item for item in exact if item.is_control)
        summaries = tuple(
            item
            for item in self._sets(observed, controls)
            if item.observed_gene_count >= minimum_genes
        )
        observed_genes = tuple(sorted({item.gene_id for item in observed}))
        observed_variants = tuple(sorted({item.variant_id for item in observed}))
        if not observed:
            state = CohortBetaState.ABSENT
            reason = "no observed pathway/regulon memberships were supplied"
        elif not summaries:
            state = CohortBetaState.PARTIAL
            reason = "no declared pathway/regulon set reached the minimum gene coverage"
        elif not controls:
            state = CohortBetaState.PARTIAL
            reason = "pathway/regulon convergence is summarized without a control comparator"
        else:
            state = CohortBetaState.SUPPORTED
            reason = "pathway/regulon convergence is contrasted with matched controls"
        ranked = tuple(
            sorted(
                summaries,
                key=lambda item: (
                    -(item.contrast if item.contrast is not None else item.observed_support),
                    item.set_kind.value,
                    item.set_id,
                ),
            )
        )
        leading: tuple[str, ...] = ()
        score: float | None = None
        if ranked:
            score = (
                ranked[0].contrast if ranked[0].contrast is not None else ranked[0].observed_support
            )
            leading = tuple(
                item.set_id
                for item in ranked
                if abs(
                    (item.contrast if item.contrast is not None else item.observed_support) - score
                )
                <= ambiguity_margin
            )
            if len(leading) > 1 and controls:
                state = CohortBetaState.AMBIGUOUS
                reason = "multiple pathway/regulon sets lead within the declared ambiguity margin"
            if any(item.directional_conflict for item in ranked if item.set_id in leading):
                state = CohortBetaState.CONTRADICTORY
                reason = "leading pathway/regulon evidence contains opposing declared directions"
        return self._result(
            context_key,
            state,
            ranked,
            leading,
            score,
            bool(controls),
            observed_genes,
            observed_variants,
            tuple(sorted({item.source_id for item in exact})),
            reason,
        )

    @staticmethod
    def _sets(
        observed: tuple[PathwayRegulonObservation, ...],
        controls: tuple[PathwayRegulonObservation, ...],
    ) -> tuple[PathwayRegulonSetSummary, ...]:
        keys = sorted(
            {(item.set_id, item.set_kind) for item in observed + controls},
            key=lambda item: (item[1].value, item[0]),
        )
        output: list[PathwayRegulonSetSummary] = []
        for set_id, set_kind in keys:
            observed_rows = tuple(
                item for item in observed if item.set_id == set_id and item.set_kind == set_kind
            )
            control_rows = tuple(
                item for item in controls if item.set_id == set_id and item.set_kind == set_kind
            )
            observed_by_gene = _max_support_by_gene(observed_rows)
            control_by_gene = _max_support_by_gene(control_rows)
            observed_support = fmean(observed_by_gene.values()) if observed_by_gene else 0.0
            control_support = fmean(control_by_gene.values()) if control_by_gene else None
            contrast = observed_support - control_support if control_support is not None else None
            directional = [
                item.direction for item in observed_rows if item.direction != SetDirection.UNKNOWN
            ]
            activated = sum(item == SetDirection.ACTIVATED for item in directional)
            repressed = sum(item == SetDirection.REPRESSED for item in directional)
            direction_total = activated + repressed
            output.append(
                PathwayRegulonSetSummary(
                    set_id=set_id,
                    set_kind=set_kind,
                    observed_gene_count=len(observed_by_gene),
                    observed_variant_count=len({item.variant_id for item in observed_rows}),
                    control_gene_count=len(control_by_gene),
                    control_variant_count=len({item.variant_id for item in control_rows}),
                    observed_support=round(observed_support, 9),
                    control_support=None if control_support is None else round(control_support, 9),
                    contrast=None if contrast is None else round(contrast, 9),
                    activated_fraction=round(activated / direction_total, 9)
                    if direction_total
                    else 0.0,
                    repressed_fraction=round(repressed / direction_total, 9)
                    if direction_total
                    else 0.0,
                    directional_conflict=activated > 0 and repressed > 0,
                    source_ids=tuple(
                        sorted({item.source_id for item in observed_rows + control_rows})
                    ),
                )
            )
        return tuple(output)

    @staticmethod
    def _result(
        context_key: str,
        state: CohortBetaState,
        sets: tuple[PathwayRegulonSetSummary, ...],
        leading_set_ids: tuple[str, ...],
        convergence_score: float | None,
        control_available: bool,
        observed_gene_ids: tuple[str, ...],
        observed_variant_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        reason: str,
    ) -> PathwayRegulonConvergenceResult:
        body = {
            "context_key": context_key,
            "state": state,
            "sets": sets,
            "leading_set_ids": leading_set_ids,
            "convergence_score": convergence_score,
        }
        return PathwayRegulonConvergenceResult(
            context_key=context_key,
            state=state,
            sets=sets,
            leading_set_ids=leading_set_ids,
            convergence_score=convergence_score,
            control_available=control_available,
            observed_gene_count=len(observed_gene_ids),
            observed_variant_count=len(observed_variant_ids),
            source_ids=source_ids,
            reason=reason,
            warnings=(
                "Pathway/regulon convergence is a bounded membership summary, not a p-value "
                "or causal pathway claim.",
                "Gene-set definitions, overlapping memberships, source dependence, and "
                "cohort transport require validation.",
                "Opposing declared directions are retained as contradictory rather than "
                "averaged away.",
            ),
            content_address=content_hash(body),
        )


def _rows(
    text: str,
    input_format: str | None,
    keys: tuple[str, ...],
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("cohort beta input must not be empty")
    selected = (input_format or "").lower().strip()
    if not selected:
        selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
    if selected == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid cohort beta JSON: {exc}") from exc
        rows: Any = payload
        if isinstance(payload, Mapping):
            for key in keys:
                if key in payload:
                    rows = payload[key]
                    break
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValidationError("cohort beta JSON rows must be a list")
        return tuple(rows), True
    if selected == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("cohort beta TSV requires a header")
        return tuple(reader), False
    raise ValidationError(f"unsupported cohort beta format: {selected}")


def _required(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    if default is not None:
        return default
    raise ValidationError(f"cohort beta field is required: {names[0]}")


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.lower().strip()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _recurrence_from_mapping(
    row: Mapping[str, Any],
    source_id: str,
    source_version: str,
    raw_hash: str,
) -> RecurrenceObservation:
    return RecurrenceObservation(
        record_id=str(_required(row, "record_id", "id")),
        variant_id=str(_required(row, "variant_id", "variant")),
        sample_id=str(_required(row, "sample_id", "sample")),
        chromosome=str(_required(row, "chromosome", "chr")),
        position=int(_required(row, "position", "start")),
        context_key=str(_required(row, "context_key", "context")),
        source_id=str(row.get("source_id", source_id)),
        source_version=str(row.get("source_version", row.get("version", source_version))),
        raw_hash=str(row.get("raw_hash", raw_hash)),
        callable=_as_bool(row.get("callable"), default=True),
        region_id=(str(row["region_id"]) if row.get("region_id") not in (None, "") else None),
        annotations=dict(row.get("annotations", {})),
    )


def _region_from_mapping(
    row: Mapping[str, Any],
    source_id: str,
    source_version: str,
    raw_hash: str,
) -> RegionalBurdenRegion:
    return RegionalBurdenRegion(
        region_id=str(_required(row, "region_id", "id")),
        chromosome=str(_required(row, "chromosome", "chr")),
        start=int(_required(row, "start")),
        end=int(_required(row, "end")),
        callable_bases=int(_required(row, "callable_bases", "callable")),
        context_key=str(_required(row, "context_key", "context")),
        source_id=str(row.get("source_id", source_id)),
        source_version=str(row.get("source_version", row.get("version", source_version))),
        raw_hash=str(row.get("raw_hash", raw_hash)),
        annotations=dict(row.get("annotations", {})),
    )


def _functional_from_mapping(
    row: Mapping[str, Any],
    source_id: str,
    source_version: str,
    raw_hash: str,
) -> FunctionalConvergenceObservation:
    return FunctionalConvergenceObservation(
        observation_id=str(_required(row, "observation_id", "id")),
        variant_id=str(_required(row, "variant_id", "variant")),
        sample_id=str(_required(row, "sample_id", "sample")),
        feature_id=str(_required(row, "feature_id", "feature")),
        feature_class=str(_required(row, "feature_class", "class")),
        support=float(_required(row, "support", "score")),
        direction=FunctionalDirection(str(row.get("direction", FunctionalDirection.UNKNOWN.value))),
        context_key=str(_required(row, "context_key", "context")),
        source_id=str(row.get("source_id", source_id)),
        source_version=str(row.get("source_version", row.get("version", source_version))),
        raw_hash=str(row.get("raw_hash", raw_hash)),
        is_control=_as_bool(row.get("is_control"), default=False),
        annotations=dict(row.get("annotations", {})),
    )


def _pathway_from_mapping(
    row: Mapping[str, Any],
    source_id: str,
    source_version: str,
    raw_hash: str,
) -> PathwayRegulonObservation:
    return PathwayRegulonObservation(
        observation_id=str(_required(row, "observation_id", "id")),
        variant_id=str(_required(row, "variant_id", "variant")),
        sample_id=str(_required(row, "sample_id", "sample")),
        gene_id=str(_required(row, "gene_id", "gene")),
        set_id=str(_required(row, "set_id", "pathway_id", "regulon_id")),
        set_kind=SetKind(str(row.get("set_kind", SetKind.PATHWAY.value))),
        support=float(_required(row, "support", "score")),
        direction=SetDirection(str(row.get("direction", SetDirection.UNKNOWN.value))),
        context_key=str(_required(row, "context_key", "context")),
        source_id=str(row.get("source_id", source_id)),
        source_version=str(row.get("source_version", row.get("version", source_version))),
        raw_hash=str(row.get("raw_hash", raw_hash)),
        is_control=_as_bool(row.get("is_control"), default=False),
        annotations=dict(row.get("annotations", {})),
    )


def _coerce_recurrence(value: RecurrenceObservation | Mapping[str, Any]) -> RecurrenceObservation:
    if isinstance(value, RecurrenceObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("recurrence observation must be a mapping")
    raw_hash = str(value.get("raw_hash", content_hash(dict(value))))
    return _recurrence_from_mapping(
        value,
        str(value.get("source_id", "cohort-input")),
        str(value.get("source_version", "unspecified")),
        raw_hash,
    )


def _coerce_region(value: RegionalBurdenRegion | Mapping[str, Any]) -> RegionalBurdenRegion:
    if isinstance(value, RegionalBurdenRegion):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("regional burden region must be a mapping")
    raw_hash = str(value.get("raw_hash", content_hash(dict(value))))
    return _region_from_mapping(
        value,
        str(value.get("source_id", "region-input")),
        str(value.get("source_version", "unspecified")),
        raw_hash,
    )


def _coerce_functional(
    value: FunctionalConvergenceObservation | Mapping[str, Any],
) -> FunctionalConvergenceObservation:
    if isinstance(value, FunctionalConvergenceObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("functional convergence observation must be a mapping")
    raw_hash = str(value.get("raw_hash", content_hash(dict(value))))
    return _functional_from_mapping(
        value,
        str(value.get("source_id", "functional-input")),
        str(value.get("source_version", "unspecified")),
        raw_hash,
    )


def _coerce_pathway(
    value: PathwayRegulonObservation | Mapping[str, Any],
) -> PathwayRegulonObservation:
    if isinstance(value, PathwayRegulonObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("pathway/regulon observation must be a mapping")
    raw_hash = str(value.get("raw_hash", content_hash(dict(value))))
    return _pathway_from_mapping(
        value,
        str(value.get("source_id", "pathway-input")),
        str(value.get("source_version", "unspecified")),
        raw_hash,
    )


def _max_support_by_variant(
    rows: Iterable[FunctionalConvergenceObservation],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in rows:
        values[row.variant_id] = max(values.get(row.variant_id, 0.0), row.support)
    return values


def _max_support_by_gene(rows: Iterable[PathwayRegulonObservation]) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in rows:
        values[row.gene_id] = max(values.get(row.gene_id, 0.0), row.support)
    return values


__all__ = [
    "CohortBetaIssue",
    "CohortBetaState",
    "FunctionalConvergenceBatch",
    "FunctionalConvergenceFeature",
    "FunctionalConvergenceObservation",
    "FunctionalConvergenceParser",
    "FunctionalConvergenceResult",
    "FunctionalConvergenceTester",
    "FunctionalDirection",
    "HotspotSummary",
    "PathwayRegulonBatch",
    "PathwayRegulonConvergenceResult",
    "PathwayRegulonConvergenceTester",
    "PathwayRegulonObservation",
    "PathwayRegulonParser",
    "PathwayRegulonSetSummary",
    "RecurrenceBatch",
    "RecurrenceObservation",
    "RegionalBurdenBatch",
    "RegionalBurdenParser",
    "RegionalBurdenRegion",
    "RegionalBurdenResult",
    "RegionalBurdenTester",
    "RegulatoryRecurrenceParser",
    "RegulatoryRecurrenceResult",
    "RegulatoryRecurrenceTester",
    "SetDirection",
    "SetKind",
]
