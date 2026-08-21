"""Deep chromatin assay-control contracts for Domain 07.

The four adapters in this module are intentionally independent:

* atomic chromatin-state segmentation;
* allele-specific chromatin comparison;
* bounded one-dimensional epigenomic purity deconvolution; and
* explicit batch and cell-composition correction.

Raw assay values, correction parameters, source receipts, exact contexts, and
disagreement are retained. Corrected or deconvolved values are descriptive
research outputs; they are not causal effects, clinical purity calls, enhancer
truth labels, or substitutes for assay-specific validation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty


class ChromatinAlphaState(StrEnum):
    """Evidence state shared by chromatin-alpha adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class ChromatinAlphaIssue:
    """Addressable assay or correction issue with raw provenance."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinSegmentationObservation:
    """One context-qualified chromatin interval observation."""

    observation_id: str
    chromosome: str
    start: int
    end: int
    assay: str
    signal: float
    declared_state: str | None
    context_key: str
    sample_id: str
    replicate_id: str
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.observation_id, "observation_id"),
            (self.chromosome, "chromosome"),
            (self.assay, "assay"),
            (self.context_key, "context_key"),
            (self.sample_id, "sample_id"),
            (self.replicate_id, "replicate_id"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(str(value), field_name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("chromatin segmentation interval is invalid")
        if self.signal < 0:
            raise ValidationError("chromatin segmentation signal cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinStateSegment:
    """Atomic observed segment with support and disagreement metadata."""

    segment_id: str
    chromosome: str
    start: int
    end: int
    assay: str
    context_key: str
    state_label: str
    median_signal: float
    minimum_signal: float
    maximum_signal: float
    signal_spread: float
    support_count: int
    sample_ids: tuple[str, ...]
    replicate_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    state: ChromatinAlphaState
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinSegmentationReport:
    """Chromatin segmentation outputs and quarantined rows."""

    input_hash: str
    context_key: str | None
    state: ChromatinAlphaState
    observations: tuple[ChromatinSegmentationObservation, ...]
    segments: tuple[ChromatinStateSegment, ...]
    issues: tuple[ChromatinAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ChromatinStateSegmentationAdapter:
    """Split observed intervals and assign transparent chromatin state labels."""

    def segment(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        low_signal: float = 0.25,
        high_signal: float = 0.75,
    ) -> ChromatinSegmentationReport:
        values = tuple(records)
        input_hash = content_hash(values)
        observations: list[ChromatinSegmentationObservation] = []
        issues: list[ChromatinAlphaIssue] = []
        context_mismatch = False
        if low_signal < 0 or high_signal <= low_signal:
            issue = ChromatinAlphaIssue(
                "invalid_segmentation_threshold",
                "low_signal must be non-negative and lower than high_signal",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, ChromatinAlphaState.INVALID, (), (), (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ChromatinAlphaIssue(
                        "row_not_object",
                        "chromatin segmentation row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    ChromatinAlphaIssue(
                        "context_mismatch",
                        "chromatin segment is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                start, end = _interval(row)
                signal = float(_value(row, "signal", "score", "value"))
                if signal < 0:
                    raise ValidationError("chromatin segmentation signal cannot be negative")
                declared = _optional_text(row, "state", "state_label", "chromatin_state")
                observations.append(
                    ChromatinSegmentationObservation(
                        observation_id=str(
                            _value(row, "observation_id", "id", default=f"row-{row_number}")
                        ),
                        chromosome=normalize_chromosome(
                            str(_value(row, "chromosome", "chrom", "contig"))
                        ),
                        start=start,
                        end=end,
                        assay=str(_value(row, "assay", "track_kind", "kind", default="chromatin")),
                        signal=signal,
                        declared_state=declared,
                        context_key=row_context or context_key or "unspecified",
                        sample_id=str(_value(row, "sample_id", "sample", default="unspecified")),
                        replicate_id=str(
                            _value(row, "replicate_id", "replicate", default="unspecified")
                        ),
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ChromatinAlphaIssue(
                        "invalid_segmentation_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        groups: dict[tuple[str, str, str], list[ChromatinSegmentationObservation]] = defaultdict(
            list
        )
        for observation in observations:
            groups[(observation.chromosome, observation.assay, observation.context_key)].append(
                observation
            )
        segments: list[ChromatinStateSegment] = []
        for group in groups.values():
            segments.extend(self._split_group(group, low_signal, high_signal))
        if context_mismatch and not observations:
            state = ChromatinAlphaState.OUT_OF_DOMAIN
        elif any(item.state == ChromatinAlphaState.AMBIGUOUS for item in segments):
            state = ChromatinAlphaState.AMBIGUOUS
        elif issues or any(item.state == ChromatinAlphaState.PARTIAL for item in segments):
            state = ChromatinAlphaState.PARTIAL
        elif not segments:
            state = ChromatinAlphaState.ABSTAINED
        else:
            state = ChromatinAlphaState.SUPPORTED
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(observations),
            tuple(segments),
            tuple(issues),
        )

    @staticmethod
    def _split_group(
        group: Sequence[ChromatinSegmentationObservation],
        low_signal: float,
        high_signal: float,
    ) -> list[ChromatinStateSegment]:
        boundaries = sorted({point for item in group for point in (item.start, item.end + 1)})
        segments: list[ChromatinStateSegment] = []
        for start, end_exclusive in zip(boundaries, boundaries[1:], strict=False):
            active = tuple(
                item for item in group if item.start <= start and item.end >= end_exclusive - 1
            )
            if not active:
                continue
            signals = tuple(item.signal for item in active)
            declared = {item.declared_state for item in active if item.declared_state}
            inferred = {
                "closed"
                if signal <= low_signal
                else "open"
                if signal >= high_signal
                else "intermediate"
                for signal in signals
            }
            labels = declared or inferred
            label = next(iter(labels)) if len(labels) == 1 else "mixed"
            state = (
                ChromatinAlphaState.AMBIGUOUS
                if len(labels) > 1
                else ChromatinAlphaState.SUPPORTED
                if len({item.replicate_id for item in active}) >= 2
                else ChromatinAlphaState.PARTIAL
            )
            body = {
                "chromosome": active[0].chromosome,
                "assay": active[0].assay,
                "context_key": active[0].context_key,
                "start": start,
                "end": end_exclusive - 1,
                "observations": tuple(item.observation_id for item in active),
            }
            segments.append(
                ChromatinStateSegment(
                    segment_id="chromatin-segment:" + content_hash(body).split(":", 1)[1][:24],
                    chromosome=active[0].chromosome,
                    start=start,
                    end=end_exclusive - 1,
                    assay=active[0].assay,
                    context_key=active[0].context_key,
                    state_label=label,
                    median_signal=round(float(median(signals)), 9),
                    minimum_signal=round(min(signals), 9),
                    maximum_signal=round(max(signals), 9),
                    signal_spread=round(max(signals) - min(signals), 9),
                    support_count=len(active),
                    sample_ids=tuple(sorted({item.sample_id for item in active})),
                    replicate_ids=tuple(sorted({item.replicate_id for item in active})),
                    observation_ids=tuple(sorted(item.observation_id for item in active)),
                    source_ids=tuple(sorted({item.source_id for item in active})),
                    state=state,
                    raw_hashes=tuple(sorted(item.raw_hash for item in active)),
                    content_address=content_hash(body | {"state": state, "label": label}),
                )
            )
        return segments

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: ChromatinAlphaState,
        observations: tuple[ChromatinSegmentationObservation, ...],
        segments: tuple[ChromatinStateSegment, ...],
        issues: tuple[ChromatinAlphaIssue, ...],
    ) -> ChromatinSegmentationReport:
        return ChromatinSegmentationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=observations,
            segments=segments,
            issues=issues,
            warnings=(
                "Chromatin state labels are observation summaries, not activity or causal claims.",
                "Atomic segments are emitted only across observed interval boundaries.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "segments": segments,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class AlleleSpecificChromatinObservation:
    """One reference/alternate chromatin measurement."""

    observation_id: str
    variant_id: str
    assay: str
    context_key: str
    reference_signal: float | None
    alternate_signal: float | None
    replicate_id: str
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.observation_id, "observation_id"),
            (self.variant_id, "variant_id"),
            (self.assay, "assay"),
            (self.context_key, "context_key"),
            (self.replicate_id, "replicate_id"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(str(value), name)
        for signal_name in ("reference_signal", "alternate_signal"):
            signal = getattr(self, signal_name)
            if signal is not None and signal < 0:
                raise ValidationError(f"{signal_name} cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleSpecificChromatinResult:
    """Replicate-aware allele-specific chromatin delta."""

    variant_id: str
    assay: str
    context_key: str
    state: ChromatinAlphaState
    median_delta: float | None
    minimum_delta: float | None
    maximum_delta: float | None
    delta_spread: float | None
    direction: str
    replicate_count: int
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleSpecificChromatinReport:
    """Allele-specific chromatin results and input issues."""

    input_hash: str
    context_key: str | None
    state: ChromatinAlphaState
    observations: tuple[AlleleSpecificChromatinObservation, ...]
    results: tuple[AlleleSpecificChromatinResult, ...]
    issues: tuple[ChromatinAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AlleleSpecificChromatinAnalyzer:
    """Compare allele-specific signals while retaining missingness and spread."""

    def analyze(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        ambiguity_tolerance: float = 0.25,
        delta_threshold: float = 0.0,
    ) -> AlleleSpecificChromatinReport:
        values = tuple(records)
        input_hash = content_hash(values)
        observations: list[AlleleSpecificChromatinObservation] = []
        issues: list[ChromatinAlphaIssue] = []
        context_mismatch = False
        if ambiguity_tolerance < 0 or delta_threshold < 0:
            issue = ChromatinAlphaIssue(
                "invalid_allele_specific_parameter",
                "ambiguity tolerance and delta threshold must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, ChromatinAlphaState.INVALID, (), (), (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ChromatinAlphaIssue(
                        "row_not_object",
                        "allele-specific chromatin row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    ChromatinAlphaIssue(
                        "context_mismatch",
                        "allele-specific chromatin row is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                observations.append(
                    AlleleSpecificChromatinObservation(
                        observation_id=str(
                            _value(row, "observation_id", "id", default=f"row-{row_number}")
                        ),
                        variant_id=str(_value(row, "variant_id", "variant", "id")),
                        assay=str(_value(row, "assay", "track_kind", default="chromatin")),
                        context_key=row_context or context_key or "unspecified",
                        reference_signal=_optional_float(
                            _value(row, "reference_signal", "reference", "ref", default=None)
                        ),
                        alternate_signal=_optional_float(
                            _value(row, "alternate_signal", "alternate", "alt", default=None)
                        ),
                        replicate_id=str(
                            _value(row, "replicate_id", "replicate", default="unspecified")
                        ),
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ChromatinAlphaIssue(
                        "invalid_allele_specific_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        groups: dict[tuple[str, str, str], list[AlleleSpecificChromatinObservation]] = defaultdict(
            list
        )
        for observation in observations:
            groups[(observation.variant_id, observation.assay, observation.context_key)].append(
                observation
            )
        results: list[AlleleSpecificChromatinResult] = []
        for key, group in sorted(groups.items()):
            deltas = [
                item.alternate_signal - item.reference_signal
                for item in group
                if item.reference_signal is not None and item.alternate_signal is not None
            ]
            if not deltas:
                state = ChromatinAlphaState.PARTIAL
                direction = "unknown"
                median_delta = minimum_delta = maximum_delta = delta_spread = None
            else:
                median_delta = round(float(median(deltas)), 9)
                minimum_delta = round(min(deltas), 9)
                maximum_delta = round(max(deltas), 9)
                delta_spread = round(max(deltas) - min(deltas), 9)
                positive = any(delta > delta_threshold for delta in deltas)
                negative = any(delta < -delta_threshold for delta in deltas)
                direction = (
                    "increased"
                    if positive and not negative
                    else "decreased"
                    if negative and not positive
                    else "mixed"
                    if positive or negative
                    else "unchanged"
                )
                state = (
                    ChromatinAlphaState.AMBIGUOUS
                    if positive and negative or delta_spread > ambiguity_tolerance
                    else ChromatinAlphaState.PARTIAL
                    if len(deltas) < len(group)
                    else ChromatinAlphaState.SUPPORTED
                )
            body = {"variant_id": key[0], "assay": key[1], "context_key": key[2], "deltas": deltas}
            results.append(
                AlleleSpecificChromatinResult(
                    variant_id=key[0],
                    assay=key[1],
                    context_key=key[2],
                    state=state,
                    median_delta=median_delta,
                    minimum_delta=minimum_delta,
                    maximum_delta=maximum_delta,
                    delta_spread=delta_spread,
                    direction=direction,
                    replicate_count=len(group),
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    raw_hashes=tuple(sorted(item.raw_hash for item in group)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        if context_mismatch and not observations:
            state = ChromatinAlphaState.OUT_OF_DOMAIN
        elif any(item.state == ChromatinAlphaState.AMBIGUOUS for item in results):
            state = ChromatinAlphaState.AMBIGUOUS
        elif issues or any(item.state == ChromatinAlphaState.PARTIAL for item in results):
            state = ChromatinAlphaState.PARTIAL
        elif not results:
            state = ChromatinAlphaState.ABSTAINED
        else:
            state = ChromatinAlphaState.SUPPORTED
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(observations),
            tuple(results),
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: ChromatinAlphaState,
        observations: tuple[AlleleSpecificChromatinObservation, ...],
        results: tuple[AlleleSpecificChromatinResult, ...],
        issues: tuple[ChromatinAlphaIssue, ...],
    ) -> AlleleSpecificChromatinReport:
        return AlleleSpecificChromatinReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=observations,
            results=results,
            issues=issues,
            warnings=(
                "Allele-specific chromatin deltas are assay comparisons, not causal effects.",
                "Mixed replicate directions remain ambiguous rather than averaged into certainty.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "results": results,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class PurityMarkerObservation:
    """One observed signal and two declared pure-state references."""

    marker_id: str
    assay: str
    context_key: str
    observed_signal: float
    tumor_signal: float
    normal_signal: float
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.marker_id, "marker_id"),
            (self.assay, "assay"),
            (self.context_key, "context_key"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(str(value), name)
        for name in ("observed_signal", "tumor_signal", "normal_signal"):
            if getattr(self, name) < 0:
                raise ValidationError(f"{name} cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PurityMarkerEstimate:
    """One bounded marker-level purity estimate."""

    marker_id: str
    assay: str
    context_key: str
    raw_purity: float | None
    bounded_purity: float | None
    denominator: float
    state: ChromatinAlphaState
    source_id: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EpigenomicPurityReport:
    """Marker-level and aggregate epigenomic purity estimates."""

    input_hash: str
    context_key: str | None
    state: ChromatinAlphaState
    marker_observations: tuple[PurityMarkerObservation, ...]
    estimates: tuple[PurityMarkerEstimate, ...]
    aggregate_purity: float | None
    purity_spread: float | None
    issues: tuple[ChromatinAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EpigenomicPurityDeconvolver:
    """Estimate a mixture proportion from declared tumor/normal references."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        minimum_markers: int = 2,
        spread_tolerance: float = 0.2,
    ) -> EpigenomicPurityReport:
        values = tuple(records)
        input_hash = content_hash(values)
        observations: list[PurityMarkerObservation] = []
        estimates: list[PurityMarkerEstimate] = []
        issues: list[ChromatinAlphaIssue] = []
        context_mismatch = False
        if minimum_markers < 1 or spread_tolerance < 0:
            issue = ChromatinAlphaIssue(
                "invalid_purity_parameter",
                "minimum markers must be positive and spread tolerance non-negative",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, ChromatinAlphaState.INVALID, (), (), None, None, (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ChromatinAlphaIssue(
                        "row_not_object",
                        "purity marker row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    ChromatinAlphaIssue(
                        "context_mismatch",
                        "purity marker is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                observation = PurityMarkerObservation(
                    marker_id=str(_value(row, "marker_id", "id", "feature_id")),
                    assay=str(_value(row, "assay", "track_kind", default="epigenomic")),
                    context_key=row_context or context_key or "unspecified",
                    observed_signal=float(_value(row, "observed_signal", "observed", "signal")),
                    tumor_signal=float(_value(row, "tumor_signal", "tumor")),
                    normal_signal=float(_value(row, "normal_signal", "normal")),
                    source_id=_source_id(row),
                    source_version=_source_version(row),
                    raw_hash=raw_hash,
                )
                observations.append(observation)
                denominator = observation.tumor_signal - observation.normal_signal
                if denominator == 0:
                    raw_purity = None
                    bounded = None
                    estimate_state = ChromatinAlphaState.ABSTAINED
                else:
                    raw_purity = (
                        observation.observed_signal - observation.normal_signal
                    ) / denominator
                    bounded = min(1.0, max(0.0, raw_purity))
                    estimate_state = (
                        ChromatinAlphaState.PARTIAL
                        if raw_purity < 0 or raw_purity > 1
                        else ChromatinAlphaState.SUPPORTED
                    )
                body = {
                    "marker_id": observation.marker_id,
                    "assay": observation.assay,
                    "context_key": observation.context_key,
                    "raw_purity": raw_purity,
                    "denominator": denominator,
                }
                estimates.append(
                    PurityMarkerEstimate(
                        marker_id=observation.marker_id,
                        assay=observation.assay,
                        context_key=observation.context_key,
                        raw_purity=None if raw_purity is None else round(raw_purity, 9),
                        bounded_purity=None if bounded is None else round(bounded, 9),
                        denominator=round(denominator, 9),
                        state=estimate_state,
                        source_id=observation.source_id,
                        raw_hash=raw_hash,
                        content_address=content_hash(body | {"state": estimate_state}),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ChromatinAlphaIssue(
                        "invalid_purity_marker",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        bounded = [item.bounded_purity for item in estimates if item.bounded_purity is not None]
        aggregate = round(float(median(bounded)), 9) if bounded else None
        spread = (
            round(max(bounded) - min(bounded), 9) if len(bounded) > 1 else 0.0 if bounded else None
        )
        if context_mismatch and not observations:
            state = ChromatinAlphaState.OUT_OF_DOMAIN
        elif not bounded:
            state = (
                ChromatinAlphaState.PARTIAL
                if observations or issues
                else ChromatinAlphaState.ABSTAINED
            )
        elif len(bounded) < minimum_markers or len(bounded) < len(observations):
            state = ChromatinAlphaState.PARTIAL
        elif spread is not None and spread > spread_tolerance:
            state = ChromatinAlphaState.AMBIGUOUS
        elif issues or any(item.state == ChromatinAlphaState.PARTIAL for item in estimates):
            state = ChromatinAlphaState.PARTIAL
        else:
            state = ChromatinAlphaState.SUPPORTED
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(observations),
            tuple(estimates),
            aggregate,
            spread,
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: ChromatinAlphaState,
        observations: tuple[PurityMarkerObservation, ...],
        estimates: tuple[PurityMarkerEstimate, ...],
        aggregate: float | None,
        spread: float | None,
        issues: tuple[ChromatinAlphaIssue, ...],
    ) -> EpigenomicPurityReport:
        return EpigenomicPurityReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            marker_observations=observations,
            estimates=estimates,
            aggregate_purity=aggregate,
            purity_spread=spread,
            issues=issues,
            warnings=(
                (
                    "Purity is a bounded mixture estimate from declared assay references, "
                    "not a clinical purity call."
                ),
                (
                    "Out-of-range marker estimates are clipped only for aggregate reporting "
                    "and remain visible."
                ),
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "estimates": estimates,
                    "aggregate": aggregate,
                    "spread": spread,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class BatchCompositionObservation:
    """One raw signal with explicit batch and composition covariates."""

    feature_id: str
    assay: str
    context_key: str
    batch_id: str
    raw_signal: float
    cell_composition: Mapping[str, float]
    composition_coefficients: Mapping[str, float]
    batch_offset: float | None
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.feature_id, "feature_id"),
            (self.assay, "assay"),
            (self.context_key, "context_key"),
            (self.batch_id, "batch_id"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(str(value), name)
        if self.raw_signal < 0:
            raise ValidationError("raw signal cannot be negative")
        if any(value < 0 for value in self.cell_composition.values()):
            raise ValidationError("cell composition proportions cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BatchCompositionCorrection:
    """Raw signal and transparent batch/composition correction terms."""

    feature_id: str
    assay: str
    context_key: str
    batch_id: str
    raw_signal: float
    batch_adjustment: float
    composition_adjustment: float
    corrected_signal: float
    target_composition: Mapping[str, float]
    state: ChromatinAlphaState
    source_id: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BatchCompositionCorrectionReport:
    """Correction outputs and covariate issues."""

    input_hash: str
    context_key: str | None
    state: ChromatinAlphaState
    observations: tuple[BatchCompositionObservation, ...]
    corrections: tuple[BatchCompositionCorrection, ...]
    issues: tuple[ChromatinAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BatchCellCompositionCorrector:
    """Apply declared batch offsets and composition coefficients transparently."""

    def correct(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        batch_offsets: Mapping[str, float] | None = None,
        target_composition: Mapping[str, float] | None = None,
    ) -> BatchCompositionCorrectionReport:
        values = tuple(records)
        input_hash = content_hash(values)
        offsets = {str(key): float(value) for key, value in (batch_offsets or {}).items()}
        target = {str(key): float(value) for key, value in (target_composition or {}).items()}
        observations: list[BatchCompositionObservation] = []
        corrections: list[BatchCompositionCorrection] = []
        issues: list[ChromatinAlphaIssue] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    ChromatinAlphaIssue(
                        "row_not_object",
                        "batch/composition row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    ChromatinAlphaIssue(
                        "context_mismatch",
                        "batch/composition row is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                raw_composition = row.get("cell_composition", row.get("composition", {}))
                raw_coefficients = row.get("composition_coefficients", row.get("coefficients", {}))
                if not isinstance(raw_composition, Mapping) or not isinstance(
                    raw_coefficients, Mapping
                ):
                    raise ValidationError("cell composition and coefficients must be objects")
                composition = {str(key): float(value) for key, value in raw_composition.items()}
                coefficients = {str(key): float(value) for key, value in raw_coefficients.items()}
                batch_id = str(_value(row, "batch_id", "batch"))
                row_offset = _optional_float(_value(row, "batch_offset", default=None))
                offset = offsets.get(batch_id, row_offset)
                row_target = row.get("target_composition", target)
                if not isinstance(row_target, Mapping):
                    raise ValidationError("target composition must be an object")
                chosen_target = {str(key): float(value) for key, value in row_target.items()}
                observation = BatchCompositionObservation(
                    feature_id=str(_value(row, "feature_id", "id", "element_id")),
                    assay=str(_value(row, "assay", "track_kind", default="chromatin")),
                    context_key=row_context or context_key or "unspecified",
                    batch_id=batch_id,
                    raw_signal=float(_value(row, "raw_signal", "signal", "value")),
                    cell_composition=composition,
                    composition_coefficients=coefficients,
                    batch_offset=offset,
                    source_id=_source_id(row),
                    source_version=_source_version(row),
                    raw_hash=raw_hash,
                )
                observations.append(observation)
                if offset is None:
                    batch_adjustment = 0.0
                    correction_state = ChromatinAlphaState.PARTIAL
                else:
                    batch_adjustment = offset
                    correction_state = ChromatinAlphaState.SUPPORTED
                composition_adjustment = sum(
                    coefficients.get(cell, 0.0)
                    * (composition.get(cell, 0.0) - chosen_target.get(cell, 0.0))
                    for cell in set(composition) | set(coefficients) | set(chosen_target)
                )
                if not coefficients and composition:
                    correction_state = ChromatinAlphaState.PARTIAL
                corrected = observation.raw_signal - batch_adjustment - composition_adjustment
                body = {
                    "feature_id": observation.feature_id,
                    "batch_id": observation.batch_id,
                    "raw_signal": observation.raw_signal,
                    "batch_adjustment": batch_adjustment,
                    "composition_adjustment": composition_adjustment,
                    "target": chosen_target,
                }
                corrections.append(
                    BatchCompositionCorrection(
                        feature_id=observation.feature_id,
                        assay=observation.assay,
                        context_key=observation.context_key,
                        batch_id=observation.batch_id,
                        raw_signal=round(observation.raw_signal, 9),
                        batch_adjustment=round(batch_adjustment, 9),
                        composition_adjustment=round(composition_adjustment, 9),
                        corrected_signal=round(corrected, 9),
                        target_composition=chosen_target,
                        state=correction_state,
                        source_id=observation.source_id,
                        raw_hash=raw_hash,
                        content_address=content_hash(body | {"state": correction_state}),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ChromatinAlphaIssue(
                        "invalid_batch_composition_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        if context_mismatch and not observations:
            state = ChromatinAlphaState.OUT_OF_DOMAIN
        elif issues or any(item.state == ChromatinAlphaState.PARTIAL for item in corrections):
            state = ChromatinAlphaState.PARTIAL
        elif not corrections:
            state = ChromatinAlphaState.ABSTAINED
        else:
            state = ChromatinAlphaState.SUPPORTED
        return BatchCompositionCorrectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=tuple(observations),
            corrections=tuple(corrections),
            issues=tuple(issues),
            warnings=(
                (
                    "Correction requires declared batch offsets and composition coefficients; "
                    "missing terms remain partial."
                ),
                (
                    "Corrected values are assay-normalization outputs, not biological effects "
                    "or causal estimates."
                ),
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "corrections": corrections,
                    "issues": issues,
                }
            ),
        )


def _interval(row: Mapping[str, Any]) -> tuple[int, int]:
    start = int(_value(row, "start", "position", "pos"))
    end = int(_value(row, "end", default=start))
    if start < 1 or end < start:
        raise ValidationError("interval must satisfy 1 <= start <= end")
    return start, end


_MISSING = object()


def _value(row: Mapping[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is not None and value != "":
            return value
    if default is not _MISSING:
        return default
    raise ValidationError(f"missing required field; expected one of {keys}")


def _optional_text(row: Mapping[str, Any], *keys: str) -> str | None:
    value = _value(row, *keys, default=None)
    return None if value is None or str(value) in {"", "."} else str(value)


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return float(value)


def _context(row: Mapping[str, Any]) -> str | None:
    value = row.get("context_key", row.get("context"))
    return str(value) if value not in {None, "", "."} else None


def _source_id(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id", row.get("source", "unspecified"))) or "unspecified"


def _source_version(row: Mapping[str, Any]) -> str:
    return str(row.get("source_version", row.get("version", "unspecified"))) or "unspecified"


def _raw_hash(row: Mapping[str, Any]) -> str:
    return content_hash(dict(row))


__all__ = [
    "AlleleSpecificChromatinAnalyzer",
    "AlleleSpecificChromatinObservation",
    "AlleleSpecificChromatinReport",
    "AlleleSpecificChromatinResult",
    "BatchCellCompositionCorrector",
    "BatchCompositionCorrection",
    "BatchCompositionCorrectionReport",
    "BatchCompositionObservation",
    "ChromatinAlphaIssue",
    "ChromatinAlphaState",
    "ChromatinSegmentationObservation",
    "ChromatinSegmentationReport",
    "ChromatinStateSegment",
    "ChromatinStateSegmentationAdapter",
    "EpigenomicPurityDeconvolver",
    "EpigenomicPurityReport",
    "PurityMarkerEstimate",
    "PurityMarkerObservation",
]
