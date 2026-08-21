"""Context-qualified 3D genome observations and topology estimators.

The Domain 09 plane handles Hi-C/Micro-C contact records, matrix quality
receipts, deterministic normalization, boundary ensembles, and insulation
score deltas.  Contact overlap is treated as measured topology evidence only;
it is not converted into a causal regulatory or clinical claim.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from statistics import mean, median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import ReferenceContext
from .serialization import content_hash, jsonable


class TopologyAssay(StrEnum):
    """Supported contact-assay families in the first topology slice."""

    HI_C = "hi-c"
    MICRO_C = "micro-c"


class TopologyState(StrEnum):
    """Result state that preserves missingness and context transport."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class TopologyIssue:
    """A quarantined parser or quality-control issue."""

    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = "Inspect the source row or matrix metadata before reuse."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContactRecord:
    """One normalized pairwise contact observation.

    Input BED-like coordinates are converted from zero-based half-open to
    one-based closed intervals by the parser.  Pair order is retained in raw
    attributes while ``canonical_key`` provides deterministic deduplication.
    """

    interaction_id: str
    assay: TopologyAssay
    chromosome_a: str
    start_a: int
    end_a: int
    chromosome_b: str
    start_b: int
    end_b: int
    signal: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    resolution: int | None = None
    replicate_id: str | None = None
    normalization: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "interaction_id",
            "chromosome_a",
            "chromosome_b",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"contact {name} is required")
        self._validate_interval(self.start_a, self.end_a, "a")
        self._validate_interval(self.start_b, self.end_b, "b")
        if not isfinite(self.signal) or self.signal < 0:
            raise ValidationError("contact signal must be finite and non-negative")
        if self.resolution is not None and self.resolution < 1:
            raise ValidationError("contact resolution must be positive")

    @staticmethod
    def _validate_interval(start: int, end: int, label: str) -> None:
        if start < 1 or end < start:
            raise ValidationError(f"contact interval {label} must satisfy 1 <= start <= end")

    @property
    def endpoint_a(self) -> tuple[str, int, int]:
        return normalize_chromosome(self.chromosome_a), self.start_a, self.end_a

    @property
    def endpoint_b(self) -> tuple[str, int, int]:
        return normalize_chromosome(self.chromosome_b), self.start_b, self.end_b

    @property
    def canonical_key(self) -> tuple[tuple[str, int, int], tuple[str, int, int]]:
        return tuple(sorted((self.endpoint_a, self.endpoint_b)))  # type: ignore[return-value]

    def matches_pair(
        self,
        chromosome_a: str,
        start_a: int,
        end_a: int,
        chromosome_b: str,
        start_b: int,
        end_b: int,
    ) -> bool:
        left = (normalize_chromosome(chromosome_a), start_a, end_a)
        right = (normalize_chromosome(chromosome_b), start_b, end_b)
        return self.canonical_key == tuple(sorted((left, right)))

    def overlaps_pair(
        self,
        chromosome_a: str,
        start_a: int,
        end_a: int,
        chromosome_b: str,
        start_b: int,
        end_b: int,
    ) -> bool:
        requested = (
            (normalize_chromosome(chromosome_a), start_a, end_a),
            (normalize_chromosome(chromosome_b), start_b, end_b),
        )
        observed = (self.endpoint_a, self.endpoint_b)
        direct = self._overlaps(observed[0], requested[0]) and self._overlaps(
            observed[1], requested[1]
        )
        swapped = self._overlaps(observed[0], requested[1]) and self._overlaps(
            observed[1], requested[0]
        )
        return direct or swapped

    @staticmethod
    def _overlaps(left: tuple[str, int, int], right: tuple[str, int, int]) -> bool:
        return left[0] == right[0] and left[1] <= right[2] and right[1] <= left[2]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContactMatrixBatch:
    """Loss-accounted contact import result."""

    source_id: str
    input_hash: str
    records: tuple[ContactRecord, ...]
    issues: tuple[TopologyIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContactMatrixParser:
    """Parse long-form Hi-C or Micro-C contacts from TSV or JSON."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        assay: TopologyAssay | str,
        input_format: str | None = None,
    ) -> ContactMatrixBatch:
        if not source_id.strip():
            raise ValidationError("contact source_id is required")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("contact input must not be empty")
        assay_value = TopologyAssay(str(assay))
        first = next(line.strip() for line in text.splitlines() if line.strip())
        selected = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid contact JSON: {exc}") from exc
            rows = payload.get("records", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("contact JSON must contain a records list")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("contact TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported contact format: {selected}")

        records: list[ContactRecord] = []
        issues: list[TopologyIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(TopologyIssue("invalid_contact_row", "row must be an object"))
                continue
            raw_hash = content_hash(row)
            try:
                start_a = int(self._value(row, "start_a", "start1", "chrom_start_a"))
                end_a = int(self._value(row, "end_a", "end1", "chrom_end_a"))
                start_b = int(self._value(row, "start_b", "start2", "chrom_start_b"))
                end_b = int(self._value(row, "end_b", "end2", "chrom_end_b"))
                if min(start_a, start_b) < 0 or end_a <= start_a or end_b <= start_b:
                    raise ValidationError("contact input intervals must be 0-based half-open")
                record_assay = TopologyAssay(
                    str(self._value(row, "assay", "assay_type", default=assay_value.value))
                )
                records.append(
                    ContactRecord(
                        interaction_id=str(
                            self._value(
                                row,
                                "interaction_id",
                                "contact_id",
                                default=f"{source_id}:{index}",
                            )
                        ),
                        assay=record_assay,
                        chromosome_a=normalize_chromosome(
                            str(self._value(row, "chromosome_a", "chrom1", "chrom_a"))
                        ),
                        start_a=start_a + 1,
                        end_a=end_a,
                        chromosome_b=normalize_chromosome(
                            str(self._value(row, "chromosome_b", "chrom2", "chrom_b"))
                        ),
                        start_b=start_b + 1,
                        end_b=end_b,
                        signal=float(
                            self._value(row, "signal", "count", "contact_count", "score")
                        ),
                        context_key=str(self._value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                        raw_hash=raw_hash,
                        resolution=self._optional_int(row, "resolution", "bin_size"),
                        replicate_id=self._optional_text(row, "replicate_id", "replicate"),
                        normalization=self._optional_text(row, "normalization", "norm"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TopologyIssue(
                        "invalid_contact_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "records": tuple(records),
            "issues": tuple(issues),
        }
        return ContactMatrixBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            records=tuple(records),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        if default is not None:
            return default
        raise ValidationError(f"contact field is required: {names[0]}")

    @classmethod
    def _optional_text(cls, row: Mapping[str, Any], *names: str) -> str | None:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return str(value)
        return None

    @classmethod
    def _optional_int(cls, row: Mapping[str, Any], *names: str) -> int | None:
        value = cls._optional_text(row, *names)
        return None if value is None else int(value)


@dataclass(frozen=True, slots=True)
class ContactMatrixQcReport:
    """Descriptive matrix QC with duplicate and zero-signal visibility."""

    assay: TopologyAssay | None
    record_count: int
    unique_pair_count: int
    duplicate_count: int
    zero_signal_count: int
    min_signal: float | None
    max_signal: float | None
    mean_signal: float | None
    state: TopologyState
    anomalies: tuple[str, ...]
    normalization_method: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContactMatrixQcEvaluator:
    """Evaluate matrix observations without treating QC as biological validity."""

    def evaluate(
        self,
        records: Iterable[ContactRecord],
        *,
        normalization_method: str = "none",
    ) -> ContactMatrixQcReport:
        values = tuple(records)
        if normalization_method not in {"none", "mean", "max"}:
            raise ValidationError("normalization_method must be none, mean, or max")
        signals = tuple(record.signal for record in values)
        pairs = {record.canonical_key for record in values}
        duplicates = len(values) - len(pairs)
        anomalies: list[str] = []
        if duplicates:
            anomalies.append("duplicate canonical contact pairs are present")
        if any(signal == 0 for signal in signals):
            anomalies.append("zero-signal contact rows are present")
        if not values:
            state = TopologyState.ABSTAINED
            anomalies.append("no contact rows were supplied")
        elif duplicates or any(signal == 0 for signal in signals):
            state = TopologyState.PARTIAL
        else:
            state = TopologyState.SUPPORTED
        assay = values[0].assay if values and len({item.assay for item in values}) == 1 else None
        body = {
            "assay": assay,
            "signals": signals,
            "pairs": tuple(sorted(pairs)),
            "normalization_method": normalization_method,
            "state": state,
            "anomalies": tuple(anomalies),
        }
        return ContactMatrixQcReport(
            assay=assay,
            record_count=len(values),
            unique_pair_count=len(pairs),
            duplicate_count=duplicates,
            zero_signal_count=sum(signal == 0 for signal in signals),
            min_signal=min(signals) if signals else None,
            max_signal=max(signals) if signals else None,
            mean_signal=round(mean(signals), 9) if signals else None,
            state=state,
            anomalies=tuple(anomalies),
            normalization_method=normalization_method,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class NormalizedContact:
    """One contact score after a declared deterministic normalization."""

    interaction_id: str
    canonical_key: tuple[tuple[str, int, int], tuple[str, int, int]]
    raw_signal: float
    normalized_signal: float | None
    normalization_method: str
    state: TopologyState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NormalizedContactMatrix:
    """Normalized contacts plus the QC receipt that preceded them."""

    records: tuple[NormalizedContact, ...]
    qc: ContactMatrixQcReport
    state: TopologyState
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContactMatrixNormalizer:
    """Apply only transparent mean or max scaling; no hidden ICE claim."""

    def normalize(
        self,
        records: Iterable[ContactRecord],
        *,
        method: str = "mean",
    ) -> NormalizedContactMatrix:
        values = tuple(records)
        if method not in {"mean", "max", "none"}:
            raise ValidationError("contact normalization method must be mean, max, or none")
        qc = ContactMatrixQcEvaluator().evaluate(values, normalization_method=method)
        denominator = (
            mean(record.signal for record in values)
            if method == "mean" and values
            else max((record.signal for record in values), default=0.0)
            if method == "max"
            else 1.0
        )
        normalized: list[NormalizedContact] = []
        for record in values:
            if method != "none" and denominator == 0:
                state = TopologyState.ABSTAINED
                value = None
            else:
                state = TopologyState.SUPPORTED
                value = round(record.signal / denominator, 9)
            body = {
                "interaction_id": record.interaction_id,
                "canonical_key": record.canonical_key,
                "raw_signal": record.signal,
                "normalized_signal": value,
                "method": method,
                "state": state,
            }
            normalized.append(
                NormalizedContact(
                    interaction_id=record.interaction_id,
                    canonical_key=record.canonical_key,
                    raw_signal=record.signal,
                    normalized_signal=value,
                    normalization_method=method,
                    state=state,
                    content_address=content_hash(body),
                )
            )
        state = (
            TopologyState.ABSTAINED
            if values and denominator == 0 and method != "none"
            else qc.state
        )
        body = {"records": normalized, "qc": qc, "method": method, "state": state}
        return NormalizedContactMatrix(
            records=tuple(normalized),
            qc=qc,
            state=state,
            limitations=(
                "Mean and max scaling are deterministic descriptive transforms, not ICE balancing.",
                "Normalization does not correct assay-specific biases or establish "
                "biological causality.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ContactQueryResult:
    """Context-gated contact lookup over a pair of genomic loci."""

    assay: TopologyAssay
    context_key: str
    chromosome_a: str
    start_a: int
    end_a: int
    chromosome_b: str
    start_b: int
    end_b: int
    state: TopologyState
    records: tuple[ContactRecord, ...]
    median_signal: float | None
    replicate_spread: float | None
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TopologyContactRetriever:
    """Retrieve contact observations only when assay and context both match."""

    def __init__(self, records: Iterable[ContactRecord]) -> None:
        self._records = tuple(records)

    def query(
        self,
        assay: TopologyAssay | str,
        chromosome_a: str,
        start_a: int,
        end_a: int,
        chromosome_b: str,
        start_b: int,
        end_b: int,
        context: ReferenceContext,
    ) -> ContactQueryResult:
        if min(start_a, start_b) < 1 or end_a < start_a or end_b < start_b:
            raise ValidationError("topology query intervals must satisfy 1 <= start <= end")
        assay_value = TopologyAssay(str(assay))
        assay_rows = tuple(row for row in self._records if row.assay == assay_value)
        overlaps = tuple(
            row
            for row in assay_rows
            if row.overlaps_pair(
                chromosome_a,
                start_a,
                end_a,
                chromosome_b,
                start_b,
                end_b,
            )
        )
        matches = tuple(row for row in overlaps if row.context_key == context.key)
        if matches:
            state = TopologyState.SUPPORTED if len(matches) == 1 else TopologyState.AMBIGUOUS
            reason = (
                "one context-matched contact was retrieved"
                if len(matches) == 1
                else "multiple context-matched contacts were retrieved"
            )
        elif overlaps:
            state = TopologyState.OUT_OF_DOMAIN
            reason = "overlapping contacts exist only for another context"
        else:
            state = TopologyState.ABSENT
            reason = "no assay-matched contact overlaps the requested pair"
        signals = tuple(row.signal for row in matches)
        body = {
            "assay": assay_value,
            "context": context,
            "loci": ((chromosome_a, start_a, end_a), (chromosome_b, start_b, end_b)),
            "records": matches,
            "state": state,
        }
        return ContactQueryResult(
            assay=assay_value,
            context_key=context.key,
            chromosome_a=normalize_chromosome(chromosome_a),
            start_a=start_a,
            end_a=end_a,
            chromosome_b=normalize_chromosome(chromosome_b),
            start_b=start_b,
            end_b=end_b,
            state=state,
            records=matches,
            median_signal=round(median(signals), 9) if signals else None,
            replicate_spread=round(max(signals) - min(signals), 9) if len(signals) > 1 else None,
            reason=reason,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class TadBoundaryObservation:
    """One caller/assay TAD boundary candidate."""

    boundary_id: str
    assay: TopologyAssay
    chromosome: str
    position: int
    score: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    caller_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.boundary_id.strip()
            or not self.context_key.strip()
            or not self.source_id.strip()
        ):
            raise ValidationError("TAD boundary identifiers and context are required")
        if self.position < 1 or not isfinite(self.score):
            raise ValidationError("TAD boundary position and score are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TadBoundaryBatch:
    """Boundary candidates with malformed rows retained as issues."""

    source_id: str
    input_hash: str
    observations: tuple[TadBoundaryObservation, ...]
    issues: tuple[TopologyIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TadBoundaryParser:
    """Parse boundary candidates with the same source-accounting rules."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        assay: TopologyAssay | str,
        input_format: str | None = None,
    ) -> TadBoundaryBatch:
        if not source_id.strip():
            raise ValidationError("boundary source_id is required")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("boundary input must not be empty")
        selected = input_format or ("json" if text.lstrip().startswith(("{", "[")) else "tsv")
        if selected == "json":
            payload = json.loads(text)
            rows = payload.get("boundaries", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("boundary JSON must contain a boundaries list")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("boundary TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported boundary format: {selected}")
        values: list[TadBoundaryObservation] = []
        issues: list[TopologyIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(TopologyIssue("invalid_boundary_row", "row must be an object"))
                continue
            raw_hash = content_hash(row)
            try:
                values.append(
                    TadBoundaryObservation(
                        boundary_id=str(
                            self._value(row, "boundary_id", "id", default=f"{source_id}:{index}")
                        ),
                        assay=TopologyAssay(
                            str(self._value(row, "assay", "assay_type", default=str(assay)))
                        ),
                        chromosome=normalize_chromosome(
                            str(self._value(row, "chromosome", "chrom"))
                        ),
                        position=int(self._value(row, "position", "boundary_position")),
                        score=float(self._value(row, "score", "support", default=1.0)),
                        context_key=str(self._value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                        raw_hash=raw_hash,
                        caller_id=self._optional_text(row, "caller_id", "caller"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TopologyIssue(
                        "invalid_boundary_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "observations": tuple(values),
            "issues": tuple(issues),
        }
        return TadBoundaryBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            observations=tuple(values),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        if default is not None:
            return default
        raise ValidationError(f"boundary field is required: {names[0]}")

    @classmethod
    def _optional_text(cls, row: Mapping[str, Any], *names: str) -> str | None:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return str(value)
        return None


@dataclass(frozen=True, slots=True)
class BoundaryCluster:
    """Nearby boundary calls grouped without collapsing assay identities."""

    chromosome: str
    start_position: int
    end_position: int
    representative_position: int
    observation_ids: tuple[str, ...]
    assay_ids: tuple[str, ...]
    mean_score: float

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TadBoundaryEnsembleResult:
    """TAD boundary ensemble with explicit competing clusters."""

    chromosome: str
    region_start: int
    region_end: int
    context_key: str
    state: TopologyState
    representative_position: int | None
    clusters: tuple[BoundaryCluster, ...]
    agreement: float | None
    reason: str
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TadBoundaryEnsembleBuilder:
    """Build a tolerance-bounded boundary ensemble from caller observations."""

    def build(
        self,
        observations: Iterable[TadBoundaryObservation],
        *,
        chromosome: str,
        region_start: int,
        region_end: int,
        context: ReferenceContext,
        tolerance: int = 1000,
    ) -> TadBoundaryEnsembleResult:
        if region_start < 1 or region_end < region_start or tolerance < 0:
            raise ValidationError("TAD region or tolerance is invalid")
        chrom = normalize_chromosome(chromosome)
        all_rows = tuple(row for row in observations if row.chromosome == chrom)
        in_region = tuple(row for row in all_rows if region_start <= row.position <= region_end)
        matched = tuple(row for row in in_region if row.context_key == context.key)
        if not matched:
            state = TopologyState.OUT_OF_DOMAIN if in_region else TopologyState.ABSENT
            reason = (
                "boundary candidates are present only outside the target context"
                if in_region
                else "no boundary candidates overlap the requested region"
            )
            return self._result(
                chrom,
                region_start,
                region_end,
                context,
                state,
                None,
                (),
                None,
                reason,
                all_rows,
            )
        clusters: list[list[TadBoundaryObservation]] = []
        for row in sorted(matched, key=lambda item: item.position):
            if not clusters or row.position - clusters[-1][-1].position > tolerance:
                clusters.append([row])
            else:
                clusters[-1].append(row)
        cluster_values = tuple(
            BoundaryCluster(
                chromosome=chrom,
                start_position=min(row.position for row in cluster),
                end_position=max(row.position for row in cluster),
                representative_position=round(mean(row.position for row in cluster)),
                observation_ids=tuple(row.boundary_id for row in cluster),
                assay_ids=tuple(sorted({row.assay.value for row in cluster})),
                mean_score=round(mean(row.score for row in cluster), 9),
            )
            for cluster in clusters
        )
        best_size = max(len(cluster.observation_ids) for cluster in cluster_values)
        best = tuple(
            cluster for cluster in cluster_values if len(cluster.observation_ids) == best_size
        )
        if len(best) > 1:
            state = TopologyState.AMBIGUOUS
            representative = None
            agreement = round(best_size / len(matched), 9)
            reason = "multiple equally supported TAD boundary clusters remain"
        else:
            state = TopologyState.SUPPORTED if len(best[0].assay_ids) > 1 else TopologyState.PARTIAL
            representative = best[0].representative_position
            agreement = round(best_size / len(matched), 9)
            reason = "boundary cluster selected by declared tolerance and support count"
        return self._result(
            chrom,
            region_start,
            region_end,
            context,
            state,
            representative,
            cluster_values,
            agreement,
            reason,
            matched,
        )

    @staticmethod
    def _result(
        chromosome: str,
        region_start: int,
        region_end: int,
        context: ReferenceContext,
        state: TopologyState,
        representative: int | None,
        clusters: tuple[BoundaryCluster, ...],
        agreement: float | None,
        reason: str,
        rows: Iterable[TadBoundaryObservation],
    ) -> TadBoundaryEnsembleResult:
        values = tuple(rows)
        body = {
            "chromosome": chromosome,
            "region": (region_start, region_end),
            "context": context,
            "state": state,
            "representative": representative,
            "clusters": clusters,
        }
        return TadBoundaryEnsembleResult(
            chromosome=chromosome,
            region_start=region_start,
            region_end=region_end,
            context_key=context.key,
            state=state,
            representative_position=representative,
            clusters=clusters,
            agreement=agreement,
            reason=reason,
            source_ids=tuple(sorted({row.source_id for row in values})),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class InsulationScoreMeasurement:
    """Reference and alternate insulation measurements for one variant/window."""

    measurement_id: str
    variant_id: str
    context_key: str
    reference_score: float | None
    alternate_score: float | None
    source_id: str
    raw_hash: str
    replicate_count: int = 1

    def __post_init__(self) -> None:
        for name in (
            "measurement_id",
            "variant_id",
            "context_key",
            "source_id",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"insulation {name} is required")
        for name in ("reference_score", "alternate_score"):
            value = getattr(self, name)
            if value is not None and not isfinite(value):
                raise ValidationError(f"insulation {name} must be finite")
        if self.replicate_count < 1:
            raise ValidationError("insulation replicate_count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InsulationScoreDelta:
    """Measured insulation delta with missingness and baseline guards."""

    variant_id: str
    context_key: str
    state: TopologyState
    delta: float | None
    relative_delta: float | None
    direction: str
    replicate_count: int
    source_id: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class InsulationScoreDeltaEstimator:
    """Estimate alternate-minus-reference insulation scores."""

    def estimate(self, measurement: InsulationScoreMeasurement) -> InsulationScoreDelta:
        if measurement.reference_score is None or measurement.alternate_score is None:
            state = TopologyState.ABSTAINED
            delta = None
            relative = None
            direction = "unknown"
        else:
            delta = measurement.alternate_score - measurement.reference_score
            relative = (
                None
                if measurement.reference_score == 0
                else delta / abs(measurement.reference_score)
            )
            direction = "increase" if delta > 0 else "decrease" if delta < 0 else "unchanged"
            state = TopologyState.SUPPORTED
        body = {
            "measurement": measurement,
            "state": state,
            "delta": delta,
            "relative": relative,
            "direction": direction,
        }
        return InsulationScoreDelta(
            variant_id=measurement.variant_id,
            context_key=measurement.context_key,
            state=state,
            delta=None if delta is None else round(delta, 9),
            relative_delta=None if relative is None else round(relative, 9),
            direction=direction,
            replicate_count=measurement.replicate_count,
            source_id=measurement.source_id,
            limitations=(
                "Insulation delta is an assay-derived comparison, not a causal effect estimate.",
                "A missing or zero reference score prevents relative normalization.",
                "External benchmark, calibration, transport, and OOD evaluation remain required.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class TopologyEvidence:
    """Shared topology evidence envelope for downstream evidence builders."""

    evidence_id: str
    context_key: str
    state: TopologyState
    contact_query: ContactQueryResult | None
    qc: ContactMatrixQcReport | None
    boundary_ensemble: TadBoundaryEnsembleResult | None
    insulation_delta: InsulationScoreDelta | None
    source_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TopologyEvidenceBuilder:
    """Assemble topology components while preserving the most cautious state."""

    def build(
        self,
        evidence_id: str,
        context: ReferenceContext,
        *,
        contact_query: ContactQueryResult | None = None,
        qc: ContactMatrixQcReport | None = None,
        boundary_ensemble: TadBoundaryEnsembleResult | None = None,
        insulation_delta: InsulationScoreDelta | None = None,
    ) -> TopologyEvidence:
        components = tuple(
            item.state
            for item in (contact_query, boundary_ensemble, insulation_delta)
            if item is not None
        )
        if not components:
            state = TopologyState.ABSTAINED
        elif TopologyState.CONTRADICTORY in components:
            state = TopologyState.CONTRADICTORY
        elif TopologyState.OUT_OF_DOMAIN in components:
            state = TopologyState.OUT_OF_DOMAIN
        elif TopologyState.ABSTAINED in components:
            state = TopologyState.ABSTAINED
        elif TopologyState.AMBIGUOUS in components:
            state = TopologyState.AMBIGUOUS
        elif all(item == TopologyState.SUPPORTED for item in components):
            state = TopologyState.SUPPORTED
        else:
            state = TopologyState.PARTIAL
        sources: set[str] = set()
        for component in (contact_query, boundary_ensemble, insulation_delta):
            if component is not None:
                sources.update(
                    getattr(component, "source_ids", ())
                    or (
                        (getattr(component, "source_id", None),)
                        if getattr(component, "source_id", None)
                        else ()
                    )
                )
        body = {
            "evidence_id": evidence_id,
            "context": context,
            "state": state,
            "contact_query": contact_query,
            "qc": qc,
            "boundary_ensemble": boundary_ensemble,
            "insulation_delta": insulation_delta,
        }
        return TopologyEvidence(
            evidence_id=evidence_id,
            context_key=context.key,
            state=state,
            contact_query=contact_query,
            qc=qc,
            boundary_ensemble=boundary_ensemble,
            insulation_delta=insulation_delta,
            source_ids=tuple(sorted(sources)),
            limitations=(
                "Topology evidence records contact and boundary observations without "
                "asserting causality.",
                "A topology signal does not establish enhancer activity, target-gene "
                "linkage, or clinical actionability.",
            ),
            content_address=content_hash(body),
        )


__all__ = [
    "BoundaryCluster",
    "ContactMatrixBatch",
    "ContactMatrixNormalizer",
    "ContactMatrixParser",
    "ContactMatrixQcEvaluator",
    "ContactMatrixQcReport",
    "ContactQueryResult",
    "ContactRecord",
    "InsulationScoreDelta",
    "InsulationScoreDeltaEstimator",
    "InsulationScoreMeasurement",
    "NormalizedContact",
    "NormalizedContactMatrix",
    "TadBoundaryEnsembleBuilder",
    "TadBoundaryEnsembleResult",
    "TadBoundaryBatch",
    "TadBoundaryObservation",
    "TadBoundaryParser",
    "TopologyAssay",
    "TopologyEvidence",
    "TopologyEvidenceBuilder",
    "TopologyIssue",
    "TopologyState",
    "TopologyContactRetriever",
]
