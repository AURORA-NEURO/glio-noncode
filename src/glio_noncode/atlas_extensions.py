"""Context-gated cCRE ingestion and atlas query surfaces.

This module is a data boundary for ENCODE SCREEN-shaped cCRE records and
context-qualified local atlas snapshots. It does not infer regulatory
activity from an interval overlap, and it never converts an absent or
out-of-domain record into a biological negative.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import ReferenceContext
from .serialization import content_hash, jsonable


class CcreAtlasProfile(StrEnum):
    ENCODE_SCREEN = "encode_screen_ccre"
    BRAIN_CELL = "brain_cell_type_ccre"
    ADULT_GLIO = "adult_glioma_regulatory"
    PEDIATRIC_GLIO = "pediatric_glioma_regulatory"


class CcreQueryState(StrEnum):
    SUPPORTED = "supported"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class CcreIssue:
    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = "Inspect the source record and route malformed data to review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CcreRecord:
    """One cCRE interval with source registry and context metadata."""

    ccre_id: str
    chromosome: str
    start: int
    end: int
    profile: CcreAtlasProfile
    source_id: str
    source_version: str
    raw_hash: str
    registry_class: str | None = None
    score: float | None = None
    cell_state: str | None = None
    disease_class: str | None = None
    age_group: str | None = None
    strand: str = "."
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "ccre_id",
            "chromosome",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"cCRE {name} is required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("cCRE interval is invalid")
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValidationError("cCRE score must be between 0 and 1")
        if self.strand not in {"+", "-", ".", "?"}:
            raise ValidationError("cCRE strand must be +, -, ., or ?")

    def overlaps(self, chromosome: str, start: int, end: int) -> bool:
        return (
            normalize_chromosome(self.chromosome) == normalize_chromosome(chromosome)
            and self.start <= end
            and start <= self.end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CcreTrackBatch:
    source_id: str
    input_hash: str
    records: tuple[CcreRecord, ...]
    issues: tuple[CcreIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CcreTrackParser:
    """Parse ENCODE SCREEN-like TSV or JSON cCRE records."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        profile: CcreAtlasProfile | str = CcreAtlasProfile.ENCODE_SCREEN,
        input_format: str | None = None,
    ) -> CcreTrackBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("cCRE input must not be empty")
        selected_profile = CcreAtlasProfile(str(profile))
        first = next(line.strip() for line in text.splitlines() if line.strip())
        selected_format = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected_format == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid cCRE JSON: {exc}") from exc
            rows = payload.get("records", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("cCRE JSON must contain a records list")
            parsed = self._parse_rows(rows, source_id, selected_profile, json_mode=True)
        elif selected_format == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("cCRE TSV requires a header")
            parsed = self._parse_rows(
                tuple(reader), source_id, selected_profile, json_mode=False
            )
        else:
            raise ValidationError(f"unsupported cCRE format: {selected_format}")
        records, issues = parsed
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "records": records,
            "issues": issues,
        }
        return CcreTrackBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            records=records,
            issues=issues,
            content_address=content_hash(body),
        )

    def _parse_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        source_id: str,
        profile: CcreAtlasProfile,
        *,
        json_mode: bool,
    ) -> tuple[tuple[CcreRecord, ...], tuple[CcreIssue, ...]]:
        records: list[CcreRecord] = []
        issues: list[CcreIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            raw_hash = content_hash(row)
            try:
                chromosome = normalize_chromosome(str(self._value(row, "chromosome", "chrom")))
                start_zero = int(self._value(row, "start", "chrom_start"))
                end_exclusive = int(self._value(row, "end", "chrom_end"))
                if start_zero < 0 or end_exclusive <= start_zero:
                    raise ValidationError("cCRE BED interval must satisfy 0 <= start < end")
                score_value = self._value(row, "score", "z_score", "signal", default=None)
                score = None if score_value is None else float(score_value)
                if score is not None and score > 1.0 and score <= 100.0:
                    score /= 100.0
                records.append(
                    CcreRecord(
                        ccre_id=str(self._value(row, "ccre_id", "id", "name")),
                        chromosome=chromosome,
                        start=start_zero + 1,
                        end=end_exclusive,
                        profile=CcreAtlasProfile(
                            str(self._value(row, "profile", default=profile.value))
                        ),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                        raw_hash=raw_hash,
                        registry_class=(
                            str(self._value(row, "registry_class", "class"))
                            if self._value(row, "registry_class", "class") is not None
                            else None
                        ),
                        score=score,
                        cell_state=self._optional_text(row, "cell_state", "cell_type"),
                        disease_class=self._optional_text(row, "disease_class", "disease"),
                        age_group=self._optional_text(row, "age_group", "age"),
                        strand=str(self._value(row, "strand", default=".")),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CcreIssue(
                        "invalid_ccre_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        return tuple(records), tuple(issues)

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
class CcreAtlasMatch:
    ccre_id: str
    profile: CcreAtlasProfile
    chromosome: str
    start: int
    end: int
    registry_class: str | None
    score: float | None
    context_key: str
    source_id: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CcreAtlasQueryResult:
    profile: CcreAtlasProfile
    chromosome: str
    start: int
    end: int
    state: CcreQueryState
    matches: tuple[CcreAtlasMatch, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CcreAtlasAdapter:
    """Query a bounded cCRE snapshot against a declared context profile."""

    def __init__(
        self,
        records: Iterable[CcreRecord],
        *,
        profile: CcreAtlasProfile | str,
    ) -> None:
        self.profile = CcreAtlasProfile(str(profile))
        self._records = tuple(records)

    def query(
        self,
        chromosome: str,
        start: int,
        end: int,
        context: ReferenceContext,
    ) -> CcreAtlasQueryResult:
        if start < 1 or end < start:
            raise ValidationError("cCRE query interval is invalid")
        profile_records = tuple(
            record for record in self._records if record.profile == self.profile
        )
        overlaps = tuple(
            record for record in profile_records if record.overlaps(chromosome, start, end)
        )
        compatible = tuple(
            record for record in overlaps if self._context_matches(record, context)
        )
        if overlaps and not compatible:
            state = CcreQueryState.OUT_OF_DOMAIN
            matches: tuple[CcreAtlasMatch, ...] = ()
            reason = "overlapping records exist but none match the declared atlas context"
        elif not compatible:
            state = CcreQueryState.ABSENT
            matches = ()
            reason = "no compatible cCRE record overlaps the requested interval"
        else:
            matches = tuple(self._match(record, context) for record in compatible)
            state = CcreQueryState.AMBIGUOUS if len(matches) > 1 else CcreQueryState.SUPPORTED
            reason = (
                "multiple compatible cCRE records overlap the interval"
                if len(matches) > 1
                else "one compatible cCRE record overlaps the interval"
            )
        body = {
            "profile": self.profile,
            "chromosome": normalize_chromosome(chromosome),
            "start": start,
            "end": end,
            "state": state,
            "matches": matches,
            "reason": reason,
        }
        return CcreAtlasQueryResult(
            profile=self.profile,
            chromosome=normalize_chromosome(chromosome),
            start=start,
            end=end,
            state=state,
            matches=matches,
            reason=reason,
            content_address=content_hash(body),
        )

    @staticmethod
    def _context_matches(record: CcreRecord, context: ReferenceContext) -> bool:
        if record.cell_state and record.cell_state.lower() != context.cell_state.lower():
            return False
        if record.disease_class and record.disease_class.lower() not in {
            context.disease_class.lower(),
            "brain",
            "glioma",
            "all",
        }:
            return False
        if record.age_group and record.age_group.lower() not in {
            context.age_group.lower(),
            "all",
        }:
            return False
        return True

    @staticmethod
    def _match(record: CcreRecord, context: ReferenceContext) -> CcreAtlasMatch:
        body = {
            "ccre_id": record.ccre_id,
            "profile": record.profile,
            "context": context.key,
            "raw_hash": record.raw_hash,
        }
        return CcreAtlasMatch(
            ccre_id=record.ccre_id,
            profile=record.profile,
            chromosome=record.chromosome,
            start=record.start,
            end=record.end,
            registry_class=record.registry_class,
            score=record.score,
            context_key=context.key,
            source_id=record.source_id,
            raw_hash=record.raw_hash,
            content_address=content_hash(body),
        )


__all__ = [
    "CcreAtlasAdapter",
    "CcreAtlasMatch",
    "CcreAtlasProfile",
    "CcreAtlasQueryResult",
    "CcreIssue",
    "CcreQueryState",
    "CcreRecord",
    "CcreTrackBatch",
    "CcreTrackParser",
]
