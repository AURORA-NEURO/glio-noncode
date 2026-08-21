"""Context-qualified chromatin track retrieval and delta estimators.

ATAC, DNase, histone, and H3K27ac records are observations tied to a source
snapshot and a declared context. Interval overlap alone is not an activity
claim. Estimators require explicit reference/alternate measurements and keep
replicate spread, missingness, and context mismatch visible.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import ReferenceContext
from .serialization import content_hash, jsonable


class ChromatinTrackKind(StrEnum):
    ATAC = "atac"
    DNASE = "dnase"
    HISTONE = "histone"
    H3K27AC = "h3k27ac"


class ChromatinState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class ChromatinIssue:
    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = "Inspect the assay record and route malformed data to review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinObservation:
    """One normalized track observation."""

    observation_id: str
    track_id: str
    track_kind: ChromatinTrackKind
    chromosome: str
    start: int
    end: int
    signal: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    replicate_id: str | None = None
    mark: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "track_id",
            "chromosome",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"chromatin {name} is required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("chromatin interval is invalid")
        if self.signal < 0:
            raise ValidationError("chromatin signal cannot be negative")

    def overlaps(self, chromosome: str, start: int, end: int) -> bool:
        return (
            normalize_chromosome(self.chromosome) == normalize_chromosome(chromosome)
            and self.start <= end
            and start <= self.end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinTrackBatch:
    source_id: str
    input_hash: str
    observations: tuple[ChromatinObservation, ...]
    issues: tuple[ChromatinIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ChromatinTrackParser:
    """Parse BED-like TSV or JSON tracks for the first chromatin slice."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        track_kind: ChromatinTrackKind | str,
        input_format: str | None = None,
    ) -> ChromatinTrackBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("chromatin input must not be empty")
        kind = ChromatinTrackKind(str(track_kind))
        first = next(line.strip() for line in text.splitlines() if line.strip())
        selected = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid chromatin JSON: {exc}") from exc
            rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("chromatin JSON must contain observations")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("chromatin TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported chromatin format: {selected}")
        observations: list[ChromatinObservation] = []
        issues: list[ChromatinIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(ChromatinIssue("invalid_chromatin_row", "row must be an object"))
                continue
            raw_hash = content_hash(row)
            try:
                start_zero = int(self._value(row, "start", "chrom_start"))
                end_exclusive = int(self._value(row, "end", "chrom_end"))
                if start_zero < 0 or end_exclusive <= start_zero:
                    raise ValidationError("track interval must satisfy 0 <= start < end")
                observations.append(
                    ChromatinObservation(
                        observation_id=f"{source_id}:{index}",
                        track_id=str(
                            self._value(row, "track_id", "track", default=f"track-{index}")
                        ),
                        track_kind=ChromatinTrackKind(
                            str(self._value(row, "track_kind", "kind", default=kind.value))
                        ),
                        chromosome=normalize_chromosome(
                            str(self._value(row, "chromosome", "chrom"))
                        ),
                        start=start_zero + 1,
                        end=end_exclusive,
                        signal=float(self._value(row, "signal", "score", "value")),
                        context_key=str(
                            self._value(row, "context_key", "context", default="unspecified")
                        ),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                        raw_hash=raw_hash,
                        replicate_id=self._optional_text(row, "replicate_id", "replicate"),
                        mark=self._optional_text(row, "mark", "histone_mark"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ChromatinIssue(
                        "invalid_chromatin_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "observations": tuple(observations),
            "issues": tuple(issues),
        }
        return ChromatinTrackBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        return default

    @classmethod
    def _optional_text(cls, row: Mapping[str, Any], *names: str) -> str | None:
        value = cls._value(row, *names)
        return None if value is None else str(value)


@dataclass(frozen=True, slots=True)
class ChromatinQueryResult:
    track_kind: ChromatinTrackKind
    chromosome: str
    start: int
    end: int
    context_key: str
    state: ChromatinState
    observations: tuple[ChromatinObservation, ...]
    median_signal: float | None
    replicate_spread: float | None
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ChromatinContextRetriever:
    """Retrieve observations only when track kind and context both match."""

    def __init__(self, observations: Iterable[ChromatinObservation]) -> None:
        self._observations = tuple(observations)

    def query(
        self,
        track_kind: ChromatinTrackKind | str,
        chromosome: str,
        start: int,
        end: int,
        context: ReferenceContext,
    ) -> ChromatinQueryResult:
        if start < 1 or end < start:
            raise ValidationError("chromatin query interval must satisfy 1 <= start <= end")
        kind = ChromatinTrackKind(str(track_kind))
        context_key = context.key
        kind_rows = tuple(row for row in self._observations if row.track_kind == kind)
        overlaps = tuple(row for row in kind_rows if row.overlaps(chromosome, start, end))
        matches = tuple(row for row in overlaps if row.context_key == context_key)
        if overlaps and not matches:
            state = ChromatinState.OUT_OF_DOMAIN
            reason = "overlapping chromatin observations exist only for another context"
        elif not matches:
            state = ChromatinState.ABSENT
            reason = "no context-matched chromatin observation overlaps the interval"
        elif len(matches) == 1:
            state = ChromatinState.SUPPORTED
            reason = "one context-matched chromatin observation was retrieved"
        else:
            state = ChromatinState.AMBIGUOUS
            reason = "multiple context-matched chromatin observations were retrieved"
        signals = tuple(row.signal for row in matches)
        body = {
            "kind": kind,
            "chromosome": normalize_chromosome(chromosome),
            "start": start,
            "end": end,
            "context_key": context_key,
            "observations": matches,
            "state": state,
        }
        return ChromatinQueryResult(
            track_kind=kind,
            chromosome=normalize_chromosome(chromosome),
            start=start,
            end=end,
            context_key=context_key,
            state=state,
            observations=matches,
            median_signal=round(median(signals), 9) if signals else None,
            replicate_spread=round(max(signals) - min(signals), 9) if len(signals) > 1 else None,
            reason=reason,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class AccessibilityMeasurement:
    measurement_id: str
    variant_id: str
    context_key: str
    assay: ChromatinTrackKind
    reference_signal: float | None
    alternate_signal: float | None
    source_id: str
    raw_hash: str
    replicate_count: int = 1

    def __post_init__(self) -> None:
        if not self.measurement_id or not self.variant_id or not self.context_key:
            raise ValidationError("accessibility measurement identifiers are required")
        if self.assay not in {ChromatinTrackKind.ATAC, ChromatinTrackKind.DNASE}:
            raise ValidationError("accessibility measurement assay must be ATAC or DNase")
        for name in ("reference_signal", "alternate_signal"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValidationError(f"{name} cannot be negative")
        if self.replicate_count < 1:
            raise ValidationError("replicate_count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AccessibilityDelta:
    variant_id: str
    context_key: str
    state: ChromatinState
    delta: float | None
    relative_delta: float | None
    replicate_count: int
    limitations: tuple[str, ...]
    source_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AccessibilityDeltaEstimator:
    """Estimate measured ATAC/DNase deltas with missingness and zero guards."""

    def estimate(self, measurement: AccessibilityMeasurement) -> AccessibilityDelta:
        limitations = (
            "Accessibility delta is an assay-derived comparison, not a causal effect estimate.",
            "A zero or missing reference signal prevents relative normalization.",
        )
        if measurement.reference_signal is None or measurement.alternate_signal is None:
            state = ChromatinState.ABSTAINED
            delta = None
            relative = None
        else:
            delta = measurement.alternate_signal - measurement.reference_signal
            relative = (
                None
                if measurement.reference_signal == 0
                else delta / measurement.reference_signal
            )
            state = ChromatinState.SUPPORTED
        body = {
            "measurement": measurement,
            "state": state,
            "delta": delta,
            "relative": relative,
        }
        return AccessibilityDelta(
            variant_id=measurement.variant_id,
            context_key=measurement.context_key,
            state=state,
            delta=None if delta is None else round(delta, 9),
            relative_delta=None if relative is None else round(relative, 9),
            replicate_count=measurement.replicate_count,
            limitations=limitations,
            source_id=measurement.source_id,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class H3K27acActivity:
    element_id: str
    context_key: str
    state: ChromatinState
    signal: float | None
    replicate_count: int
    source_id: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class H3K27acActivityEstimator:
    """Report H3K27ac signal as an observation, not an enhancer truth label."""

    def estimate(
        self,
        element_id: str,
        query: ChromatinQueryResult,
    ) -> H3K27acActivity:
        if query.track_kind != ChromatinTrackKind.H3K27AC:
            raise ValidationError("H3K27ac estimator requires an H3K27ac query")
        signal = query.median_signal
        if query.state in {ChromatinState.ABSENT, ChromatinState.OUT_OF_DOMAIN}:
            state = ChromatinState.ABSTAINED
        elif signal is None:
            state = ChromatinState.ABSTAINED
        elif query.state == ChromatinState.AMBIGUOUS:
            state = ChromatinState.AMBIGUOUS
        else:
            state = ChromatinState.SUPPORTED
        limitations = (
            "H3K27ac signal is an assay observation and does not establish enhancer "
            "activity alone.",
            "Target-gene linkage, cell composition, and assay calibration remain "
            "separate evidence.",
        )
        body = {
            "element_id": element_id,
            "context_key": query.context_key,
            "state": state,
            "signal": signal,
            "observation_ids": tuple(row.observation_id for row in query.observations),
        }
        return H3K27acActivity(
            element_id=element_id,
            context_key=query.context_key,
            state=state,
            signal=signal,
            replicate_count=len(query.observations),
            source_id=(query.observations[0].source_id if query.observations else "none"),
            limitations=limitations,
            content_address=content_hash(body),
        )


__all__ = [
    "AccessibilityDelta",
    "AccessibilityDeltaEstimator",
    "AccessibilityMeasurement",
    "ChromatinContextRetriever",
    "ChromatinIssue",
    "ChromatinObservation",
    "ChromatinQueryResult",
    "ChromatinState",
    "ChromatinTrackBatch",
    "ChromatinTrackKind",
    "ChromatinTrackParser",
    "H3K27acActivity",
    "H3K27acActivityEstimator",
]
