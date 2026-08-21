"""Reference-coordinate extensions built on explicit assembly mappings.

The base reference registry resolves assembly names and projects a variant
through one supplied mapping segment. This module adds ingestion and
ambiguity-aware surfaces for chain-like tables and pangenome paths. It does
not download a chain file, claim that a mapping is biologically equivalent, or
choose among competing paths without evidence.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .reference_registry import (
    MappingCatalog,
    MappingSegment,
    ProjectionResult,
    ReferenceProjector,
    ReferenceRegistry,
)
from .serialization import content_hash, jsonable


class ReferenceExtensionState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ReferenceExtensionIssue:
    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = "Inspect the mapping source and route unresolved coordinates to review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LiftoverChainBatch:
    source_id: str
    input_hash: str
    segments: tuple[MappingSegment, ...]
    issues: tuple[ReferenceExtensionIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LiftoverChainManager:
    """Load explicit equal-length chain segments and project through them."""

    def __init__(self, registry: ReferenceRegistry) -> None:
        self.registry = registry
        self._segments: tuple[MappingSegment, ...] = ()

    def register(self, segments: Iterable[MappingSegment]) -> None:
        values = tuple(segments)
        if len({segment.mapping_id for segment in values}) != len(values):
            raise ValidationError("liftover mapping IDs must be unique")
        self._segments = values

    @property
    def catalog(self) -> MappingCatalog:
        return MappingCatalog(self._segments)

    def projector(self) -> ReferenceProjector:
        return ReferenceProjector(self.registry, self.catalog)

    def project(self, variant: Any, target_build: str) -> ProjectionResult:
        return self.projector().project(variant, target_build)

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_assembly: str,
        target_assembly: str,
    ) -> LiftoverChainBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("liftover chain input must not be empty")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("liftover chain TSV requires a header")
        segments: list[MappingSegment] = []
        issues: list[ReferenceExtensionIssue] = []
        for line_number, row in enumerate(reader, start=2):
            raw_hash = content_hash(row)
            try:
                source_chromosome = normalize_chromosome(
                    str(self._value(row, "source_chromosome", "source_chrom", "chrom"))
                )
                target_chromosome = normalize_chromosome(
                    str(self._value(row, "target_chromosome", "target_chrom", "chrom"))
                )
                source_start = int(self._value(row, "source_start", "start"))
                source_end = int(self._value(row, "source_end", "end"))
                target_start = int(self._value(row, "target_start"))
                target_end = int(self._value(row, "target_end"))
                segments.append(
                    MappingSegment(
                        mapping_id=str(
                            self._value(
                                row,
                                "mapping_id",
                                "id",
                                default=f"{source_id}:{line_number}",
                            )
                        ),
                        source_assembly=source_assembly,
                        source_chromosome=source_chromosome,
                        source_start=source_start,
                        source_end=source_end,
                        target_assembly=target_assembly,
                        target_chromosome=target_chromosome,
                        target_start=target_start,
                        target_end=target_end,
                        strand=str(self._value(row, "strand", default="+")),
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceExtensionIssue(
                        "invalid_liftover_segment",
                        str(exc),
                        line_number,
                        raw_hash,
                    )
                )
        self.register(segments)
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "segments": tuple(segments),
            "issues": tuple(issues),
        }
        return LiftoverChainBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            segments=tuple(segments),
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


@dataclass(frozen=True, slots=True)
class LiftoverAmbiguity:
    """A bounded score over candidate mapping segments."""

    state: ReferenceExtensionState
    candidate_mapping_ids: tuple[str, ...]
    score: float | None
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LiftoverAmbiguityScorer:
    """Report unique, absent, or competing mappings without forced choice."""

    def score(self, candidates: Iterable[MappingSegment]) -> LiftoverAmbiguity:
        values = tuple(candidates)
        ids = tuple(sorted(segment.mapping_id for segment in values))
        if not values:
            state = ReferenceExtensionState.ABSTAINED
            score = None
            reason = "no mapping segment contains the complete requested interval"
        elif len(values) == 1:
            state = ReferenceExtensionState.SUPPORTED
            score = 1.0
            reason = "exactly one explicit mapping segment contains the interval"
        else:
            state = ReferenceExtensionState.AMBIGUOUS
            score = round(1.0 / len(values), 6)
            reason = "multiple explicit mapping segments compete for the interval"
        body = {"mapping_ids": ids, "state": state, "score": score, "reason": reason}
        return LiftoverAmbiguity(
            state=state,
            candidate_mapping_ids=ids,
            score=score,
            reason=reason,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class PangenomePath:
    """One declared path interval in a pangenome coordinate system."""

    path_id: str
    path_name: str
    chromosome: str
    start: int
    end: int
    strand: str
    sequence_id: str
    source_id: str
    version: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "path_id",
            "path_name",
            "chromosome",
            "sequence_id",
            "source_id",
            "version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"pangenome path {name} is required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("pangenome path interval is invalid")
        if self.strand not in {"+", "-"}:
            raise ValidationError("pangenome path strand must be + or -")

    def contains(self, chromosome: str, start: int, end: int) -> bool:
        return (
            normalize_chromosome(self.chromosome) == normalize_chromosome(chromosome)
            and self.start <= start
            and end <= self.end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PangenomeCandidate:
    path_id: str
    path_name: str
    sequence_id: str
    chromosome: str
    start: int
    end: int
    strand: str
    source_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PangenomeMappingResult:
    chromosome: str
    start: int
    end: int
    candidates: tuple[PangenomeCandidate, ...]
    state: ReferenceExtensionState
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PangenomeCoordinateMapper:
    """Map a reference interval onto zero, one, or many declared paths."""

    def __init__(self, paths: Iterable[PangenomePath] = ()) -> None:
        self._paths = tuple(paths)
        if len({path.path_id for path in self._paths}) != len(self._paths):
            raise ValidationError("pangenome path IDs must be unique")

    def map_interval(
        self,
        chromosome: str,
        start: int,
        end: int,
    ) -> PangenomeMappingResult:
        if start < 1 or end < start:
            raise ValidationError("pangenome query interval is invalid")
        candidates = tuple(
            PangenomeCandidate(
                path_id=path.path_id,
                path_name=path.path_name,
                sequence_id=path.sequence_id,
                chromosome=path.chromosome,
                start=start,
                end=end,
                strand=path.strand,
                source_id=path.source_id,
                content_address=content_hash(
                    {"path_id": path.path_id, "chromosome": chromosome, "start": start, "end": end}
                ),
            )
            for path in self._paths
            if path.contains(chromosome, start, end)
        )
        if not candidates:
            state = ReferenceExtensionState.ABSTAINED
            reason = "no declared pangenome path contains the requested interval"
        elif len(candidates) == 1:
            state = ReferenceExtensionState.SUPPORTED
            reason = "exactly one declared pangenome path contains the interval"
        else:
            state = ReferenceExtensionState.AMBIGUOUS
            reason = "multiple declared pangenome paths contain the interval"
        body = {
            "chromosome": normalize_chromosome(chromosome),
            "start": start,
            "end": end,
            "candidates": candidates,
            "state": state,
        }
        return PangenomeMappingResult(
            chromosome=normalize_chromosome(chromosome),
            start=start,
            end=end,
            candidates=candidates,
            state=state,
            reason=reason,
            content_address=content_hash(body),
        )


__all__ = [
    "LiftoverAmbiguity",
    "LiftoverAmbiguityScorer",
    "LiftoverChainBatch",
    "LiftoverChainManager",
    "PangenomeCandidate",
    "PangenomeCoordinateMapper",
    "PangenomeMappingResult",
    "PangenomePath",
    "ReferenceExtensionIssue",
    "ReferenceExtensionState",
]
