"""Columnar interval indexes and context-lattice queries for public tracks.

This module is the shared, dependency-free indexing boundary for public
reference observations. It deliberately stores typed columns rather than a
list of mutable row dictionaries, keeps interval blocks addressable, and
separates coordinate overlap from context compatibility. The separation is
important: an overlapping interval from a different disease, age, cell state,
or treatment phase is out of domain, not a negative observation.

The index is designed for bounded local and offline use. It is not a
replacement for a distributed genomic database, a compressed interchange
format, or a clinical annotation service. Every build and query result is
content-addressed, and public payloads are filtered for direct identifiers,
attribution fields, and credential-like keys before they enter the index.
"""

from __future__ import annotations

import csv
import io
import json
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import ReferenceContext
from .serialization import content_hash, jsonable, require_non_empty


REFERENCE_INTERVAL_INDEX_VERSION = "reference-interval-index-v1"
REFERENCE_INTERVAL_INDEX_SCHEMA_VERSION = "reference-interval-index-schema-v1"
REFERENCE_INTERVAL_INDEX_MAX_RECORDS = 1_000_000
REFERENCE_INTERVAL_INDEX_MAX_QUERY_LIMIT = 5_000
REFERENCE_INTERVAL_INDEX_BLOCK_SIZE = 256
REFERENCE_INTERVAL_INDEX_MAX_ISSUES = 10_000
REFERENCE_CONTEXT_DIMENSIONS = (
    "genome_build",
    "disease_class",
    "age_group",
    "cell_state",
    "territory",
    "treatment_phase",
)
REFERENCE_CONTEXT_WILDCARDS = frozenset({"*", "all", "unknown"})
REFERENCE_CONTEXT_QUERY_WILDCARDS = frozenset({"*"})
REFERENCE_CONTEXT_GENERALIZATIONS = frozenset({"*", "all", "unknown"})

_PUBLIC_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "primary_agent",
        "programming_language",
        "produced_by",
        "sample_id",
        "secret",
        "secret_key",
        "subject_id",
        "token",
    }
)


class ReferenceIndexIssueSeverity(StrEnum):
    """Severity for an index-build or query-boundary issue."""

    WARNING = "warning"
    ERROR = "error"


class ReferenceIndexQueryState(StrEnum):
    """Coordinate and context result states."""

    SUPPORTED = "supported"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    AMBIGUOUS = "ambiguous"
    TRUNCATED = "truncated"
    INVALID = "invalid"


class ContextQueryMode(StrEnum):
    """Context matching policies."""

    EXACT = "exact"
    LATTICE = "lattice"


def _public_projection(value: Any) -> Any:
    """Recursively remove public-boundary keys from supplied payloads."""

    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if str(key).casefold() not in _PUBLIC_FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _context_parts(context_key: str) -> tuple[str, ...]:
    values = tuple(str(item).strip() for item in context_key.split("|"))
    if len(values) != len(REFERENCE_CONTEXT_DIMENSIONS) or any(not item for item in values):
        raise ValidationError(
            "context_key must contain six non-empty pipe-delimited dimensions: "
            "genome_build|disease_class|age_group|cell_state|territory|treatment_phase"
        )
    return values


def _context_from_key(context_key: str) -> tuple[str, ...]:
    """Validate a stored context key, including explicit generalized values."""

    return _context_parts(context_key)


@dataclass(frozen=True, slots=True)
class LatticeContext:
    """A six-axis context pattern; wildcard values are query patterns."""

    genome_build: str
    disease_class: str
    age_group: str
    cell_state: str
    territory: str
    treatment_phase: str

    def __post_init__(self) -> None:
        for name in REFERENCE_CONTEXT_DIMENSIONS:
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValidationError(f"lattice context {name} must not be empty")
            object.__setattr__(self, name, value)

    @classmethod
    def from_key(cls, context_key: str) -> "LatticeContext":
        return cls(*_context_parts(context_key))

    @classmethod
    def from_context(cls, context: ReferenceContext) -> "LatticeContext":
        return cls(*(_context_value(context, name) for name in REFERENCE_CONTEXT_DIMENSIONS))

    @property
    def key(self) -> str:
        return "|".join(str(getattr(self, name)) for name in REFERENCE_CONTEXT_DIMENSIONS)

    @property
    def constrained_dimensions(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in REFERENCE_CONTEXT_DIMENSIONS
            if str(getattr(self, name)).casefold() not in REFERENCE_CONTEXT_QUERY_WILDCARDS
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "key": self.key,
            "constrained_dimensions": self.constrained_dimensions,
        }


def _context_value(context: ReferenceContext, name: str) -> str:
    return str(getattr(context, name))


def _lattice_context_from_mapping(raw: Mapping[str, Any]) -> LatticeContext:
    """Parse a query or generalized row mapping without losing wildcard values."""

    return LatticeContext(
        genome_build=str(raw.get("genome_build", "")),
        disease_class=str(raw.get("disease_class", "")),
        age_group=str(raw.get("age_group", "")),
        cell_state=str(raw.get("cell_state", "")),
        territory=str(raw.get("territory", "unknown")),
        treatment_phase=str(raw.get("treatment_phase", "unknown")),
    )


@dataclass(frozen=True, slots=True)
class ContextMatch:
    """Compatibility result between one indexed context and one query pattern."""

    accepted: bool
    specificity: int
    constrained_dimensions: int
    exact_dimensions: tuple[str, ...]
    generalized_dimensions: tuple[str, ...]
    rejected_dimensions: tuple[str, ...]
    score: float
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def match_context(
    record_context_key: str,
    query_context: LatticeContext | ReferenceContext | str,
    *,
    mode: ContextQueryMode | str = ContextQueryMode.LATTICE,
) -> ContextMatch:
    """Evaluate exact or general-to-specific compatibility without transport."""

    selected_mode = ContextQueryMode(str(mode))
    record = LatticeContext.from_key(record_context_key)
    query = (
        query_context
        if isinstance(query_context, LatticeContext)
        else LatticeContext.from_context(query_context)
        if isinstance(query_context, ReferenceContext)
        else LatticeContext.from_key(str(query_context))
    )
    exact: list[str] = []
    generalized: list[str] = []
    rejected: list[str] = []
    constrained = 0
    for name in REFERENCE_CONTEXT_DIMENSIONS:
        record_value = str(getattr(record, name))
        query_value = str(getattr(query, name))
        query_wildcard = query_value.casefold() in REFERENCE_CONTEXT_QUERY_WILDCARDS
        if not query_wildcard:
            constrained += 1
        if query_wildcard:
            continue
        if record_value == query_value:
            exact.append(name)
            continue
        if (
            selected_mode is ContextQueryMode.LATTICE
            and record_value.casefold() in REFERENCE_CONTEXT_GENERALIZATIONS
            and name != "genome_build"
        ):
            generalized.append(name)
            continue
        rejected.append(name)
    accepted = not rejected and (selected_mode is ContextQueryMode.LATTICE or not generalized)
    specificity = len(exact)
    score = specificity / constrained if constrained else 1.0
    if not accepted:
        reason = "record context conflicts with the declared query context"
    elif generalized:
        reason = "record is compatible through explicitly generalized lattice dimensions"
    else:
        reason = "record context exactly matches the declared query context"
    body = {
        "record_context_key": record_context_key,
        "query_context_key": query.key,
        "mode": selected_mode,
        "accepted": accepted,
        "specificity": specificity,
        "constrained_dimensions": constrained,
        "exact_dimensions": exact,
        "generalized_dimensions": generalized,
        "rejected_dimensions": rejected,
        "score": score,
        "reason": reason,
    }
    return ContextMatch(
        accepted=accepted,
        specificity=specificity,
        constrained_dimensions=constrained,
        exact_dimensions=tuple(exact),
        generalized_dimensions=tuple(generalized),
        rejected_dimensions=tuple(rejected),
        score=round(score, 6),
        reason=reason,
        content_address=content_hash(body, prefix="context-match"),
    )


@dataclass(frozen=True, slots=True)
class PublicReferenceRecord:
    """One public interval row normalized for columnar storage."""

    record_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    source_id: str
    track_type: str
    state: str
    payload: Mapping[str, Any]
    tags: tuple[str, ...] = ()
    raw_hash: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "source_id", "track_type", "state"):
            require_non_empty(str(getattr(self, name)), name)
        chromosome = normalize_chromosome(self.chromosome)
        object.__setattr__(self, "chromosome", chromosome)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("reference interval must satisfy 1 <= start <= end")
        _context_from_key(self.context_key)
        tags = tuple(sorted({str(tag).strip() for tag in self.tags if str(tag).strip()}))
        object.__setattr__(self, "tags", tags)
        safe_payload = _public_projection(dict(self.payload))
        if not isinstance(safe_payload, Mapping):
            raise ValidationError("reference payload must be a mapping")
        object.__setattr__(self, "payload", dict(safe_payload))
        body = self.body()
        raw_hash = self.raw_hash or content_hash(body, prefix="reference-row")
        object.__setattr__(self, "raw_hash", raw_hash)
        expected = content_hash(body | {"raw_hash": raw_hash}, prefix="reference-row")
        if self.content_address and self.content_address != expected:
            raise ValidationError("reference row content_address does not match its body")
        object.__setattr__(self, "content_address", expected)

    @classmethod
    def from_mapping(
        cls,
        row: Mapping[str, Any],
        *,
        default_source_id: str = "reference-source",
        default_track_type: str = "reference",
        default_state: str = "supported",
    ) -> "PublicReferenceRecord":
        if not isinstance(row, Mapping):
            raise ValidationError("reference interval row must be an object")
        context_raw = row.get("context")
        if isinstance(context_raw, Mapping):
            context_key = _lattice_context_from_mapping(context_raw).key
        elif context_raw is not None:
            context_key = str(context_raw)
        else:
            context_key = str(row.get("context_key", ""))
        start = int(row.get("start", row.get("position", row.get("pos", 0))))
        end = int(row.get("end", start))
        record_id = str(row.get("record_id", row.get("id", "")))
        if not record_id:
            raise ValidationError("reference interval row requires record_id")
        reserved = {
            "record_id",
            "id",
            "chromosome",
            "chrom",
            "contig",
            "start",
            "position",
            "pos",
            "end",
            "context",
            "context_key",
            "source_id",
            "track_type",
            "state",
            "tags",
            "payload",
            "raw_hash",
            "content_address",
        }
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            payload = {str(key): value for key, value in row.items() if key not in reserved}
        tags_raw = row.get("tags", ())
        tags = (str(tags_raw),) if isinstance(tags_raw, str) else tuple(str(item) for item in tags_raw)
        return cls(
            record_id=record_id,
            chromosome=str(row.get("chromosome", row.get("chrom", row.get("contig", "")))),
            start=start,
            end=end,
            context_key=context_key,
            source_id=str(row.get("source_id", default_source_id)),
            track_type=str(row.get("track_type", default_track_type)),
            state=str(row.get("state", default_state)),
            payload=dict(payload),
            tags=tags,
            raw_hash=str(row.get("raw_hash", "")),
            content_address=str(row.get("content_address", "")),
        )

    def body(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "chromosome": self.chromosome,
            "start": self.start,
            "end": self.end,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "track_type": self.track_type,
            "state": self.state,
            "payload": self.payload,
            "tags": self.tags,
        }

    def overlaps(self, chromosome: str, start: int, end: int) -> bool:
        return (
            self.chromosome == normalize_chromosome(chromosome)
            and self.start <= end
            and self.end >= start
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"raw_hash": self.raw_hash, "content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class IntervalBlock:
    """A bounded row range and overlap summary inside one chromosome column."""

    first: int
    last: int
    minimum_start: int
    maximum_start: int
    maximum_end: int
    prefix_maximum_end: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ColumnarIntervalColumns:
    """Parallel immutable columns used by the interval index."""

    record_ids: tuple[str, ...]
    chromosomes: tuple[str, ...]
    starts: tuple[int, ...]
    ends: tuple[int, ...]
    context_keys: tuple[str, ...]
    source_ids: tuple[str, ...]
    track_types: tuple[str, ...]
    states: tuple[str, ...]
    payloads: tuple[Mapping[str, Any], ...]
    tags: tuple[tuple[str, ...], ...]
    raw_hashes: tuple[str, ...]
    content_addresses: tuple[str, ...]

    def __post_init__(self) -> None:
        lengths = {
            len(self.record_ids),
            len(self.chromosomes),
            len(self.starts),
            len(self.ends),
            len(self.context_keys),
            len(self.source_ids),
            len(self.track_types),
            len(self.states),
            len(self.payloads),
            len(self.tags),
            len(self.raw_hashes),
            len(self.content_addresses),
        }
        if len(lengths) != 1:
            raise ValidationError("columnar interval columns must all have the same length")

    @property
    def row_count(self) -> int:
        return len(self.record_ids)

    @classmethod
    def from_records(cls, records: Sequence[PublicReferenceRecord]) -> "ColumnarIntervalColumns":
        return cls(
            record_ids=tuple(record.record_id for record in records),
            chromosomes=tuple(record.chromosome for record in records),
            starts=tuple(record.start for record in records),
            ends=tuple(record.end for record in records),
            context_keys=tuple(record.context_key for record in records),
            source_ids=tuple(record.source_id for record in records),
            track_types=tuple(record.track_type for record in records),
            states=tuple(record.state for record in records),
            payloads=tuple(dict(record.payload) for record in records),
            tags=tuple(record.tags for record in records),
            raw_hashes=tuple(record.raw_hash for record in records),
            content_addresses=tuple(record.content_address for record in records),
        )

    def record_at(self, index: int) -> PublicReferenceRecord:
        if index < 0 or index >= self.row_count:
            raise IndexError("columnar interval row index is out of range")
        return PublicReferenceRecord(
            record_id=self.record_ids[index],
            chromosome=self.chromosomes[index],
            start=self.starts[index],
            end=self.ends[index],
            context_key=self.context_keys[index],
            source_id=self.source_ids[index],
            track_type=self.track_types[index],
            state=self.states[index],
            payload=self.payloads[index],
            tags=self.tags[index],
            raw_hash=self.raw_hashes[index],
            content_address=self.content_addresses[index],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ColumnarIntervalColumns":
        return cls(
            record_ids=tuple(str(item) for item in raw.get("record_ids", ())),
            chromosomes=tuple(str(item) for item in raw.get("chromosomes", ())),
            starts=tuple(int(item) for item in raw.get("starts", ())),
            ends=tuple(int(item) for item in raw.get("ends", ())),
            context_keys=tuple(str(item) for item in raw.get("context_keys", ())),
            source_ids=tuple(str(item) for item in raw.get("source_ids", ())),
            track_types=tuple(str(item) for item in raw.get("track_types", ())),
            states=tuple(str(item) for item in raw.get("states", ())),
            payloads=tuple(dict(item) for item in raw.get("payloads", ())),
            tags=tuple(tuple(str(tag) for tag in item) for item in raw.get("tags", ())),
            raw_hashes=tuple(str(item) for item in raw.get("raw_hashes", ())),
            content_addresses=tuple(str(item) for item in raw.get("content_addresses", ())),
        )


@dataclass(frozen=True, slots=True)
class ReferenceIntervalIndex:
    """Addressable sorted column store with per-contig block summaries."""

    index_id: str
    assembly: str
    columns: ColumnarIntervalColumns
    chromosome_ranges: Mapping[str, tuple[int, int]]
    blocks: Mapping[str, tuple[IntervalBlock, ...]]
    context_counts: Mapping[str, int]
    track_counts: Mapping[str, int]
    source_counts: Mapping[str, int]
    block_size: int = REFERENCE_INTERVAL_INDEX_BLOCK_SIZE
    version: str = REFERENCE_INTERVAL_INDEX_VERSION
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.index_id, "index_id")
        require_non_empty(self.assembly, "assembly")
        if len(self.columns.chromosomes) > REFERENCE_INTERVAL_INDEX_MAX_RECORDS:
            raise ValidationError("reference interval index exceeds the record ceiling")
        if self.block_size < 1 or self.block_size > 4096:
            raise ValidationError("reference interval index block_size must be between 1 and 4096")
        ranges = {str(key): tuple(value) for key, value in self.chromosome_ranges.items()}
        for chromosome, (first, last) in ranges.items():
            if first < 0 or last < first or last > self.columns.row_count:
                raise ValidationError(f"invalid chromosome range for {chromosome}")
        object.__setattr__(self, "chromosome_ranges", ranges)
        expected = content_hash(self.body(), prefix="reference-index")
        if self.content_address and self.content_address != expected:
            raise ValidationError("reference interval index content address does not match body")
        object.__setattr__(self, "content_address", expected)

    @property
    def record_count(self) -> int:
        return self.columns.row_count

    @property
    def chromosome_count(self) -> int:
        return len(self.chromosome_ranges)

    @classmethod
    def build(
        cls,
        records: Iterable[PublicReferenceRecord],
        *,
        index_id: str,
        assembly: str,
        block_size: int = REFERENCE_INTERVAL_INDEX_BLOCK_SIZE,
    ) -> "ReferenceIntervalIndex":
        if block_size < 1 or block_size > 4096:
            raise ValidationError("block_size must be between 1 and 4096")
        selected = tuple(
            sorted(
                records,
                key=lambda row: (
                    row.chromosome,
                    row.start,
                    row.end,
                    row.record_id,
                    row.source_id,
                    row.context_key,
                ),
            )
        )
        if len(selected) > REFERENCE_INTERVAL_INDEX_MAX_RECORDS:
            raise ValidationError("reference interval index exceeds the record ceiling")
        columns = ColumnarIntervalColumns.from_records(selected)
        ranges: dict[str, tuple[int, int]] = {}
        blocks: dict[str, tuple[IntervalBlock, ...]] = {}
        cursor = 0
        while cursor < columns.row_count:
            chromosome = columns.chromosomes[cursor]
            first = cursor
            while cursor < columns.row_count and columns.chromosomes[cursor] == chromosome:
                cursor += 1
            ranges[chromosome] = (first, cursor)
            chromosome_blocks: list[IntervalBlock] = []
            prefix_max_end = 0
            for block_first in range(first, cursor, block_size):
                block_last = min(block_first + block_size, cursor)
                minimum_start = min(columns.starts[block_first:block_last])
                maximum_start = max(columns.starts[block_first:block_last])
                maximum_end = max(columns.ends[block_first:block_last])
                prefix_max_end = max(prefix_max_end, maximum_end)
                block_body = {
                    "first": block_first,
                    "last": block_last,
                    "minimum_start": minimum_start,
                    "maximum_start": maximum_start,
                    "maximum_end": maximum_end,
                    "prefix_maximum_end": prefix_max_end,
                }
                chromosome_blocks.append(
                    IntervalBlock(
                        first=block_first,
                        last=block_last,
                        minimum_start=minimum_start,
                        maximum_start=maximum_start,
                        maximum_end=maximum_end,
                        prefix_maximum_end=prefix_max_end,
                        content_address=content_hash(block_body, prefix="reference-index-block"),
                    )
                )
            blocks[chromosome] = tuple(chromosome_blocks)
        context_counts = Counter(columns.context_keys)
        track_counts = Counter(columns.track_types)
        source_counts = Counter(columns.source_ids)
        return cls(
            index_id=index_id,
            assembly=assembly,
            columns=columns,
            chromosome_ranges=ranges,
            blocks=blocks,
            context_counts=dict(sorted(context_counts.items())),
            track_counts=dict(sorted(track_counts.items())),
            source_counts=dict(sorted(source_counts.items())),
            block_size=block_size,
        )

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "index_id": self.index_id,
            "assembly": self.assembly,
            "columns": self.columns,
            "chromosome_ranges": self.chromosome_ranges,
            "blocks": self.blocks,
            "context_counts": self.context_counts,
            "track_counts": self.track_counts,
            "source_counts": self.source_counts,
            "block_size": self.block_size,
        }

    def record_at(self, index: int) -> PublicReferenceRecord:
        return self.columns.record_at(index)

    def candidate_indices(self, chromosome: str, start: int, end: int) -> tuple[int, ...]:
        """Use contig blocks and prefix maxima before checking exact overlap."""

        normalized = normalize_chromosome(chromosome)
        if start < 1 or end < start:
            raise ValidationError("interval query must satisfy 1 <= start <= end")
        if normalized not in self.chromosome_ranges:
            return ()
        blocks = self.blocks.get(normalized, ())
        if not blocks:
            return ()
        prefix_ends = tuple(block.prefix_maximum_end for block in blocks)
        first_block = bisect_left(prefix_ends, start)
        block_starts = tuple(block.minimum_start for block in blocks)
        last_block = bisect_right(block_starts, end)
        candidates: list[int] = []
        for block in blocks[first_block:last_block]:
            if block.maximum_end < start or block.minimum_start > end:
                continue
            candidates.extend(
                index
                for index in range(block.first, block.last)
                if self.columns.starts[index] <= end and self.columns.ends[index] >= start
            )
        return tuple(candidates)

    def query(self, query: "ReferenceIndexQuery") -> "ReferenceIndexQueryReport":
        """Execute coordinate, track, source, state, and context-lattice filters."""

        candidate_indices = self.candidate_indices(query.chromosome, query.start, query.end)
        interval_candidate_count = len(candidate_indices)
        matches: list[ReferenceIndexMatch] = []
        context_rejected = 0
        filter_rejected = 0
        for index in candidate_indices:
            record = self.record_at(index)
            if query.track_types and record.track_type not in query.track_types:
                filter_rejected += 1
                continue
            if query.source_ids and record.source_id not in query.source_ids:
                filter_rejected += 1
                continue
            if query.states and record.state not in query.states:
                filter_rejected += 1
                continue
            context_match = match_context(record.context_key, query.context, mode=query.mode)
            if not context_match.accepted:
                context_rejected += 1
                continue
            overlap_start = max(record.start, query.start)
            overlap_end = min(record.end, query.end)
            matches.append(
                ReferenceIndexMatch(
                    record=record,
                    overlap_bp=overlap_end - overlap_start + 1,
                    context_score=context_match.score,
                    specificity=context_match.specificity,
                    generalized_dimensions=context_match.generalized_dimensions,
                    context_reason=context_match.reason,
                    source_row=index,
                    content_address="",
                )
            )
        ordered = tuple(
            sorted(
                matches,
                key=lambda item: (
                    -item.specificity,
                    -item.context_score,
                    -item.overlap_bp,
                    item.record.chromosome,
                    item.record.start,
                    item.record.end,
                    item.record.record_id,
                    item.record.source_id,
                ),
            )
        )
        addressed = tuple(
            replace(
                match,
                rank=index + 1,
                content_address=content_hash(
                    {
                        "index_id": self.index_id,
                        "query": query,
                        "record": match.record,
                        "overlap_bp": match.overlap_bp,
                        "context_score": match.context_score,
                        "specificity": match.specificity,
                        "generalized_dimensions": match.generalized_dimensions,
                        "source_row": match.source_row,
                    },
                    prefix="reference-index-match",
                ),
            )
            for index, match in enumerate(ordered)
        )
        selected = addressed[query.offset : query.offset + query.limit]
        truncated = query.offset + query.limit < len(addressed)
        if selected:
            state = (
                ReferenceIndexQueryState.TRUNCATED
                if truncated
                else ReferenceIndexQueryState.SUPPORTED
            )
        elif interval_candidate_count == 0:
            state = ReferenceIndexQueryState.ABSENT
        elif context_rejected:
            state = ReferenceIndexQueryState.OUT_OF_DOMAIN
        else:
            state = ReferenceIndexQueryState.ABSENT
        warnings: list[str] = []
        if context_rejected:
            warnings.append(
                "overlapping rows from incompatible context were excluded; exclusion is not a negative measurement"
            )
        if truncated:
            warnings.append("query result was bounded by offset and limit")
        body = {
            "version": REFERENCE_INTERVAL_INDEX_VERSION,
            "index_id": self.index_id,
            "query": query,
            "state": state,
            "matches": selected,
            "interval_candidate_count": interval_candidate_count,
            "rows_scanned": interval_candidate_count,
            "context_rejected_count": context_rejected,
            "filter_rejected_count": filter_rejected,
            "total_match_count": len(addressed),
            "offset": query.offset,
            "limit": query.limit,
            "truncated": truncated,
            "warnings": warnings,
        }
        return ReferenceIndexQueryReport(
            version=REFERENCE_INTERVAL_INDEX_VERSION,
            index_id=self.index_id,
            query=query,
            state=state,
            matches=selected,
            interval_candidate_count=interval_candidate_count,
            rows_scanned=interval_candidate_count,
            context_rejected_count=context_rejected,
            filter_rejected_count=filter_rejected,
            total_match_count=len(addressed),
            offset=query.offset,
            limit=query.limit,
            truncated=truncated,
            warnings=tuple(warnings),
            content_address=content_hash(body, prefix="reference-index-query"),
        )

    def context_lattice_summary(self) -> dict[str, Any]:
        """Describe available context levels without returning interval payloads."""

        levels: Counter[int] = Counter()
        by_dimension: dict[str, Counter[str]] = {
            name: Counter() for name in REFERENCE_CONTEXT_DIMENSIONS
        }
        for key, count in self.context_counts.items():
            context = LatticeContext.from_key(key)
            specificity = sum(
                str(getattr(context, name)).casefold() not in REFERENCE_CONTEXT_GENERALIZATIONS
                for name in REFERENCE_CONTEXT_DIMENSIONS
            )
            levels[specificity] += count
            for name in REFERENCE_CONTEXT_DIMENSIONS:
                by_dimension[name][str(getattr(context, name))] += count
        body = {
            "index_id": self.index_id,
            "context_count": len(self.context_counts),
            "specificity_histogram": dict(sorted(levels.items())),
            "dimensions": {
                name: dict(sorted(values.items())) for name, values in by_dimension.items()
            },
        }
        return body | {"content_address": content_hash(body, prefix="reference-context-lattice")}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address})

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ReferenceIntervalIndex":
        columns = ColumnarIntervalColumns.from_dict(raw.get("columns", {}))
        blocks_raw = raw.get("blocks", {})
        blocks = {
            str(chromosome): tuple(
                IntervalBlock(
                    first=int(item["first"]),
                    last=int(item["last"]),
                    minimum_start=int(item["minimum_start"]),
                    maximum_start=int(item["maximum_start"]),
                    maximum_end=int(item["maximum_end"]),
                    prefix_maximum_end=int(item["prefix_maximum_end"]),
                    content_address=str(item["content_address"]),
                )
                for item in values
            )
            for chromosome, values in dict(blocks_raw).items()
        }
        index = cls(
            index_id=str(raw.get("index_id", "")),
            assembly=str(raw.get("assembly", "")),
            columns=columns,
            chromosome_ranges={
                str(key): (int(value[0]), int(value[1]))
                for key, value in dict(raw.get("chromosome_ranges", {})).items()
            },
            blocks=blocks,
            context_counts={
                str(key): int(value) for key, value in dict(raw.get("context_counts", {})).items()
            },
            track_counts={
                str(key): int(value) for key, value in dict(raw.get("track_counts", {})).items()
            },
            source_counts={
                str(key): int(value) for key, value in dict(raw.get("source_counts", {})).items()
            },
            block_size=int(raw.get("block_size", REFERENCE_INTERVAL_INDEX_BLOCK_SIZE)),
            version=str(raw.get("version", REFERENCE_INTERVAL_INDEX_VERSION)),
            content_address=str(raw.get("content_address", "")),
        )
        expected_blocks = cls.build(
            (index.record_at(row) for row in range(index.record_count)),
            index_id=index.index_id,
            assembly=index.assembly,
            block_size=index.block_size,
        )
        if expected_blocks.content_address != index.content_address:
            raise ValidationError(
                "reference interval index blocks or columns failed round-trip verification"
            )
        return index


@dataclass(frozen=True, slots=True)
class ReferenceIndexBuildIssue:
    """One row-level build issue."""

    code: str
    severity: ReferenceIndexIssueSeverity
    message: str
    row_number: int | None = None
    remediation: str = "Inspect the row and correct or route it explicitly."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceIndexBuildReport:
    """Bounded build receipt with the resulting index."""

    version: str
    index: ReferenceIntervalIndex
    row_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    error_count: int
    truncated: bool
    issues: tuple[ReferenceIndexBuildIssue, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return not self.truncated and self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_reference_interval_index(
    rows: Iterable[Mapping[str, Any] | PublicReferenceRecord],
    *,
    index_id: str = "reference-index",
    assembly: str = "GRCh38",
    max_records: int = REFERENCE_INTERVAL_INDEX_MAX_RECORDS,
    max_issues: int = REFERENCE_INTERVAL_INDEX_MAX_ISSUES,
    block_size: int = REFERENCE_INTERVAL_INDEX_BLOCK_SIZE,
) -> ReferenceIndexBuildReport:
    """Normalize public rows and build an addressed columnar interval index."""

    if isinstance(rows, (str, bytes, bytearray)):
        raise ValidationError("reference index rows must be an iterable of records")
    if max_records < 1 or max_records > REFERENCE_INTERVAL_INDEX_MAX_RECORDS:
        raise ValidationError("max_records is outside the reference index ceiling")
    if max_issues < 1 or max_issues > REFERENCE_INTERVAL_INDEX_MAX_ISSUES:
        raise ValidationError("max_issues is outside the reference index ceiling")
    accepted: list[PublicReferenceRecord] = []
    issues: list[ReferenceIndexBuildIssue] = []
    row_count = 0
    warning_count = 0
    error_count = 0
    truncated = False
    seen_ids: set[tuple[str, str]] = set()
    for row_number, raw in enumerate(rows, start=1):
        row_count += 1
        if row_count > max_records:
            truncated = True
            if row_count == max_records + 1:
                issue = ReferenceIndexBuildIssue(
                    "max_records_exceeded",
                    ReferenceIndexIssueSeverity.ERROR,
                    f"reference index record ceiling of {max_records} was exceeded",
                    row_number=row_number,
                    remediation="Increase the declared ceiling only after reviewing resource capacity.",
                )
                error_count += 1
                if len(issues) < max_issues:
                    issues.append(issue)
            continue
        try:
            record = (
                raw
                if isinstance(raw, PublicReferenceRecord)
                else PublicReferenceRecord.from_mapping(raw)
            )
            duplicate_key = (record.source_id, record.record_id)
            if duplicate_key in seen_ids:
                warning_count += 1
                issue = ReferenceIndexBuildIssue(
                    "duplicate_record",
                    ReferenceIndexIssueSeverity.WARNING,
                    f"duplicate record ignored: {record.source_id}:{record.record_id}",
                    row_number=row_number,
                    remediation="Retain one source row or assign a stable source-qualified record ID.",
                )
                if len(issues) < max_issues:
                    issues.append(issue)
                continue
            seen_ids.add(duplicate_key)
            accepted.append(record)
        except (TypeError, ValueError, ValidationError) as exc:
            error_count += 1
            issue = ReferenceIndexBuildIssue(
                "invalid_record",
                ReferenceIndexIssueSeverity.ERROR,
                str(exc),
                row_number=row_number,
            )
            if len(issues) < max_issues:
                issues.append(issue)
    index = ReferenceIntervalIndex.build(
        accepted,
        index_id=index_id,
        assembly=assembly,
        block_size=block_size,
    )
    body = {
        "version": REFERENCE_INTERVAL_INDEX_VERSION,
        "index": index,
        "row_count": row_count,
        "accepted_count": len(accepted),
        "rejected_count": row_count - len(accepted),
        "warning_count": warning_count,
        "error_count": error_count,
        "truncated": truncated,
        "issues": issues,
    }
    return ReferenceIndexBuildReport(
        version=REFERENCE_INTERVAL_INDEX_VERSION,
        index=index,
        row_count=row_count,
        accepted_count=len(accepted),
        rejected_count=row_count - len(accepted),
        warning_count=warning_count,
        error_count=error_count,
        truncated=truncated,
        issues=tuple(issues),
        content_address=content_hash(body, prefix="reference-index-build"),
    )


@dataclass(frozen=True, slots=True)
class ReferenceIndexQuery:
    """Bounded interval and context-lattice request."""

    chromosome: str
    start: int
    end: int
    context: LatticeContext
    mode: ContextQueryMode = ContextQueryMode.LATTICE
    track_types: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    states: tuple[str, ...] = ()
    offset: int = 0
    limit: int = 100

    def __post_init__(self) -> None:
        object.__setattr__(self, "chromosome", normalize_chromosome(self.chromosome))
        if self.start < 1 or self.end < self.start:
            raise ValidationError("reference index query interval must satisfy 1 <= start <= end")
        if self.offset < 0:
            raise ValidationError("reference index query offset must not be negative")
        if self.limit < 1 or self.limit > REFERENCE_INTERVAL_INDEX_MAX_QUERY_LIMIT:
            raise ValidationError(
                f"reference index query limit must be between 1 and {REFERENCE_INTERVAL_INDEX_MAX_QUERY_LIMIT}"
            )
        object.__setattr__(self, "mode", ContextQueryMode(str(self.mode)))
        object.__setattr__(self, "track_types", _unique_texts(self.track_types))
        object.__setattr__(self, "source_ids", _unique_texts(self.source_ids))
        object.__setattr__(self, "states", _unique_texts(self.states))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ReferenceIndexQuery":
        context = raw.get("context")
        if isinstance(context, Mapping):
            context_key = _lattice_context_from_mapping(context).key
        else:
            context_key = str(raw.get("context_key", context or ""))
        return cls(
            chromosome=str(raw.get("chromosome", raw.get("chrom", raw.get("contig", "")))),
            start=int(raw.get("start", raw.get("position", 0))),
            end=int(raw.get("end", raw.get("start", raw.get("position", 0)))),
            context=LatticeContext.from_key(context_key),
            mode=ContextQueryMode(str(raw.get("mode", ContextQueryMode.LATTICE.value))),
            track_types=_as_text_tuple(raw.get("track_types", raw.get("track_type", ()))),
            source_ids=_as_text_tuple(raw.get("source_ids", raw.get("source_id", ()))),
            states=_as_text_tuple(raw.get("states", raw.get("state", ()))),
            offset=int(raw.get("offset", 0)),
            limit=int(raw.get("limit", 100)),
        )

    @property
    def context_key(self) -> str:
        return self.context.key

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"context_key": self.context_key}


def _as_text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else tuple(value)
    return tuple(str(item) for item in values if str(item).strip())


def _unique_texts(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


@dataclass(frozen=True, slots=True)
class ReferenceIndexMatch:
    """One public record selected by an index query."""

    record: PublicReferenceRecord
    overlap_bp: int
    context_score: float
    specificity: int
    generalized_dimensions: tuple[str, ...]
    context_reason: str
    source_row: int
    rank: int = 0
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            body = {
                "record": self.record,
                "overlap_bp": self.overlap_bp,
                "context_score": self.context_score,
                "specificity": self.specificity,
                "generalized_dimensions": self.generalized_dimensions,
                "context_reason": self.context_reason,
                "source_row": self.source_row,
                "rank": self.rank,
            }
            object.__setattr__(
                self,
                "content_address",
                content_hash(body, prefix="reference-index-match"),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceIndexQueryReport:
    """Addressed query result with overlap and context rejection accounting."""

    version: str
    index_id: str
    query: ReferenceIndexQuery
    state: ReferenceIndexQueryState
    matches: tuple[ReferenceIndexMatch, ...]
    interval_candidate_count: int
    rows_scanned: int
    context_rejected_count: int
    filter_rejected_count: int
    total_match_count: int
    offset: int
    limit: int
    truncated: bool
    warnings: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state in {
            ReferenceIndexQueryState.SUPPORTED,
            ReferenceIndexQueryState.TRUNCATED,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def query_reference_interval_index(
    index: ReferenceIntervalIndex,
    query: ReferenceIndexQuery | Mapping[str, Any],
) -> ReferenceIndexQueryReport:
    """Execute a typed query against a previously verified index."""

    selected = (
        query if isinstance(query, ReferenceIndexQuery) else ReferenceIndexQuery.from_mapping(query)
    )
    return index.query(selected)


def load_reference_rows(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    """Load JSON, JSONL, TSV, or CSV public rows without fetching anything."""

    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".jsonl":
        rows: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValidationError(f"JSONL row {line_number} must be an object")
            rows.append(value)
        return tuple(rows)
    if suffix == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(value, Mapping):
            value = value.get("records", value.get("rows", ()))
        if not isinstance(value, list):
            raise ValidationError("JSON reference input must be a list or records/rows object")
        if not all(isinstance(row, Mapping) for row in value):
            raise ValidationError("JSON reference rows must be objects")
        return tuple(value)
    delimiter = "\t" if suffix in {".tsv", ".bed"} else ","
    reader = csv.DictReader(
        io.StringIO(source.read_text(encoding="utf-8")),
        delimiter=delimiter,
    )
    if not reader.fieldnames:
        raise ValidationError("delimited reference input requires a header")
    return tuple(dict(row) for row in reader)


def reference_interval_index_schema() -> dict[str, Any]:
    """Return the stable machine-readable index/query contract."""

    return {
        "version": REFERENCE_INTERVAL_INDEX_SCHEMA_VERSION,
        "index_version": REFERENCE_INTERVAL_INDEX_VERSION,
        "context_dimensions": list(REFERENCE_CONTEXT_DIMENSIONS),
        "context_wildcards": sorted(REFERENCE_CONTEXT_WILDCARDS),
        "query_modes": [item.value for item in ContextQueryMode],
        "query_states": [item.value for item in ReferenceIndexQueryState],
        "limits": {
            "max_records": REFERENCE_INTERVAL_INDEX_MAX_RECORDS,
            "max_query_limit": REFERENCE_INTERVAL_INDEX_MAX_QUERY_LIMIT,
            "default_block_size": REFERENCE_INTERVAL_INDEX_BLOCK_SIZE,
            "max_issues": REFERENCE_INTERVAL_INDEX_MAX_ISSUES,
        },
        "columns": [
            "record_ids",
            "chromosomes",
            "starts",
            "ends",
            "context_keys",
            "source_ids",
            "track_types",
            "states",
            "payloads",
            "tags",
            "raw_hashes",
            "content_addresses",
        ],
        "query_accounting": [
            "interval_candidate_count",
            "rows_scanned",
            "context_rejected_count",
            "filter_rejected_count",
            "total_match_count",
            "truncated",
        ],
        "public_boundary": [
            "payload keys are recursively filtered before indexing",
            "context incompatibility is visible as out_of_domain",
            "context generalization is explicit in generalized_dimensions",
            "content addresses describe the exact index or query projection",
        ],
    }


def reference_interval_index_capabilities() -> dict[str, Any]:
    """Describe the operational behavior of the index without source data."""

    return {
        "version": REFERENCE_INTERVAL_INDEX_VERSION,
        "storage": "sorted parallel columns with per-contig bounded blocks",
        "coordinate_semantics": "one-based inclusive intervals",
        "indexing": "contig range lookup, block pruning, then exact overlap filtering",
        "context": {
            "exact": "all six context dimensions must match",
            "lattice": "exact dimensions outrank explicit all/unknown/* generalizations",
            "genome_build": "never generalized across assemblies",
        },
        "source_policy": "rows retain source_id, state, raw_hash, tags, and public-safe payload",
        "query_states": [item.value for item in ReferenceIndexQueryState],
        "determinism": "sorting, columns, matches, and addresses are stable for equal inputs",
        "limits": reference_interval_index_schema()["limits"],
    }


__all__ = [
    "ContextMatch",
    "ContextQueryMode",
    "ColumnarIntervalColumns",
    "IntervalBlock",
    "LatticeContext",
    "PublicReferenceRecord",
    "REFERENCE_CONTEXT_DIMENSIONS",
    "REFERENCE_INTERVAL_INDEX_BLOCK_SIZE",
    "REFERENCE_INTERVAL_INDEX_MAX_RECORDS",
    "REFERENCE_INTERVAL_INDEX_MAX_QUERY_LIMIT",
    "REFERENCE_INTERVAL_INDEX_SCHEMA_VERSION",
    "REFERENCE_INTERVAL_INDEX_VERSION",
    "ReferenceIndexBuildIssue",
    "ReferenceIndexBuildReport",
    "ReferenceIndexIssueSeverity",
    "ReferenceIndexMatch",
    "ReferenceIndexQuery",
    "ReferenceIndexQueryReport",
    "ReferenceIndexQueryState",
    "ReferenceIntervalIndex",
    "build_reference_interval_index",
    "load_reference_rows",
    "match_context",
    "query_reference_interval_index",
    "reference_interval_index_capabilities",
    "reference_interval_index_schema",
]
