"""Deep regulatory-atlas harmonization and role contracts.

This module extends the Domain 05 atlas boundary with four independent
operations:

* open-chromatin track harmonization across replicates and callers;
* methylation interval harmonization with coverage-aware summaries;
* enhancer/promoter/silencer role classification from declared channels; and
* super-enhancer candidate grouping from ranked constituent intervals.

The outputs are descriptive, source-accounted research objects. They preserve
assay disagreement, exact context, missing channels, and candidate ranking.
They do not turn accessibility into activity, methylation into silencing, or a
super-enhancer candidate into a causal or clinical claim.
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


class AtlasAlphaState(StrEnum):
    """Evidence state shared by the Domain 05 atlas alpha adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class AtlasAlphaIssue:
    """A row-addressable assay or context issue."""

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
class OpenChromatinObservation:
    """One ATAC/DNase/open-chromatin interval observation."""

    observation_id: str
    chromosome: str
    start: int
    end: int
    track_kind: str
    signal: float
    replicate_id: str
    caller_id: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    peak_p_value: float | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.observation_id, "observation_id"),
            (self.chromosome, "chromosome"),
            (self.track_kind, "track_kind"),
            (self.replicate_id, "replicate_id"),
            (self.caller_id, "caller_id"),
            (self.context_key, "context_key"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(value, field_name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("open-chromatin interval is invalid")
        if self.signal < 0:
            raise ValidationError("open-chromatin signal cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OpenChromatinInterval:
    """Atomic open-chromatin interval with replicate spread."""

    interval_id: str
    chromosome: str
    start: int
    end: int
    track_kind: str
    context_key: str
    median_signal: float
    minimum_signal: float
    maximum_signal: float
    signal_spread: float
    replicate_ids: tuple[str, ...]
    caller_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    state: AtlasAlphaState
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OpenChromatinHarmonizationReport:
    """Open-chromatin observations, harmonized intervals, and issues."""

    input_hash: str
    context_key: str | None
    state: AtlasAlphaState
    observations: tuple[OpenChromatinObservation, ...]
    intervals: tuple[OpenChromatinInterval, ...]
    issues: tuple[AtlasAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class OpenChromatinTrackHarmonizer:
    """Split observed open-chromatin peaks and summarize replicate spread."""

    def harmonize(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        spread_tolerance: float = 0.25,
        minimum_signal: float = 0.0,
    ) -> OpenChromatinHarmonizationReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[AtlasAlphaIssue] = []
        observations: list[OpenChromatinObservation] = []
        context_mismatch = False
        if spread_tolerance < 0 or minimum_signal < 0:
            issue = AtlasAlphaIssue(
                "invalid_open_chromatin_parameter",
                "spread tolerance and minimum signal must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, AtlasAlphaState.INVALID, (), (), (issue,))
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    AtlasAlphaIssue(
                        "row_not_object",
                        "open-chromatin row must be an object",
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
                    AtlasAlphaIssue(
                        "context_mismatch",
                        "open-chromatin row is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                start, end = _interval(row)
                observation = OpenChromatinObservation(
                    observation_id=str(
                        _value(row, "observation_id", "id", "name", default=f"row-{row_number}")
                    ),
                    chromosome=normalize_chromosome(
                        str(_value(row, "chromosome", "chrom", "contig"))
                    ),
                    start=start,
                    end=end,
                    track_kind=str(
                        _value(row, "track_kind", "assay", "kind", default="open_chromatin")
                    ),
                    signal=float(_value(row, "signal", "score", "value")),
                    replicate_id=str(
                        _value(row, "replicate_id", "replicate", default="unspecified")
                    ),
                    caller_id=str(_value(row, "caller_id", "caller", default="unspecified")),
                    context_key=row_context or context_key or "unspecified",
                    source_id=_source_id(row),
                    source_version=_source_version(row),
                    raw_hash=raw_hash,
                    peak_p_value=_optional_float(
                        _value(row, "peak_p_value", "p_value", default=None)
                    ),
                    attributes=dict(row),
                )
                if observation.signal < minimum_signal:
                    continue
                observations.append(observation)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    AtlasAlphaIssue(
                        "invalid_open_chromatin_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        intervals: list[OpenChromatinInterval] = []
        groups: dict[tuple[str, str, str, str], list[OpenChromatinObservation]] = defaultdict(list)
        for observation in observations:
            groups[
                (
                    observation.chromosome,
                    observation.track_kind,
                    observation.context_key,
                    observation.caller_id,
                )
            ].append(observation)
        for _group_key, group in sorted(groups.items()):
            intervals.extend(self._split_group(group, spread_tolerance))
        if context_mismatch and not observations:
            state = AtlasAlphaState.OUT_OF_DOMAIN
        elif any(item.state == AtlasAlphaState.AMBIGUOUS for item in intervals):
            state = AtlasAlphaState.AMBIGUOUS
        elif issues or any(item.state == AtlasAlphaState.PARTIAL for item in intervals):
            state = AtlasAlphaState.PARTIAL
        elif not intervals:
            state = AtlasAlphaState.ABSTAINED
        elif context_mismatch:
            state = AtlasAlphaState.PARTIAL
        else:
            state = AtlasAlphaState.SUPPORTED
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(observations),
            tuple(intervals),
            tuple(issues),
        )

    @staticmethod
    def _split_group(
        group: Sequence[OpenChromatinObservation], spread_tolerance: float
    ) -> list[OpenChromatinInterval]:
        boundaries = sorted({boundary for item in group for boundary in (item.start, item.end + 1)})
        intervals: list[OpenChromatinInterval] = []
        for start, right_exclusive in zip(boundaries, boundaries[1:], strict=False):
            active = tuple(
                item for item in group if item.start <= start and item.end >= right_exclusive - 1
            )
            if not active:
                continue
            signals = tuple(item.signal for item in active)
            spread = max(signals) - min(signals)
            state = (
                AtlasAlphaState.SUPPORTED
                if len({item.replicate_id for item in active}) >= 2 and spread <= spread_tolerance
                else AtlasAlphaState.AMBIGUOUS
                if spread > spread_tolerance
                else AtlasAlphaState.PARTIAL
            )
            body = {
                "chromosome": group[0].chromosome,
                "track_kind": group[0].track_kind,
                "context_key": group[0].context_key,
                "start": start,
                "end": right_exclusive - 1,
                "observations": tuple(item.observation_id for item in active),
            }
            intervals.append(
                OpenChromatinInterval(
                    interval_id="open:" + content_hash(body).split(":", 1)[1][:24],
                    chromosome=group[0].chromosome,
                    start=start,
                    end=right_exclusive - 1,
                    track_kind=group[0].track_kind,
                    context_key=group[0].context_key,
                    median_signal=round(float(median(signals)), 6),
                    minimum_signal=round(min(signals), 6),
                    maximum_signal=round(max(signals), 6),
                    signal_spread=round(spread, 6),
                    replicate_ids=tuple(sorted({item.replicate_id for item in active})),
                    caller_ids=tuple(sorted({item.caller_id for item in active})),
                    observation_ids=tuple(sorted(item.observation_id for item in active)),
                    source_ids=tuple(sorted({item.source_id for item in active})),
                    state=state,
                    raw_hashes=tuple(sorted(item.raw_hash for item in active)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        return intervals

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: AtlasAlphaState,
        observations: tuple[OpenChromatinObservation, ...],
        intervals: tuple[OpenChromatinInterval, ...],
        issues: tuple[AtlasAlphaIssue, ...],
    ) -> OpenChromatinHarmonizationReport:
        return OpenChromatinHarmonizationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=observations,
            intervals=intervals,
            issues=issues,
            warnings=(
                "Open chromatin is an accessibility observation, not an activity or causal call.",
                "Unobserved bases are not imputed between track intervals.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "intervals": intervals,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class MethylationObservation:
    """One CpG or methylation interval observation."""

    observation_id: str
    chromosome: str
    start: int
    end: int
    methylation_fraction: float | None
    methylated_count: int | None
    total_count: int | None
    replicate_id: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        require_non_empty(self.observation_id, "observation_id")
        require_non_empty(self.chromosome, "chromosome")
        require_non_empty(self.replicate_id, "replicate_id")
        require_non_empty(self.context_key, "context_key")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("methylation interval is invalid")
        if self.methylation_fraction is not None and not 0 <= self.methylation_fraction <= 1:
            raise ValidationError("methylation fraction must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationInterval:
    """Coverage-aware methylation interval summary."""

    interval_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    median_fraction: float | None
    minimum_fraction: float | None
    maximum_fraction: float | None
    fraction_spread: float | None
    total_methylated_count: int
    total_count: int
    replicate_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    state: AtlasAlphaState
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationHarmonizationReport:
    """Methylation observations, coverage summaries, and issues."""

    input_hash: str
    context_key: str | None
    state: AtlasAlphaState
    observations: tuple[MethylationObservation, ...]
    intervals: tuple[MethylationInterval, ...]
    issues: tuple[AtlasAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MethylationTrackHarmonizer:
    """Harmonize methylation fractions while preserving coverage limits."""

    def harmonize(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        spread_tolerance: float = 0.25,
    ) -> MethylationHarmonizationReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[AtlasAlphaIssue] = []
        observations: list[MethylationObservation] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    AtlasAlphaIssue(
                        "row_not_object",
                        "methylation row must be an object",
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
                    AtlasAlphaIssue(
                        "context_mismatch",
                        "methylation row is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                start, end = _interval(row)
                methylated = _optional_int(
                    _value(row, "methylated_count", "methylated", "M", default=None)
                )
                total = _optional_int(_value(row, "total_count", "coverage", "N", default=None))
                fraction = _optional_float(
                    _value(row, "methylation_fraction", "fraction", "beta", default=None)
                )
                if fraction is None and methylated is not None and total is not None:
                    if total <= 0:
                        raise ValidationError("methylation total count must be positive")
                    fraction = methylated / total
                if fraction is not None and not 0 <= fraction <= 1:
                    raise ValidationError("methylation fraction must be between zero and one")
                if methylated is None:
                    methylated = round(fraction * total) if fraction is not None and total else 0
                if total is None:
                    total = 0
                if methylated > total and total > 0:
                    raise ValidationError("methylated count cannot exceed total count")
                observations.append(
                    MethylationObservation(
                        observation_id=str(
                            _value(row, "observation_id", "id", default=f"row-{row_number}")
                        ),
                        chromosome=normalize_chromosome(
                            str(_value(row, "chromosome", "chrom", "contig"))
                        ),
                        start=start,
                        end=end,
                        methylation_fraction=round(fraction, 12) if fraction is not None else None,
                        methylated_count=methylated,
                        total_count=total,
                        replicate_id=str(
                            _value(row, "replicate_id", "replicate", default="unspecified")
                        ),
                        context_key=row_context or context_key or "unspecified",
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    AtlasAlphaIssue(
                        "invalid_methylation_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        groups: dict[tuple[str, str], list[MethylationObservation]] = defaultdict(list)
        for observation in observations:
            groups[(observation.chromosome, observation.context_key)].append(observation)
        intervals: list[MethylationInterval] = []
        for group in groups.values():
            intervals.extend(self._split_group(group, spread_tolerance))
        if context_mismatch and not observations:
            state = AtlasAlphaState.OUT_OF_DOMAIN
        elif any(item.state == AtlasAlphaState.AMBIGUOUS for item in intervals):
            state = AtlasAlphaState.AMBIGUOUS
        elif issues or any(item.state == AtlasAlphaState.PARTIAL for item in intervals):
            state = AtlasAlphaState.PARTIAL
        elif not intervals:
            state = AtlasAlphaState.ABSTAINED
        else:
            state = AtlasAlphaState.SUPPORTED
        return MethylationHarmonizationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=tuple(observations),
            intervals=tuple(intervals),
            issues=tuple(issues),
            warnings=(
                (
                    "Methylation fraction is an assay observation; silencing is not inferred "
                    "without role evidence."
                ),
                "Coverage and replicate disagreement remain attached to every interval.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "intervals": intervals,
                    "issues": issues,
                }
            ),
        )

    @staticmethod
    def _split_group(
        group: Sequence[MethylationObservation], spread_tolerance: float
    ) -> list[MethylationInterval]:
        boundaries = sorted({boundary for item in group for boundary in (item.start, item.end + 1)})
        intervals: list[MethylationInterval] = []
        for start, right_exclusive in zip(boundaries, boundaries[1:], strict=False):
            active = tuple(
                item for item in group if item.start <= start and item.end >= right_exclusive - 1
            )
            if not active:
                continue
            fractions = [
                item.methylation_fraction
                for item in active
                if item.methylation_fraction is not None
            ]
            spread = max(fractions) - min(fractions) if fractions else None
            state = (
                AtlasAlphaState.PARTIAL
                if not fractions or sum(item.total_count or 0 for item in active) == 0
                else AtlasAlphaState.AMBIGUOUS
                if spread is not None and spread > spread_tolerance
                else AtlasAlphaState.SUPPORTED
            )
            body = {
                "chromosome": active[0].chromosome,
                "context_key": active[0].context_key,
                "start": start,
                "end": right_exclusive - 1,
                "observations": tuple(item.observation_id for item in active),
            }
            intervals.append(
                MethylationInterval(
                    interval_id="methylation:" + content_hash(body).split(":", 1)[1][:24],
                    chromosome=active[0].chromosome,
                    start=start,
                    end=right_exclusive - 1,
                    context_key=active[0].context_key,
                    median_fraction=round(float(median(fractions)), 12) if fractions else None,
                    minimum_fraction=round(min(fractions), 12) if fractions else None,
                    maximum_fraction=round(max(fractions), 12) if fractions else None,
                    fraction_spread=round(spread, 12) if spread is not None else None,
                    total_methylated_count=sum(item.methylated_count or 0 for item in active),
                    total_count=sum(item.total_count or 0 for item in active),
                    replicate_ids=tuple(sorted({item.replicate_id for item in active})),
                    observation_ids=tuple(sorted(item.observation_id for item in active)),
                    state=state,
                    raw_hashes=tuple(sorted(item.raw_hash for item in active)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        return intervals


@dataclass(frozen=True, slots=True)
class RegulatoryRoleObservation:
    """Declared activity channels for one regulatory element."""

    element_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    promoter_score: float | None
    enhancer_score: float | None
    silencer_score: float | None
    open_chromatin_signal: float | None
    methylation_fraction: float | None
    contact_support: float | None
    target_gene_ids: tuple[str, ...]
    source_id: str
    source_version: str
    raw_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryRoleClassification:
    """Role labels with channel evidence and missingness."""

    element_id: str
    context_key: str
    roles: tuple[str, ...]
    state: AtlasAlphaState
    evidence_channels: tuple[str, ...]
    missing_channels: tuple[str, ...]
    target_gene_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryRoleClassificationReport:
    """Role classifications and source issues."""

    input_hash: str
    context_key: str | None
    state: AtlasAlphaState
    observations: tuple[RegulatoryRoleObservation, ...]
    classifications: tuple[RegulatoryRoleClassification, ...]
    issues: tuple[AtlasAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EnhancerPromoterSilencerClassifier:
    """Classify roles from declared scores and preserve multi-role ambiguity."""

    def classify(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        role_threshold: float = 0.5,
        methylation_silencer_threshold: float = 0.8,
    ) -> RegulatoryRoleClassificationReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[AtlasAlphaIssue] = []
        observations: list[RegulatoryRoleObservation] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    AtlasAlphaIssue(
                        "row_not_object",
                        "regulatory role row must be an object",
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
                    AtlasAlphaIssue(
                        "context_mismatch",
                        "regulatory role row is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                start, end = _interval(row)
                observations.append(
                    RegulatoryRoleObservation(
                        element_id=str(_value(row, "element_id", "id", "name")),
                        chromosome=normalize_chromosome(
                            str(_value(row, "chromosome", "chrom", "contig"))
                        ),
                        start=start,
                        end=end,
                        context_key=row_context or context_key or "unspecified",
                        promoter_score=_optional_score(
                            _value(row, "promoter_score", "promoter", default=None)
                        ),
                        enhancer_score=_optional_score(
                            _value(row, "enhancer_score", "enhancer", default=None)
                        ),
                        silencer_score=_optional_score(
                            _value(row, "silencer_score", "silencer", default=None)
                        ),
                        open_chromatin_signal=_optional_float(
                            _value(
                                row,
                                "open_chromatin_signal",
                                "accessibility",
                                "open_signal",
                                default=None,
                            )
                        ),
                        methylation_fraction=_optional_score(
                            _value(row, "methylation_fraction", "methylation", "beta", default=None)
                        ),
                        contact_support=_optional_score(
                            _value(row, "contact_support", "contact", default=None)
                        ),
                        target_gene_ids=_text_tuple(
                            _value(row, "target_gene_ids", "targets", "genes", default=())
                        ),
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    AtlasAlphaIssue(
                        "invalid_regulatory_role_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        classifications: list[RegulatoryRoleClassification] = []
        for observation in observations:
            roles: list[str] = []
            evidence: list[str] = []
            missing: list[str] = []
            if (
                observation.promoter_score is not None
                and observation.promoter_score >= role_threshold
            ):
                roles.append("promoter")
                evidence.append("promoter_score")
            elif observation.promoter_score is None:
                missing.append("promoter_score")
            if (
                observation.enhancer_score is not None
                and observation.enhancer_score >= role_threshold
            ):
                roles.append("enhancer")
                evidence.append("enhancer_score")
            elif observation.enhancer_score is None:
                missing.append("enhancer_score")
            if (
                observation.silencer_score is not None
                and observation.silencer_score >= role_threshold
            ):
                roles.append("silencer")
                evidence.append("silencer_score")
            elif (
                observation.methylation_fraction is not None
                and observation.methylation_fraction >= methylation_silencer_threshold
            ):
                roles.append("silencer_candidate")
                evidence.append("high_methylation")
            elif observation.silencer_score is None:
                missing.append("silencer_score")
            if observation.open_chromatin_signal is not None:
                evidence.append("open_chromatin")
            else:
                missing.append("open_chromatin")
            if observation.contact_support is not None:
                evidence.append("contact_support")
            else:
                missing.append("contact_support")
            state = (
                AtlasAlphaState.AMBIGUOUS
                if len(roles) > 1
                else AtlasAlphaState.SUPPORTED
                if roles and not missing
                else AtlasAlphaState.PARTIAL
                if roles
                else AtlasAlphaState.ABSTAINED
            )
            body = {
                "element_id": observation.element_id,
                "context_key": observation.context_key,
                "roles": roles,
                "evidence": evidence,
            }
            classifications.append(
                RegulatoryRoleClassification(
                    element_id=observation.element_id,
                    context_key=observation.context_key,
                    roles=tuple(roles),
                    state=state,
                    evidence_channels=tuple(dict.fromkeys(evidence)),
                    missing_channels=tuple(dict.fromkeys(missing)),
                    target_gene_ids=observation.target_gene_ids,
                    source_ids=(observation.source_id,),
                    raw_hashes=(observation.raw_hash,),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        if context_mismatch and not observations:
            state = AtlasAlphaState.OUT_OF_DOMAIN
        elif any(item.state == AtlasAlphaState.AMBIGUOUS for item in classifications):
            state = AtlasAlphaState.AMBIGUOUS
        elif issues or any(
            item.state in {AtlasAlphaState.PARTIAL, AtlasAlphaState.ABSTAINED}
            for item in classifications
        ):
            state = AtlasAlphaState.PARTIAL
        elif not classifications:
            state = AtlasAlphaState.ABSTAINED
        else:
            state = AtlasAlphaState.SUPPORTED
        return RegulatoryRoleClassificationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=tuple(observations),
            classifications=tuple(classifications),
            issues=tuple(issues),
            warnings=(
                "Role labels combine declared channels and remain research classifications.",
                "High methylation alone creates only a silencer candidate, not a silencing claim.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "classifications": classifications,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class SuperEnhancerConstituent:
    """One ranked enhancer interval contributing to a candidate."""

    enhancer_id: str
    chromosome: str
    start: int
    end: int
    signal: float
    activity_score: float | None
    target_gene_ids: tuple[str, ...]
    source_id: str
    source_version: str
    raw_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SuperEnhancerCandidate:
    """One bounded super-enhancer candidate interval."""

    candidate_id: str
    chromosome: str
    start: int
    end: int
    constituent_ids: tuple[str, ...]
    target_gene_ids: tuple[str, ...]
    total_signal: float
    median_signal: float
    rank_threshold: float
    evidence_channels: tuple[str, ...]
    state: AtlasAlphaState
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SuperEnhancerAtlasReport:
    """Super-enhancer candidates and input issues."""

    input_hash: str
    context_key: str | None
    state: AtlasAlphaState
    constituents: tuple[SuperEnhancerConstituent, ...]
    candidates: tuple[SuperEnhancerCandidate, ...]
    issues: tuple[AtlasAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SuperEnhancerCandidateAtlas:
    """Group high-ranked observed enhancer intervals into candidate domains."""

    def build(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        minimum_constituents: int = 2,
        merge_gap_bp: int = 0,
        rank_quantile: float = 0.8,
    ) -> SuperEnhancerAtlasReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[AtlasAlphaIssue] = []
        constituents: list[SuperEnhancerConstituent] = []
        context_mismatch = False
        if minimum_constituents < 1 or merge_gap_bp < 0 or not 0 <= rank_quantile <= 1:
            issue = AtlasAlphaIssue(
                "invalid_super_enhancer_parameter",
                "super-enhancer parameters are outside valid bounds",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, AtlasAlphaState.INVALID, (), (), (issue,))
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    AtlasAlphaIssue(
                        "row_not_object",
                        "enhancer candidate row must be an object",
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
                    AtlasAlphaIssue(
                        "context_mismatch",
                        "enhancer row is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                start, end = _interval(row)
                signal = float(_value(row, "signal", "score", "activity_score"))
                if signal < 0:
                    raise ValidationError("enhancer signal cannot be negative")
                constituents.append(
                    SuperEnhancerConstituent(
                        enhancer_id=str(_value(row, "enhancer_id", "element_id", "id", "name")),
                        chromosome=normalize_chromosome(
                            str(_value(row, "chromosome", "chrom", "contig"))
                        ),
                        start=start,
                        end=end,
                        signal=signal,
                        activity_score=_optional_score(
                            _value(row, "activity_score", "activity", default=None)
                        ),
                        target_gene_ids=_text_tuple(
                            _value(row, "target_gene_ids", "targets", "genes", default=())
                        ),
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    AtlasAlphaIssue(
                        "invalid_enhancer_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        if not constituents:
            state = AtlasAlphaState.OUT_OF_DOMAIN if context_mismatch else AtlasAlphaState.ABSTAINED
            return self._report(input_hash, context_key, state, (), (), tuple(issues))
        signals = sorted(item.signal for item in constituents)
        threshold_index = min(len(signals) - 1, int(rank_quantile * (len(signals) - 1)))
        threshold = signals[threshold_index]
        selected = [item for item in constituents if item.signal >= threshold]
        groups: list[list[SuperEnhancerConstituent]] = []
        by_chromosome: dict[str, list[SuperEnhancerConstituent]] = defaultdict(list)
        for item in selected:
            by_chromosome[item.chromosome].append(item)
        for chromosome in sorted(by_chromosome):
            current: list[SuperEnhancerConstituent] = []
            current_end = 0
            for item in sorted(
                by_chromosome[chromosome],
                key=lambda value: (value.start, value.end, value.enhancer_id),
            ):
                if current and item.start > current_end + merge_gap_bp + 1:
                    groups.append(current)
                    current = []
                current.append(item)
                current_end = max(current_end, item.end)
            if current:
                groups.append(current)
        candidates: list[SuperEnhancerCandidate] = []
        for group in groups:
            if len(group) < minimum_constituents:
                continue
            body = {
                "chromosome": group[0].chromosome,
                "start": min(item.start for item in group),
                "end": max(item.end for item in group),
                "constituents": tuple(item.enhancer_id for item in group),
            }
            has_activity = any(item.activity_score is not None for item in group)
            state = AtlasAlphaState.SUPPORTED if has_activity else AtlasAlphaState.PARTIAL
            candidates.append(
                SuperEnhancerCandidate(
                    candidate_id="super-enhancer:" + content_hash(body).split(":", 1)[1][:24],
                    chromosome=group[0].chromosome,
                    start=min(item.start for item in group),
                    end=max(item.end for item in group),
                    constituent_ids=tuple(sorted(item.enhancer_id for item in group)),
                    target_gene_ids=tuple(
                        sorted({gene for item in group for gene in item.target_gene_ids})
                    ),
                    total_signal=round(sum(item.signal for item in group), 6),
                    median_signal=round(float(median(item.signal for item in group)), 6),
                    rank_threshold=round(threshold, 6),
                    evidence_channels=("ranked_constituent_signal", "interval_proximity")
                    + (("declared_activity",) if has_activity else ()),
                    state=state,
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    raw_hashes=tuple(sorted(item.raw_hash for item in group)),
                    content_address=content_hash(body | {"state": state, "threshold": threshold}),
                )
            )
        if context_mismatch and not constituents:
            state = AtlasAlphaState.OUT_OF_DOMAIN
        elif any(item.state == AtlasAlphaState.PARTIAL for item in candidates) or issues:
            state = AtlasAlphaState.PARTIAL
        elif not candidates:
            state = AtlasAlphaState.ABSTAINED
        else:
            state = AtlasAlphaState.SUPPORTED
        return self._report(
            input_hash, context_key, state, tuple(constituents), tuple(candidates), tuple(issues)
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: AtlasAlphaState,
        constituents: tuple[SuperEnhancerConstituent, ...],
        candidates: tuple[SuperEnhancerCandidate, ...],
        issues: tuple[AtlasAlphaIssue, ...],
    ) -> SuperEnhancerAtlasReport:
        return SuperEnhancerAtlasReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            constituents=constituents,
            candidates=candidates,
            issues=issues,
            warnings=(
                (
                    "Super-enhancer candidates are ranked interval groupings, not causal "
                    "regulatory claims."
                ),
                "Target genes are retained only when declared in the input constituent records.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "constituents": constituents,
                    "candidates": candidates,
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


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return float(value)


def _optional_score(value: Any) -> float | None:
    parsed = _optional_float(value)
    if parsed is None:
        return None
    if not 0 <= parsed <= 1:
        raise ValidationError("score must be between zero and one")
    return parsed


def _optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValidationError("integer value cannot be negative")
    return parsed


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", "|").replace(",", "|").split("|")
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


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
    "AtlasAlphaIssue",
    "AtlasAlphaState",
    "EnhancerPromoterSilencerClassifier",
    "MethylationHarmonizationReport",
    "MethylationInterval",
    "MethylationObservation",
    "MethylationTrackHarmonizer",
    "OpenChromatinHarmonizationReport",
    "OpenChromatinInterval",
    "OpenChromatinObservation",
    "OpenChromatinTrackHarmonizer",
    "RegulatoryRoleClassification",
    "RegulatoryRoleClassificationReport",
    "RegulatoryRoleObservation",
    "SuperEnhancerAtlasReport",
    "SuperEnhancerCandidate",
    "SuperEnhancerCandidateAtlas",
    "SuperEnhancerConstituent",
]
