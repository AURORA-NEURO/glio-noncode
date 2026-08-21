"""Lossless, bounded parsers for public regulatory interval tracks.

The parser accepts BED/BED-like, narrowPeak, GFF3, and JSON records.  It keeps
the coordinate convention explicit: BED input is zero-based half-open and is
converted to one-based closed intervals; GFF3 input is already one-based
closed.  Malformed rows are quarantined with line hashes and never become
candidate regulatory elements.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import unquote

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import CandidateElement, ReferenceContext
from .serialization import content_hash, jsonable


class RegulatoryTrackFormat(StrEnum):
    """Supported public interval encodings."""

    BED = "bed"
    NARROWPEAK = "narrowpeak"
    GFF3 = "gff3"
    JSON = "json"


class TrackIssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TrackIssue:
    """Line-addressable parse issue retained for review and replay."""

    code: str
    severity: TrackIssueSeverity
    message: str
    line_number: int | None = None
    raw_hash: str | None = None
    remediation: str = "Inspect the row and correct the source or route it to review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryFeature:
    """One normalized interval with source coordinates and parsed attributes."""

    feature_id: str
    chromosome: str
    start: int
    end: int
    feature_type: str
    source_id: str
    genome_build: str
    score: float | None = None
    strand: str = "."
    attributes: Mapping[str, Any] = field(default_factory=dict)
    source_line: int | None = None
    raw_hash: str = ""
    input_coordinate_system: str = "1-based-closed"

    def __post_init__(self) -> None:
        for name in (
            "feature_id",
            "chromosome",
            "feature_type",
            "source_id",
            "genome_build",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"regulatory feature {name} is required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("regulatory feature interval is invalid")
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValidationError("regulatory feature score must be between 0 and 1")
        if self.strand not in {"+", "-", ".", "?"}:
            raise ValidationError("regulatory feature strand must be +, -, ., or ?")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryTrackBatch:
    """Parsed features plus complete source accounting."""

    source_id: str
    input_format: RegulatoryTrackFormat
    genome_build: str
    input_hash: str
    header_hash: str
    features: tuple[RegulatoryFeature, ...]
    issues: tuple[TrackIssue, ...]
    content_address: str

    @property
    def errors(self) -> tuple[TrackIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == TrackIssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[TrackIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == TrackIssueSeverity.WARNING)

    def to_candidate_elements(
        self,
        context: ReferenceContext,
        *,
        target_gene_keys: tuple[str, ...] = ("gene", "gene_id", "gene_name", "target_gene"),
    ) -> tuple[CandidateElement, ...]:
        """Convert valid intervals into context-qualified candidates."""

        output: list[CandidateElement] = []
        for feature in self.features:
            genes: list[str] = []
            for key in target_gene_keys:
                value = feature.attributes.get(key)
                if value is None:
                    continue
                values = value if isinstance(value, (list, tuple)) else str(value).split(",")
                genes.extend(str(item).strip() for item in values if str(item).strip())
            genes = list(dict.fromkeys(genes))
            state_ids = tuple(
                str(item)
                for item in (
                    feature.attributes.get("cell_state"),
                    feature.attributes.get("state_id"),
                )
                if item is not None and str(item).strip()
            )
            if not genes and not state_ids:
                state_ids = ("unresolved_state",)
            features: dict[str, float] = {}
            if feature.score is not None:
                features["track_score"] = feature.score
            output.append(
                CandidateElement(
                    element_id=feature.feature_id,
                    chromosome=feature.chromosome,
                    start=feature.start,
                    end=feature.end,
                    element_type=feature.feature_type,
                    context=context,
                    source_id=feature.source_id,
                    target_genes=tuple(genes),
                    state_ids=tuple(dict.fromkeys(state_ids)),
                    features=features,
                    annotations={
                        "track_genome_build": feature.genome_build,
                        "track_coordinate_system": feature.input_coordinate_system,
                        "track_attributes": dict(feature.attributes),
                        "track_line": feature.source_line,
                        "track_raw_hash": feature.raw_hash,
                    },
                )
            )
        return tuple(output)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryTrackParser:
    """Parse interval tracks while preserving coordinates and anomalies."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        genome_build: str,
        input_format: RegulatoryTrackFormat | str | None = None,
    ) -> RegulatoryTrackBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("regulatory track text must not be empty")
        if not source_id.strip() or not genome_build.strip():
            raise ValidationError("source_id and genome_build are required")
        selected = self._select_format(text, input_format)
        if selected == RegulatoryTrackFormat.JSON:
            return self._parse_json(text, source_id, genome_build)
        if selected == RegulatoryTrackFormat.GFF3:
            return self._parse_gff3(text, source_id, genome_build)
        return self._parse_bed(text, source_id, genome_build, selected)

    @staticmethod
    def _select_format(
        text: str,
        input_format: RegulatoryTrackFormat | str | None,
    ) -> RegulatoryTrackFormat:
        if input_format is not None:
            try:
                return RegulatoryTrackFormat(str(input_format))
            except ValueError as exc:
                raise ValidationError(
                    f"unsupported regulatory track format: {input_format}"
                ) from exc
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first.startswith("##gff-version") or first.count("\t") >= 8:
            fields = first.split("\t")
            try:
                int(fields[1])
                int(fields[2])
                return (
                    RegulatoryTrackFormat.NARROWPEAK
                    if len(fields) >= 10
                    else RegulatoryTrackFormat.BED
                )
            except (IndexError, ValueError):
                return RegulatoryTrackFormat.GFF3
        if first.startswith("{") or first.startswith("["):
            return RegulatoryTrackFormat.JSON
        return RegulatoryTrackFormat.BED

    def _parse_bed(
        self,
        text: str,
        source_id: str,
        genome_build: str,
        input_format: RegulatoryTrackFormat,
    ) -> RegulatoryTrackBatch:
        features: list[RegulatoryFeature] = []
        issues: list[TrackIssue] = []
        headers: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            if line.startswith(("#", "track ", "browser ")):
                headers.append(line)
                continue
            raw_hash = content_hash(line)
            fields = line.split("\t")
            if len(fields) < 3:
                issues.append(
                    TrackIssue(
                        "invalid_bed_columns",
                        TrackIssueSeverity.ERROR,
                        "BED row requires at least chrom, start, and end columns.",
                        line_number,
                        raw_hash,
                    )
                )
                continue
            try:
                chromosome = normalize_chromosome(fields[0])
                start_zero = int(fields[1])
                end_exclusive = int(fields[2])
                if start_zero < 0 or end_exclusive <= start_zero:
                    raise ValueError("BED interval must satisfy 0 <= start < end")
                start = start_zero + 1
                end = end_exclusive
                feature_id = (
                    fields[3]
                    if len(fields) > 3 and fields[3] not in {"", "."}
                    else f"{source_id}:{line_number}"
                )
                score = self._bed_score(fields[4] if len(fields) > 4 else None)
                strand = fields[5] if len(fields) > 5 and fields[5] else "."
                attributes = self._bed_attributes(fields, input_format)
                features.append(
                    RegulatoryFeature(
                        feature_id=feature_id,
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        feature_type="peak"
                        if input_format == RegulatoryTrackFormat.NARROWPEAK
                        else "regulatory",
                        source_id=source_id,
                        genome_build=genome_build,
                        score=score,
                        strand=strand,
                        attributes=attributes,
                        source_line=line_number,
                        raw_hash=raw_hash,
                        input_coordinate_system="0-based-half-open",
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TrackIssue(
                        "invalid_bed_row",
                        TrackIssueSeverity.ERROR,
                        str(exc),
                        line_number,
                        raw_hash,
                    )
                )
        return self._finish(text, source_id, genome_build, input_format, headers, features, issues)

    def _parse_gff3(self, text: str, source_id: str, genome_build: str) -> RegulatoryTrackBatch:
        features: list[RegulatoryFeature] = []
        issues: list[TrackIssue] = []
        headers: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            if line.startswith("#"):
                headers.append(line)
                continue
            raw_hash = content_hash(line)
            fields = line.split("\t")
            if len(fields) != 9:
                issues.append(
                    TrackIssue(
                        "invalid_gff3_columns",
                        TrackIssueSeverity.ERROR,
                        "GFF3 row must contain exactly nine tab-separated columns.",
                        line_number,
                        raw_hash,
                    )
                )
                continue
            try:
                (
                    chromosome,
                    source,
                    feature_type,
                    start_text,
                    end_text,
                    score_text,
                    strand,
                    phase,
                    attributes_text,
                ) = fields
                start = int(start_text)
                end = int(end_text)
                if start < 1 or end < start:
                    raise ValueError("GFF3 interval must satisfy 1 <= start <= end")
                attributes = self._gff_attributes(attributes_text)
                feature_id = str(
                    attributes.get("ID") or attributes.get("Name") or f"{source_id}:{line_number}"
                )
                score = None if score_text in {"", "."} else self._bounded_score(float(score_text))
                if strand == "?":
                    strand = "."
                features.append(
                    RegulatoryFeature(
                        feature_id=feature_id,
                        chromosome=normalize_chromosome(chromosome),
                        start=start,
                        end=end,
                        feature_type=feature_type or "regulatory",
                        source_id=source_id,
                        genome_build=genome_build,
                        score=score,
                        strand=strand,
                        attributes={"source": source, "phase": phase, **attributes},
                        source_line=line_number,
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TrackIssue(
                        "invalid_gff3_row",
                        TrackIssueSeverity.ERROR,
                        str(exc),
                        line_number,
                        raw_hash,
                    )
                )
        return self._finish(
            text, source_id, genome_build, RegulatoryTrackFormat.GFF3, headers, features, issues
        )

    def _parse_json(self, text: str, source_id: str, genome_build: str) -> RegulatoryTrackBatch:
        features: list[RegulatoryFeature] = []
        issues: list[TrackIssue] = []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            issues.append(TrackIssue("invalid_json", TrackIssueSeverity.ERROR, str(exc)))
            return self._finish(
                text, source_id, genome_build, RegulatoryTrackFormat.JSON, (), features, issues
            )
        rows = payload.get("features") if isinstance(payload, Mapping) else payload
        if not isinstance(rows, list):
            issues.append(
                TrackIssue(
                    "invalid_json_shape",
                    TrackIssueSeverity.ERROR,
                    "regulatory JSON must be a list or an object with a features list.",
                )
            )
            return self._finish(
                text, source_id, genome_build, RegulatoryTrackFormat.JSON, (), features, issues
            )
        for line_number, raw in enumerate(rows, start=1):
            raw_hash = content_hash(raw)
            if not isinstance(raw, Mapping):
                issues.append(
                    TrackIssue(
                        "invalid_json_feature",
                        TrackIssueSeverity.ERROR,
                        "feature must be an object",
                        line_number,
                        raw_hash,
                    )
                )
                continue
            try:
                chromosome = normalize_chromosome(str(raw.get("chromosome", raw.get("chrom", ""))))
                start = int(raw.get("start", 0))
                end = int(raw.get("end", start))
                score_raw = raw.get("score")
                score = None if score_raw is None else self._bounded_score(float(score_raw))
                features.append(
                    RegulatoryFeature(
                        feature_id=str(
                            raw.get("feature_id", raw.get("id", f"{source_id}:{line_number}"))
                        ),
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        feature_type=str(raw.get("feature_type", raw.get("type", "regulatory"))),
                        source_id=source_id,
                        genome_build=genome_build,
                        score=score,
                        strand=str(raw.get("strand", ".")),
                        attributes=dict(raw.get("attributes", {})),
                        source_line=line_number,
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TrackIssue(
                        "invalid_json_feature",
                        TrackIssueSeverity.ERROR,
                        str(exc),
                        line_number,
                        raw_hash,
                    )
                )
        return self._finish(
            text, source_id, genome_build, RegulatoryTrackFormat.JSON, (), features, issues
        )

    @staticmethod
    def _bed_score(value: str | None) -> float | None:
        if value is None or value in {"", "."}:
            return None
        score = float(value)
        if score > 1.0:
            score /= 1000.0
        return RegulatoryTrackParser._bounded_score(score)

    @staticmethod
    def _bounded_score(value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("track score must be between 0 and 1 or a BED 0-1000 score")
        return round(value, 6)

    @staticmethod
    def _bed_attributes(fields: list[str], input_format: RegulatoryTrackFormat) -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        if len(fields) > 3 and fields[3] not in {"", "."}:
            attributes["Name"] = fields[3]
        if input_format == RegulatoryTrackFormat.NARROWPEAK:
            names = ("signal_value", "p_value", "q_value", "peak_offset")
            for name, raw in zip(names, fields[6:10], strict=False):
                if raw not in {"", "."}:
                    attributes[name] = float(raw)
        return attributes

    @staticmethod
    def _gff_attributes(value: str) -> dict[str, Any]:
        output: dict[str, Any] = {}
        if value in {"", "."}:
            return output
        for item in value.split(";"):
            if not item:
                continue
            key, separator, raw = item.partition("=")
            if not separator:
                output[unquote(key)] = True
                continue
            output[unquote(key)] = unquote(raw)
        return output

    @staticmethod
    def _finish(
        text: str,
        source_id: str,
        genome_build: str,
        input_format: RegulatoryTrackFormat,
        headers: Iterable[str],
        features: Iterable[RegulatoryFeature],
        issues: Iterable[TrackIssue],
    ) -> RegulatoryTrackBatch:
        feature_values = tuple(features)
        issue_values = tuple(issues)
        payload = {
            "source_id": source_id,
            "input_format": input_format,
            "genome_build": genome_build,
            "input_hash": content_hash(text),
            "header_hash": content_hash(tuple(headers)),
            "features": feature_values,
            "issues": issue_values,
        }
        return RegulatoryTrackBatch(
            source_id=source_id,
            input_format=input_format,
            genome_build=genome_build,
            input_hash=payload["input_hash"],
            header_hash=payload["header_hash"],
            features=feature_values,
            issues=issue_values,
            content_address=content_hash(payload),
        )
