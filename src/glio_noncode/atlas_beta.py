"""Scientific-beta glioma atlas and histone-track contracts.

This module extends the cCRE atlas boundary with explicit molecular-state
profiles and a transparent histone-mark harmonizer. It keeps IDH-mutant,
IDH-wildtype, and H3K27-altered evidence distinct, requires exact context
matches for queries, and never promotes an atlas overlap or signal summary to
an activity, causal, or clinical claim.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import ReferenceContext
from .serialization import content_hash, jsonable, require_non_empty


class AtlasBetaState(StrEnum):
    """Evidence state used by state atlases and histone harmonization."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"


class MolecularAtlasState(StrEnum):
    IDH_MUTANT = "IDH-mutant"
    IDH_WILDTYPE = "IDH-wildtype"
    H3K27_ALTERED = "H3K27-altered"


@dataclass(frozen=True, slots=True)
class AtlasBetaIssue:
    """Row-level atlas or track issue."""

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
class MolecularStateAtlasRecord:
    """One molecular-state-qualified regulatory element observation."""

    element_id: str
    chromosome: str
    start: int
    end: int
    molecular_state: MolecularAtlasState
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    assay: str
    activity_score: float | None = None
    cell_state: str | None = None
    territory: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "element_id",
            "chromosome",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "assay",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("state atlas interval is invalid")
        if self.activity_score is not None and not 0 <= self.activity_score <= 1:
            raise ValidationError("state atlas activity_score must be between zero and one")

    def overlaps(self, chromosome: str, start: int, end: int) -> bool:
        return (
            normalize_chromosome(self.chromosome) == normalize_chromosome(chromosome)
            and self.start <= end
            and start <= self.end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularStateAtlasBatch:
    source_id: str
    source_version: str
    input_hash: str
    records: tuple[MolecularStateAtlasRecord, ...]
    issues: tuple[AtlasBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularStateAtlasMatch:
    element_id: str
    molecular_state: MolecularAtlasState
    chromosome: str
    start: int
    end: int
    context_key: str
    activity_score: float | None
    assay: str
    source_id: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularStateAtlasQueryResult:
    molecular_state: MolecularAtlasState
    context_key: str
    chromosome: str
    start: int
    end: int
    state: AtlasBetaState
    matches: tuple[MolecularStateAtlasMatch, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MolecularStateAtlasAdapter:
    """Parse and query IDH/H3K27 molecular-state atlas records."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        coordinate_system: str = "bed",
    ) -> MolecularStateAtlasBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("molecular-state atlas input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                return self._batch(
                    source_id,
                    source_version,
                    text,
                    (),
                    (
                        AtlasBetaIssue(
                            "invalid_json", str(exc), content_hash(text), severity="error"
                        ),
                    ),
                )
            rows = (
                payload.get("records", payload.get("elements"))
                if isinstance(payload, Mapping)
                else payload
            )
            if not isinstance(rows, list):
                return self._batch(
                    source_id,
                    source_version,
                    text,
                    (),
                    (
                        AtlasBetaIssue(
                            "invalid_json_shape",
                            "state atlas JSON must contain a records list",
                            content_hash(payload),
                            severity="error",
                        ),
                    ),
                )
        elif selected in {"tsv", "csv"}:
            reader = csv.DictReader(io.StringIO(text), delimiter="\t" if selected == "tsv" else ",")
            if not reader.fieldnames:
                raise ValidationError("state atlas input requires a header")
            rows = list(reader)
        else:
            raise ValidationError(f"unsupported state atlas format: {selected}")
        records: list[MolecularStateAtlasRecord] = []
        issues: list[AtlasBetaIssue] = []
        for row_number, row in enumerate(rows, start=1):
            raw_hash = content_hash(row)
            try:
                start = int(_value(row, "start", "chrom_start"))
                end = int(_value(row, "end", "chrom_end"))
                if coordinate_system.lower() == "bed":
                    if start < 0 or end <= start:
                        raise ValidationError("BED interval must satisfy 0 <= start < end")
                    start += 1
                state = MolecularAtlasState(str(_value(row, "molecular_state", "state", "class")))
                score_value = _value(row, "activity_score", "score", "signal")
                score = None if score_value in {None, "", "."} else float(score_value)
                if score is not None and score > 1 and score <= 100:
                    score /= 100.0
                records.append(
                    MolecularStateAtlasRecord(
                        element_id=str(_value(row, "element_id", "ccre_id", "id", "name")),
                        chromosome=normalize_chromosome(str(_value(row, "chromosome", "chrom"))),
                        start=start,
                        end=end,
                        molecular_state=state,
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        assay=str(_value(row, "assay", "track_kind", default="unspecified")),
                        activity_score=score,
                        cell_state=_optional_text(_value(row, "cell_state", "cell_type")),
                        territory=_optional_text(_value(row, "territory", "microenvironment")),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    AtlasBetaIssue(
                        "invalid_state_atlas_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row) if isinstance(row, Mapping) else {},
                    )
                )
        return self._batch(source_id, source_version, text, tuple(records), tuple(issues))

    def query(
        self,
        records: Iterable[MolecularStateAtlasRecord],
        *,
        molecular_state: MolecularAtlasState | str,
        chromosome: str,
        start: int,
        end: int,
        context: ReferenceContext,
    ) -> MolecularStateAtlasQueryResult:
        if start < 1 or end < start:
            raise ValidationError("state atlas query interval is invalid")
        selected_state = MolecularAtlasState(str(molecular_state))
        values = tuple(
            record
            for record in records
            if record.molecular_state == selected_state and record.overlaps(chromosome, start, end)
        )
        compatible = tuple(record for record in values if record.context_key == context.key)
        if values and not compatible:
            state = AtlasBetaState.OUT_OF_DOMAIN
            reason = "overlapping state-atlas records do not match the exact context key"
        elif not compatible:
            state = AtlasBetaState.ABSTAINED
            reason = "no exact-state record overlaps the requested interval"
        else:
            state = AtlasBetaState.AMBIGUOUS if len(compatible) > 1 else AtlasBetaState.SUPPORTED
            reason = (
                "multiple exact-state records overlap"
                if len(compatible) > 1
                else "one exact-state record overlaps"
            )
        matches = tuple(self._match(record, context) for record in compatible)
        body = {
            "state": selected_state,
            "context": context.key,
            "chromosome": chromosome,
            "start": start,
            "end": end,
            "matches": matches,
        }
        return MolecularStateAtlasQueryResult(
            selected_state,
            context.key,
            normalize_chromosome(chromosome),
            start,
            end,
            state,
            matches,
            reason,
            content_hash(body),
        )

    @staticmethod
    def _match(
        record: MolecularStateAtlasRecord, context: ReferenceContext
    ) -> MolecularStateAtlasMatch:
        body = {
            "element_id": record.element_id,
            "state": record.molecular_state,
            "context": context.key,
            "raw_hash": record.raw_hash,
        }
        return MolecularStateAtlasMatch(
            record.element_id,
            record.molecular_state,
            record.chromosome,
            record.start,
            record.end,
            context.key,
            record.activity_score,
            record.assay,
            record.source_id,
            record.raw_hash,
            content_hash(body),
        )

    @staticmethod
    def _batch(
        source_id: str,
        source_version: str,
        text: str,
        records: tuple[MolecularStateAtlasRecord, ...],
        issues: tuple[AtlasBetaIssue, ...],
    ) -> MolecularStateAtlasBatch:
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "input_hash": content_hash(text),
            "records": records,
            "issues": issues,
        }
        return MolecularStateAtlasBatch(
            source_id, source_version, content_hash(text), records, issues, content_hash(body)
        )


@dataclass(frozen=True, slots=True)
class HistoneObservation:
    """One histone-mark interval observation."""

    observation_id: str
    mark: str
    chromosome: str
    start: int
    end: int
    signal: float
    replicate_id: str
    caller_id: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "mark",
            "chromosome",
            "replicate_id",
            "caller_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("histone interval is invalid")
        if self.signal < 0:
            raise ValidationError("histone signal cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HistoneHarmonizedInterval:
    """Atomic histone interval with replicate spread and caller provenance."""

    interval_id: str
    mark: str
    chromosome: str
    start: int
    end: int
    context_key: str
    median_signal: float
    minimum_signal: float
    maximum_signal: float
    signal_spread: float
    replicate_ids: tuple[str, ...]
    caller_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    state: AtlasBetaState
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HistoneHarmonizationBatch:
    input_hash: str
    state: AtlasBetaState
    observations: tuple[HistoneObservation, ...]
    intervals: tuple[HistoneHarmonizedInterval, ...]
    issues: tuple[AtlasBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class HistoneMarkTrackHarmonizer:
    """Normalize histone tracks to atomic observed intervals and expose spread."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        coordinate_system: str = "bed",
        spread_tolerance: float = 0.25,
    ) -> HistoneHarmonizationBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("histone track input must not be empty")
        if spread_tolerance < 0:
            raise ValidationError("spread_tolerance must be non-negative")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            payload = json.loads(text)
            rows = (
                payload.get("records", payload.get("observations"))
                if isinstance(payload, Mapping)
                else payload
            )
            if not isinstance(rows, list):
                raise ValidationError("histone JSON must contain a records list")
        elif selected in {"tsv", "csv"}:
            reader = csv.DictReader(io.StringIO(text), delimiter="\t" if selected == "tsv" else ",")
            if not reader.fieldnames:
                raise ValidationError("histone track input requires a header")
            rows = list(reader)
        else:
            raise ValidationError(f"unsupported histone track format: {selected}")
        observations: list[HistoneObservation] = []
        issues: list[AtlasBetaIssue] = []
        for row_number, row in enumerate(rows, start=1):
            raw_hash = content_hash(row)
            try:
                start = int(_value(row, "start", "chrom_start"))
                end = int(_value(row, "end", "chrom_end"))
                if coordinate_system.lower() == "bed":
                    if start < 0 or end <= start:
                        raise ValidationError("BED interval must satisfy 0 <= start < end")
                    start += 1
                observations.append(
                    HistoneObservation(
                        observation_id=str(
                            _value(
                                row,
                                "observation_id",
                                "id",
                                "name",
                                default=f"{source_id}:{row_number}",
                            )
                        ),
                        mark=str(_value(row, "mark", "histone_mark", "target")),
                        chromosome=normalize_chromosome(str(_value(row, "chromosome", "chrom"))),
                        start=start,
                        end=end,
                        signal=float(_value(row, "signal", "score", "value")),
                        replicate_id=str(
                            _value(row, "replicate_id", "replicate", default="unspecified")
                        ),
                        caller_id=str(_value(row, "caller_id", "caller", default="unspecified")),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    AtlasBetaIssue(
                        "invalid_histone_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row) if isinstance(row, Mapping) else {},
                    )
                )
        harmonized = self.harmonize(observations, spread_tolerance=spread_tolerance)
        if not issues:
            return harmonized
        return HistoneHarmonizationBatch(
            input_hash=harmonized.input_hash,
            state=AtlasBetaState.PARTIAL,
            observations=harmonized.observations,
            intervals=harmonized.intervals,
            issues=harmonized.issues + tuple(issues),
            warnings=harmonized.warnings,
            content_address=content_hash(
                {
                    "observations": harmonized.observations,
                    "intervals": harmonized.intervals,
                    "issues": harmonized.issues + tuple(issues),
                }
            ),
        )

    def harmonize(
        self,
        observations: Iterable[HistoneObservation],
        *,
        spread_tolerance: float = 0.25,
    ) -> HistoneHarmonizationBatch:
        values = tuple(observations)
        input_hash = content_hash(values)
        groups: dict[tuple[str, str, str], list[HistoneObservation]] = defaultdict(list)
        for observation in values:
            groups[(observation.chromosome, observation.mark, observation.context_key)].append(
                observation
            )
        intervals: list[HistoneHarmonizedInterval] = []
        for group_key, group in sorted(groups.items()):
            chromosome, mark, context_key = group_key
            boundaries = sorted(
                {boundary for item in group for boundary in (item.start, item.end + 1)}
            )
            for start, right_exclusive in zip(boundaries, boundaries[1:], strict=False):
                active = tuple(
                    item
                    for item in group
                    if item.start <= start and item.end >= right_exclusive - 1
                )
                if not active:
                    continue
                signals = tuple(item.signal for item in active)
                spread = max(signals) - min(signals)
                replicate_ids = tuple(sorted({item.replicate_id for item in active}))
                caller_ids = tuple(sorted({item.caller_id for item in active}))
                state = (
                    AtlasBetaState.SUPPORTED
                    if len(replicate_ids) >= 2 and spread <= spread_tolerance
                    else AtlasBetaState.AMBIGUOUS
                    if spread > spread_tolerance
                    else AtlasBetaState.PARTIAL
                )
                body = {
                    "chromosome": chromosome,
                    "mark": mark,
                    "context_key": context_key,
                    "start": start,
                    "end": right_exclusive - 1,
                    "observation_ids": tuple(item.observation_id for item in active),
                }
                intervals.append(
                    HistoneHarmonizedInterval(
                        interval_id="histone:" + content_hash(body).split(":", 1)[1][:24],
                        mark=mark,
                        chromosome=chromosome,
                        start=start,
                        end=right_exclusive - 1,
                        context_key=context_key,
                        median_signal=round(float(median(signals)), 6),
                        minimum_signal=round(min(signals), 6),
                        maximum_signal=round(max(signals), 6),
                        signal_spread=round(spread, 6),
                        replicate_ids=replicate_ids,
                        caller_ids=caller_ids,
                        source_ids=tuple(sorted({item.source_id for item in active})),
                        source_observation_ids=tuple(
                            sorted(item.observation_id for item in active)
                        ),
                        state=state,
                        raw_hashes=tuple(sorted(item.raw_hash for item in active)),
                        content_address=content_hash(
                            body | {"state": state, "median_signal": median(signals)}
                        ),
                    )
                )
        state = (
            AtlasBetaState.ABSTAINED
            if not intervals
            else AtlasBetaState.AMBIGUOUS
            if any(item.state == AtlasBetaState.AMBIGUOUS for item in intervals)
            else AtlasBetaState.PARTIAL
            if any(item.state == AtlasBetaState.PARTIAL for item in intervals)
            else AtlasBetaState.SUPPORTED
        )
        return HistoneHarmonizationBatch(
            input_hash=input_hash,
            state=state,
            observations=values,
            intervals=tuple(intervals),
            issues=(),
            warnings=(
                "Histone harmonization is a descriptive signal summary, not a calibrated "
                "activity call.",
                "Intervals are split at observed boundaries; unobserved bases are not imputed.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": values,
                    "intervals": intervals,
                }
            ),
        )


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return default


def _optional_text(value: Any) -> str | None:
    if value in {None, "", "."}:
        return None
    return str(value)


__all__ = [
    "AtlasBetaIssue",
    "AtlasBetaState",
    "HistoneHarmonizationBatch",
    "HistoneHarmonizedInterval",
    "HistoneMarkTrackHarmonizer",
    "HistoneObservation",
    "MolecularAtlasState",
    "MolecularStateAtlasAdapter",
    "MolecularStateAtlasBatch",
    "MolecularStateAtlasMatch",
    "MolecularStateAtlasQueryResult",
    "MolecularStateAtlasRecord",
]
