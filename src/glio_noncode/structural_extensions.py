"""Consensus and harmonization utilities for the Domain 02 structural plane.

The structural reconstructor handles one source of deferred VCF records. This
module handles the next boundary: multiple callers, multiple breakend events,
and copy-number segments that disagree at their edges or values. Every result
retains the contributing records and makes disagreement explicit. A consensus
is never treated as truth merely because one caller produced it.
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
from .serialization import content_hash, jsonable
from .variation import StructuralEvent


class StructuralEvidenceState(StrEnum):
    """State used when evidence from callers or segments is reconciled."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    ABSTAINED = "abstained"


class StructuralIssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StructuralExtensionIssue:
    """An addressable anomaly retained beside the structural result."""

    code: str
    severity: StructuralIssueSeverity
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    record_ids: tuple[str, ...] = ()
    remediation: str = "Inspect the source evidence and route unresolved cases to review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return default


def _float_score(value: Any, *, field_name: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc
    if score > 1.0 and score <= 100.0:
        score /= 100.0
    if not 0.0 <= score <= 1.0:
        raise ValidationError(f"{field_name} must be between 0 and 1 or 0 and 100")
    return score


def _canonical_kind(value: Any) -> str:
    normalized = str(value or "").strip().upper().strip("<>")
    aliases = {
        "BND": "BND",
        "BREAKEND": "BND",
        "DEL": "DEL",
        "DUP": "DUP",
        "INV": "INV",
        "CNV": "CNV",
        "TRA": "TRA",
        "TRANSLOCATION": "TRA",
    }
    if normalized not in aliases:
        raise ValidationError(f"unsupported structural event type: {value!r}")
    return aliases[normalized]


@dataclass(frozen=True, slots=True)
class SVCallerObservation:
    """One lossless, normalized observation from one SV caller."""

    observation_id: str
    caller_id: str
    caller_version: str
    source_id: str
    event_key: str
    chromosome: str
    start: int
    end: int
    event_type: str
    support: float
    raw_hash: str
    source_line: int | None = None
    copy_number: float | None = None
    alternate: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "caller_id",
            "source_id",
            "event_key",
            "chromosome",
            "caller_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"SV observation {name} is required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("SV observation interval is invalid")
        _canonical_kind(self.event_type)
        if not 0.0 <= self.support <= 1.0:
            raise ValidationError("SV observation support must be between 0 and 1")
        if self.copy_number is not None and self.copy_number < 0:
            raise ValidationError("SV copy number cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SVConsensusRecord:
    """One clustered event with caller support and breakpoint disagreement."""

    consensus_id: str
    event_key: str
    chromosome: str
    start: int
    end: int
    event_type: str
    caller_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    support: float
    breakpoint_disagreement_bp: int
    state: StructuralEvidenceState
    transformation_provenance: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not self.caller_ids or not self.observation_ids:
            raise ValidationError("SV consensus must retain callers and observations")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("SV consensus interval is invalid")
        if self.breakpoint_disagreement_bp < 0:
            raise ValidationError("breakpoint disagreement cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SVConsensusBatch:
    """Complete caller import with all observations, clusters, and anomalies."""

    source_id: str
    input_hash: str
    observations: tuple[SVCallerObservation, ...]
    consensus: tuple[SVConsensusRecord, ...]
    issues: tuple[StructuralExtensionIssue, ...]
    content_address: str

    @property
    def errors(self) -> tuple[StructuralExtensionIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == StructuralIssueSeverity.ERROR
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SVConsensusImporter:
    """Parse caller tables and cluster observations without silent arbitration."""

    def __init__(self, *, breakpoint_tolerance: int = 10) -> None:
        if breakpoint_tolerance < 0:
            raise ValidationError("breakpoint_tolerance cannot be negative")
        self.breakpoint_tolerance = breakpoint_tolerance

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        input_format: str | None = None,
    ) -> SVConsensusBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("SV caller input must not be empty")
        if not source_id.strip():
            raise ValidationError("source_id must not be empty")
        selected = input_format or self._detect_format(text)
        if selected == "json":
            rows = self._json_rows(text)
            observations, issues = self._parse_rows(rows, source_id, json_mode=True)
        elif selected == "tsv":
            observations, issues = self._parse_tsv(text, source_id)
        else:
            raise ValidationError(f"unsupported SV caller format: {selected}")
        return self._finish(text, source_id, observations, issues)

    @staticmethod
    def _detect_format(text: str) -> str:
        first = next(line.strip() for line in text.splitlines() if line.strip())
        return "json" if first.startswith("{") or first.startswith("[") else "tsv"

    @staticmethod
    def _json_rows(text: str) -> tuple[Mapping[str, Any], ...]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid SV caller JSON: {exc}") from exc
        rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
        if not isinstance(rows, list):
            raise ValidationError("SV caller JSON must contain an observations list")
        return tuple(row for row in rows if isinstance(row, Mapping))

    def _parse_tsv(
        self,
        text: str,
        source_id: str,
    ) -> tuple[tuple[SVCallerObservation, ...], tuple[StructuralExtensionIssue, ...]]:
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("SV caller TSV requires a header")
        return self._parse_rows(
            tuple(row for row in reader),
            source_id,
            json_mode=False,
            line_offset=2,
        )

    def _parse_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        source_id: str,
        *,
        json_mode: bool,
        line_offset: int = 1,
    ) -> tuple[tuple[SVCallerObservation, ...], tuple[StructuralExtensionIssue, ...]]:
        observations: list[SVCallerObservation] = []
        issues: list[StructuralExtensionIssue] = []
        for index, row in enumerate(rows, start=line_offset):
            raw_hash = content_hash(row)
            try:
                caller_id = str(_value(row, "caller_id", "caller", "tool"))
                caller_version = str(
                    _value(row, "caller_version", "version", default="unspecified")
                )
                event_id = str(_value(row, "event_id", "id", default=f"row-{index}"))
                chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom")))
                start = int(_value(row, "start", "position", "pos"))
                end = int(_value(row, "end", default=start))
                event_type = _canonical_kind(_value(row, "event_type", "svtype", "type"))
                support = _float_score(
                    _value(row, "support", "confidence", "score", default=1.0),
                    field_name="support",
                )
                copy_number_value = _value(row, "copy_number", "CN", default=None)
                copy_number = None if copy_number_value is None else float(copy_number_value)
                event_key = str(
                    _value(row, "event_key", "cluster_key", default="")
                    or f"{chromosome}:{start}:{end}:{event_type}"
                )
                observation = SVCallerObservation(
                    observation_id=f"{source_id}:{index}:{caller_id}:{event_id}",
                    caller_id=caller_id,
                    caller_version=caller_version,
                    source_id=source_id,
                    event_key=event_key,
                    chromosome=chromosome,
                    start=start,
                    end=end,
                    event_type=event_type,
                    support=support,
                    raw_hash=raw_hash,
                    source_line=None if json_mode else index,
                    copy_number=copy_number,
                    alternate=(str(_value(row, "alternate", "alt")) or None),
                    attributes={
                        str(key): value
                        for key, value in row.items()
                        if str(key)
                        not in {
                            "caller_id",
                            "caller",
                            "tool",
                            "caller_version",
                            "version",
                            "event_id",
                            "id",
                            "chromosome",
                            "chrom",
                            "start",
                            "position",
                            "pos",
                            "end",
                            "event_type",
                            "event_key",
                            "cluster_key",
                            "svtype",
                            "type",
                            "support",
                            "confidence",
                            "score",
                            "copy_number",
                            "CN",
                        }
                    },
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralExtensionIssue(
                        "invalid_sv_caller_row",
                        StructuralIssueSeverity.ERROR,
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                        remediation="Correct the row or quarantine it before consensus.",
                    )
                )
                continue
            observations.append(observation)
        return tuple(observations), tuple(issues)

    def _finish(
        self,
        text: str,
        source_id: str,
        observations: tuple[SVCallerObservation, ...],
        issues: tuple[StructuralExtensionIssue, ...],
    ) -> SVConsensusBatch:
        clusters: list[list[SVCallerObservation]] = []
        for observation in sorted(
            observations,
            key=lambda item: (
                item.chromosome,
                item.start,
                item.end,
                item.event_type,
                item.caller_id,
            ),
        ):
            selected: list[SVCallerObservation] | None = None
            for cluster in clusters:
                anchor = cluster[0]
                same_event_key = anchor.event_key == observation.event_key
                nearby_breakpoints = (
                    anchor.chromosome == observation.chromosome
                    and anchor.event_type == observation.event_type
                    and abs(int(median(item.start for item in cluster)) - observation.start)
                    <= self.breakpoint_tolerance
                    and abs(int(median(item.end for item in cluster)) - observation.end)
                    <= self.breakpoint_tolerance
                )
                if same_event_key or nearby_breakpoints:
                    selected = cluster
                    break
            if selected is None:
                clusters.append([observation])
            else:
                selected.append(observation)
        consensus = tuple(self._consensus(cluster) for cluster in clusters)
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "observations": observations,
            "consensus": consensus,
            "issues": issues,
        }
        return SVConsensusBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            observations=observations,
            consensus=consensus,
            issues=issues,
            content_address=content_hash(body),
        )

    def _consensus(self, cluster: list[SVCallerObservation]) -> SVConsensusRecord:
        callers = tuple(sorted({item.caller_id for item in cluster}))
        starts = tuple(item.start for item in cluster)
        ends = tuple(item.end for item in cluster)
        start = int(median(starts))
        end = int(median(ends))
        disagreement = max(max(starts) - min(starts), max(ends) - min(ends))
        state = (
            StructuralEvidenceState.SUPPORTED
            if len(callers) >= 2 and disagreement <= self.breakpoint_tolerance
            else StructuralEvidenceState.AMBIGUOUS
            if disagreement > self.breakpoint_tolerance
            else StructuralEvidenceState.PARTIAL
        )
        body = {
            "event_key": cluster[0].event_key,
            "observations": tuple(item.observation_id for item in cluster),
        }
        return SVConsensusRecord(
            consensus_id="svcons:" + content_hash(body).split(":", 1)[1][:24],
            event_key=body["event_key"],
            chromosome=cluster[0].chromosome,
            start=start,
            end=end,
            event_type=cluster[0].event_type,
            caller_ids=callers,
            observation_ids=tuple(sorted(item.observation_id for item in cluster)),
            support=round(sum(item.support for item in cluster) / len(cluster), 6),
            breakpoint_disagreement_bp=disagreement,
            state=state,
            transformation_provenance=(
                "clustered by chromosome, event type, and bounded breakpoint tolerance",
                "median breakpoint selected only as a reported consensus coordinate",
                "caller-level observations remain available for review",
            ),
            content_address=content_hash(body | {"state": state}),
        )


@dataclass(frozen=True, slots=True)
class ComplexPath:
    """One possible order through a connected structural component."""

    path_id: str
    event_ids: tuple[str, ...]
    breakpoint_nodes: tuple[str, ...]
    support: float
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ComplexResolution:
    """A connected component with alternatives and explicit ambiguity."""

    resolution_id: str
    event_ids: tuple[str, ...]
    paths: tuple[ComplexPath, ...]
    state: StructuralEvidenceState
    ambiguities: tuple[str, ...]
    provenance: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ComplexResolutionBatch:
    """All resolved components and structural graph issues."""

    resolutions: tuple[ComplexResolution, ...]
    issues: tuple[StructuralExtensionIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ComplexRearrangementResolver:
    """Resolve shared-breakpoint components without selecting an unsupported path."""

    def resolve(self, events: Iterable[StructuralEvent]) -> ComplexResolutionBatch:
        values = tuple(events)
        by_node: dict[str, set[str]] = defaultdict(set)
        event_nodes: dict[str, tuple[str, ...]] = {}
        issues: list[StructuralExtensionIssue] = []
        for event in values:
            nodes = tuple(
                sorted(
                    self._breakpoint_node(item.chromosome, item.position)
                    for item in event.breakends
                )
            )
            if not nodes:
                issues.append(
                    StructuralExtensionIssue(
                        "event_without_breakpoints",
                        StructuralIssueSeverity.WARNING,
                        "event has no explicit breakpoints and was not used in graph resolution",
                        record_ids=(event.event_id,),
                    )
                )
                continue
            event_nodes[event.event_id] = nodes
            for node in nodes:
                by_node[node].add(event.event_id)
        components = self._components(event_nodes, by_node)
        resolutions = tuple(
            self._resolution(component, event_nodes, by_node) for component in components
        )
        body = {"resolutions": resolutions, "issues": issues}
        return ComplexResolutionBatch(
            resolutions=resolutions,
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _breakpoint_node(chromosome: str, position: int) -> str:
        return f"{normalize_chromosome(chromosome)}:{position}"

    @staticmethod
    def _components(
        event_nodes: Mapping[str, tuple[str, ...]],
        by_node: Mapping[str, set[str]],
    ) -> tuple[tuple[str, ...], ...]:
        remaining = set(event_nodes)
        components: list[tuple[str, ...]] = []
        while remaining:
            seed = min(remaining)
            stack = [seed]
            found: set[str] = set()
            while stack:
                event_id = stack.pop()
                if event_id in found:
                    continue
                found.add(event_id)
                for node in event_nodes[event_id]:
                    stack.extend(by_node[node] - found)
            remaining -= found
            components.append(tuple(sorted(found)))
        return tuple(sorted(components))

    def _resolution(
        self,
        event_ids: tuple[str, ...],
        event_nodes: Mapping[str, tuple[str, ...]],
        by_node: Mapping[str, set[str]],
    ) -> ComplexResolution:
        nodes = tuple(sorted({node for event_id in event_ids for node in event_nodes[event_id]}))
        shared_nodes = tuple(node for node in nodes if len(by_node[node]) > 1)
        ambiguities: list[str] = []
        if len(event_ids) > 1 and shared_nodes:
            ambiguities.append("multiple events share breakpoint loci")
        if any(len(by_node[node]) > 2 for node in nodes):
            ambiguities.append("a breakpoint locus has more than two event attachments")
        state = (
            StructuralEvidenceState.AMBIGUOUS
            if ambiguities
            else StructuralEvidenceState.PARTIAL
        )
        path_body = {"events": event_ids, "nodes": nodes}
        path = ComplexPath(
            path_id="complex-path:" + content_hash(path_body).split(":", 1)[1][:20],
            event_ids=event_ids,
            breakpoint_nodes=nodes,
            support=0.5 if state == StructuralEvidenceState.PARTIAL else 0.0,
            explanation=(
                "Connected event order retained for review; no canonical rearrangement "
                "identity was inferred."
            ),
        )
        resolution_body = {"events": event_ids, "paths": (path,), "state": state}
        return ComplexResolution(
            resolution_id="complex:" + content_hash(resolution_body).split(":", 1)[1][:24],
            event_ids=event_ids,
            paths=(path,),
            state=state,
            ambiguities=tuple(ambiguities),
            provenance=(
                "breakpoint loci were normalized to chromosome:position nodes",
                "connected components were derived from shared loci",
                "prior event identities and source lineage remain immutable",
                "no supersession or canonical path was inferred",
            ),
            content_address=content_hash(resolution_body),
        )


@dataclass(frozen=True, slots=True)
class CopyNumberSegment:
    """One caller's one-based closed copy-number segment."""

    segment_id: str
    caller_id: str
    chromosome: str
    start: int
    end: int
    copy_number: float
    raw_hash: str
    source_id: str
    minor_copy_number: float | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.segment_id or not self.caller_id or not self.source_id or not self.raw_hash:
            raise ValidationError("copy-number segment identifiers and source are required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("copy-number segment interval is invalid")
        if self.copy_number < 0:
            raise ValidationError("copy number cannot be negative")
        if (
            self.minor_copy_number is not None
            and not 0 <= self.minor_copy_number <= self.copy_number
        ):
            raise ValidationError("minor copy number must be within total copy number")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HarmonizedSegment:
    """Atomic interval reconciled across active caller segments."""

    segment_id: str
    chromosome: str
    start: int
    end: int
    copy_number: float
    caller_ids: tuple[str, ...]
    source_segment_ids: tuple[str, ...]
    disagreement: float
    state: StructuralEvidenceState
    provenance: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CopyNumberHarmonization:
    """Content-addressed copy-number output with all source accounting."""

    segments: tuple[HarmonizedSegment, ...]
    issues: tuple[StructuralExtensionIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CopyNumberSegmentHarmonizer:
    """Sweep caller segments into atomic intervals and preserve disagreements."""

    def harmonize(
        self,
        segments: Iterable[CopyNumberSegment],
        *,
        value_tolerance: float = 0.25,
    ) -> CopyNumberHarmonization:
        if value_tolerance < 0:
            raise ValidationError("value_tolerance cannot be negative")
        values = tuple(segments)
        issues: list[StructuralExtensionIssue] = []
        output: list[HarmonizedSegment] = []
        chromosomes = sorted({normalize_chromosome(segment.chromosome) for segment in values})
        for chromosome in chromosomes:
            chrom_segments = tuple(
                segment
                for segment in values
                if normalize_chromosome(segment.chromosome) == chromosome
            )
            boundaries = sorted(
                {
                    boundary
                    for segment in chrom_segments
                    for boundary in (segment.start, segment.end + 1)
                }
            )
            for left, right_exclusive in zip(boundaries, boundaries[1:], strict=False):
                active = tuple(
                    segment
                    for segment in chrom_segments
                    if segment.start <= left and segment.end >= right_exclusive - 1
                )
                if not active:
                    continue
                values_for_interval = tuple(segment.copy_number for segment in active)
                consensus = float(median(values_for_interval))
                spread = max(values_for_interval) - min(values_for_interval)
                callers = tuple(sorted({segment.caller_id for segment in active}))
                state = (
                    StructuralEvidenceState.SUPPORTED
                    if len(callers) >= 2 and spread <= value_tolerance
                    else StructuralEvidenceState.AMBIGUOUS
                    if spread > value_tolerance
                    else StructuralEvidenceState.PARTIAL
                )
                disagreement = round(spread / max(consensus, 1.0), 6)
                body = {
                    "chromosome": chromosome,
                    "start": left,
                    "end": right_exclusive - 1,
                    "source_segment_ids": tuple(segment.segment_id for segment in active),
                    "copy_number": consensus,
                }
                output.append(
                    HarmonizedSegment(
                        segment_id="cn:" + content_hash(body).split(":", 1)[1][:24],
                        chromosome=chromosome,
                        start=left,
                        end=right_exclusive - 1,
                        copy_number=round(consensus, 6),
                        caller_ids=callers,
                        source_segment_ids=tuple(sorted(segment.segment_id for segment in active)),
                        disagreement=disagreement,
                        state=state,
                        provenance=(
                            "segments were split at every observed caller boundary",
                            "median total copy number is a reported consensus, not a truth label",
                            "caller disagreement remains visible in state and disagreement",
                        ),
                        content_address=content_hash(body | {"state": state}),
                    )
                )
        merged = self._merge_adjacent(output)
        body = {"segments": merged, "issues": issues}
        return CopyNumberHarmonization(
            segments=tuple(merged),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _merge_adjacent(segments: Iterable[HarmonizedSegment]) -> tuple[HarmonizedSegment, ...]:
        merged: list[HarmonizedSegment] = []
        for segment in sorted(segments, key=lambda item: (item.chromosome, item.start, item.end)):
            if (
                merged
                and merged[-1].chromosome == segment.chromosome
                and merged[-1].end + 1 == segment.start
                and merged[-1].copy_number == segment.copy_number
                and merged[-1].caller_ids == segment.caller_ids
                and merged[-1].state == segment.state
            ):
                previous = merged.pop()
                body = {
                    "chromosome": previous.chromosome,
                    "start": previous.start,
                    "end": segment.end,
                    "source_segment_ids": previous.source_segment_ids + segment.source_segment_ids,
                    "copy_number": previous.copy_number,
                }
                merged.append(
                    HarmonizedSegment(
                        segment_id="cn:" + content_hash(body).split(":", 1)[1][:24],
                        chromosome=previous.chromosome,
                        start=previous.start,
                        end=segment.end,
                        copy_number=previous.copy_number,
                        caller_ids=previous.caller_ids,
                        source_segment_ids=tuple(dict.fromkeys(body["source_segment_ids"])),
                        disagreement=max(previous.disagreement, segment.disagreement),
                        state=previous.state,
                        provenance=previous.provenance,
                        content_address=content_hash(body | {"state": previous.state}),
                    )
                )
            else:
                merged.append(segment)
        return tuple(merged)

    def parse_text(self, text: str, *, source_id: str) -> CopyNumberHarmonization:
        """Parse a caller segment TSV and immediately harmonize it."""

        if not isinstance(text, str) or not text.strip():
            raise ValidationError("copy-number segment input must not be empty")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("copy-number TSV requires a header")
        segments: list[CopyNumberSegment] = []
        issues: list[StructuralExtensionIssue] = []
        for line_number, row in enumerate(reader, start=2):
            raw_hash = content_hash(row)
            try:
                chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom")))
                start = int(_value(row, "start", "position"))
                end = int(_value(row, "end", default=start))
                segments.append(
                    CopyNumberSegment(
                        segment_id=str(
                            _value(row, "segment_id", "id", default=f"row-{line_number}")
                        ),
                        caller_id=str(_value(row, "caller_id", "caller")),
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        copy_number=float(_value(row, "copy_number", "CN", "total_cn")),
                        minor_copy_number=(
                            float(_value(row, "minor_copy_number", "minor_cn"))
                            if _value(row, "minor_copy_number", "minor_cn") is not None
                            else None
                        ),
                        raw_hash=raw_hash,
                        source_id=source_id,
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralExtensionIssue(
                        "invalid_copy_number_row",
                        StructuralIssueSeverity.ERROR,
                        str(exc),
                        source_line=line_number,
                        raw_hash=raw_hash,
                    )
                )
        result = self.harmonize(segments)
        if not issues:
            return result
        body = {"segments": result.segments, "issues": result.issues + tuple(issues)}
        return CopyNumberHarmonization(
            segments=result.segments,
            issues=result.issues + tuple(issues),
            content_address=content_hash(body),
        )


__all__ = [
    "ComplexPath",
    "ComplexRearrangementResolver",
    "ComplexResolution",
    "ComplexResolutionBatch",
    "CopyNumberHarmonization",
    "CopyNumberSegment",
    "CopyNumberSegmentHarmonizer",
    "HarmonizedSegment",
    "SVCallerObservation",
    "SVConsensusBatch",
    "SVConsensusImporter",
    "SVConsensusRecord",
    "StructuralEvidenceState",
    "StructuralExtensionIssue",
    "StructuralIssueSeverity",
]
