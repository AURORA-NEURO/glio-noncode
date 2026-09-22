"""Specimen identity, matched-normal, purity, and integrity boundaries.

Domain 03 is intentionally conservative. These utilities do not infer a
patient identity from a label, manufacture a matched normal, or turn generic
purity thresholds into a clinical statement. They preserve declared
relationships and make one-to-many, missing, and contradictory mappings
explicit for review.
"""

from __future__ import annotations

import csv
import io
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import islice
from typing import Any

from .errors import ValidationError
from .serialization import _strict_json_loads, content_hash, jsonable

MAX_SPECIMEN_OBSERVATIONS = 100_000
MAX_PURITY_PLOIDY_INPUT_BYTES = 16 * 1024 * 1024
MAX_PURITY_PLOIDY_ROWS = 100_000
_UNDECLARED_VALUES = frozenset({"", ".", "na", "n/a", "none", "null", "unknown", "unspecified"})


class SpecimenEvidenceState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"


class SpecimenIssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SpecimenIssue:
    """A source-addressable specimen or integrity anomaly."""

    code: str
    severity: SpecimenIssueSeverity
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    sample_ids: tuple[str, ...] = ()
    remediation: str = "Inspect the source declaration and route unresolved identity to review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenObservation:
    """One project-local specimen declaration."""

    observation_id: str
    sample_id: str
    specimen_id: str
    subject_id: str | None
    relationship: str
    specimen_type: str
    timepoint: str
    source_id: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "sample_id",
            "specimen_id",
            "relationship",
            "specimen_type",
            "timepoint",
            "source_id",
            "raw_hash",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"specimen {name} is required")
            if len(value) > 2_048 or any(ord(character) < 32 for character in value):
                raise ValidationError(f"specimen {name} must be a bounded text value")
        if self.subject_id is not None and (
            not isinstance(self.subject_id, str)
            or not self.subject_id.strip()
            or len(self.subject_id) > 2_048
            or any(ord(character) < 32 for character in self.subject_id)
        ):
            raise ValidationError("specimen subject_id must be a bounded text value or null")
        if not isinstance(self.attributes, Mapping):
            raise ValidationError("specimen attributes must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenMapping:
    """Candidate ontology mapping for one sample with no hidden fallback."""

    sample_id: str
    candidate_observation_ids: tuple[str, ...]
    subject_ids: tuple[str, ...]
    specimen_ids: tuple[str, ...]
    relationships: tuple[str, ...]
    specimen_types: tuple[str, ...]
    timepoints: tuple[str, ...]
    state: SpecimenEvidenceState
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenOntologyResult:
    """All mapped specimen identities and source issues."""

    mappings: tuple[SpecimenMapping, ...]
    observations: tuple[SpecimenObservation, ...]
    issues: tuple[SpecimenIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _row_value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return default


def _is_declared(value: str | None) -> bool:
    return value is not None and value.strip().casefold() not in _UNDECLARED_VALUES


class SpecimenOntologyMapper:
    """Map declared sample/specimen rows while exposing contradictory labels."""

    def map(self, observations: Iterable[SpecimenObservation]) -> SpecimenOntologyResult:
        try:
            values = tuple(islice(iter(observations), MAX_SPECIMEN_OBSERVATIONS + 1))
        except TypeError as exc:
            raise ValidationError("specimen observations must be iterable") from exc
        if len(values) > MAX_SPECIMEN_OBSERVATIONS:
            raise ValidationError(
                f"specimen mapping exceeds the {MAX_SPECIMEN_OBSERVATIONS}-observation limit"
            )
        if any(not isinstance(item, SpecimenObservation) for item in values):
            raise ValidationError("specimen observations must be typed SpecimenObservation values")
        observation_ids = tuple(item.observation_id for item in values)
        if len(set(observation_ids)) != len(observation_ids):
            raise ValidationError("specimen observation IDs must be unique")
        grouped: dict[str, list[SpecimenObservation]] = defaultdict(list)
        for observation in values:
            grouped[observation.sample_id].append(observation)
        mappings: list[SpecimenMapping] = []
        for sample_id in sorted(grouped):
            rows = tuple(grouped[sample_id])
            subject_ids = tuple(
                sorted({row.subject_id for row in rows if _is_declared(row.subject_id)})
            )
            specimen_ids = tuple(
                sorted({row.specimen_id for row in rows if _is_declared(row.specimen_id)})
            )
            relationships = tuple(
                sorted({row.relationship for row in rows if _is_declared(row.relationship)})
            )
            specimen_types = tuple(
                sorted({row.specimen_type for row in rows if _is_declared(row.specimen_type)})
            )
            timepoints = tuple(
                sorted({row.timepoint for row in rows if _is_declared(row.timepoint)})
            )
            reasons: list[str] = []
            has_conflict = False
            if len(subject_ids) > 1:
                has_conflict = True
                reasons.append("one sample is declared against multiple subject identifiers")
            if len(specimen_ids) > 1:
                has_conflict = True
                reasons.append("one sample is declared against multiple specimen identifiers")
            if len(relationships) > 1:
                has_conflict = True
                reasons.append("one sample has conflicting relationship labels")
            if len(specimen_types) > 1:
                has_conflict = True
                reasons.append("one sample has conflicting specimen type labels")
            if len(timepoints) > 1:
                has_conflict = True
                reasons.append("one sample has conflicting timepoint labels")

            missing_fields = tuple(
                label
                for label, field_values in (
                    ("subject identifier", tuple(row.subject_id for row in rows)),
                    ("specimen identifier", tuple(row.specimen_id for row in rows)),
                    ("relationship", tuple(row.relationship for row in rows)),
                    ("specimen type", tuple(row.specimen_type for row in rows)),
                    ("timepoint", tuple(row.timepoint for row in rows)),
                )
                if any(not _is_declared(value) for value in field_values)
            )
            if missing_fields:
                reasons.append(
                    "one or more observations omit declared " + ", ".join(missing_fields)
                )
            state = (
                SpecimenEvidenceState.AMBIGUOUS
                if has_conflict
                else SpecimenEvidenceState.PARTIAL
                if missing_fields
                else SpecimenEvidenceState.SUPPORTED
            )
            body = {
                "sample_id": sample_id,
                "observation_ids": tuple(row.observation_id for row in rows),
                "subject_ids": subject_ids,
                "specimen_ids": specimen_ids,
                "relationships": relationships,
                "specimen_types": specimen_types,
                "timepoints": timepoints,
                "state": state,
                "reasons": tuple(reasons),
            }
            mappings.append(
                SpecimenMapping(
                    sample_id=sample_id,
                    candidate_observation_ids=tuple(row.observation_id for row in rows),
                    subject_ids=subject_ids,
                    specimen_ids=specimen_ids,
                    relationships=relationships,
                    specimen_types=specimen_types,
                    timepoints=timepoints,
                    state=state,
                    reasons=tuple(reasons),
                    content_address=content_hash(body),
                )
            )
        body = {"mappings": mappings, "observations": values, "issues": ()}
        return SpecimenOntologyResult(
            mappings=tuple(mappings),
            observations=values,
            issues=(),
            content_address=content_hash(body),
        )

    def parse_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        source_id: str,
    ) -> SpecimenOntologyResult:
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValidationError("specimen source_id is required")
        observations: list[SpecimenObservation] = []
        issues: list[SpecimenIssue] = []
        for line_number, row in enumerate(rows, start=1):
            if line_number > MAX_SPECIMEN_OBSERVATIONS:
                raise ValidationError(
                    f"specimen mapping exceeds the {MAX_SPECIMEN_OBSERVATIONS}-observation limit"
                )
            raw_hash = content_hash(row)
            try:
                sample_value = _row_value(row, "sample_id", "sample")
                if sample_value is None or not str(sample_value).strip():
                    raise ValidationError("sample_id is required")
                sample_id = str(sample_value)
                specimen_id = str(
                    _row_value(row, "specimen_id", "specimen", default="unspecified")
                )
                subject_value = _row_value(
                    row,
                    "subject_id",
                    "subject_key",
                    "case_key",
                    "donor_key",
                    "patient_id",
                    "participant_id",
                )
                relationship = str(
                    _row_value(row, "relationship", "sample_type", default="unspecified")
                )
                specimen_type = str(
                    _row_value(row, "specimen_type", "material", default="unspecified")
                )
                timepoint = str(_row_value(row, "timepoint", "visit", default="unspecified"))
                observations.append(
                    SpecimenObservation(
                        observation_id=f"{source_id}:{line_number}",
                        sample_id=sample_id,
                        specimen_id=specimen_id,
                        subject_id=(str(subject_value) if subject_value is not None else None),
                        relationship=relationship,
                        specimen_type=specimen_type,
                        timepoint=timepoint,
                        source_id=source_id,
                        raw_hash=raw_hash,
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SpecimenIssue(
                        "invalid_specimen_row",
                        SpecimenIssueSeverity.ERROR,
                        str(exc),
                        line_number,
                        raw_hash,
                    )
                )
        result = self.map(observations)
        if not issues:
            return result
        body = {
            "mappings": result.mappings,
            "observations": result.observations,
            "issues": tuple(issues),
        }
        return SpecimenOntologyResult(
            mappings=result.mappings,
            observations=result.observations,
            issues=tuple(issues),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class MatchedNormalPair:
    """One tumor-to-normal resolution, including missing or ambiguous outcomes."""

    tumor_sample_id: str
    subject_id: str | None
    normal_sample_ids: tuple[str, ...]
    state: SpecimenEvidenceState
    reasons: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MatchedNormalResult:
    pairs: tuple[MatchedNormalPair, ...]
    issues: tuple[SpecimenIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MatchedNormalResolver:
    """Resolve only declared same-subject normal relationships."""

    def resolve(self, observations: Iterable[SpecimenObservation]) -> MatchedNormalResult:
        ontology = SpecimenOntologyMapper().map(observations)
        values = ontology.observations
        mappings = {mapping.sample_id: mapping for mapping in ontology.mappings}
        rows_by_sample: dict[str, list[SpecimenObservation]] = defaultdict(list)
        for row in values:
            rows_by_sample[row.sample_id].append(row)
        tumor_relationships = {"tumor", "tumour", "case", "somatic"}
        normal_relationships = {"normal", "germline", "control"}
        tumor_sample_ids = tuple(
            sample_id
            for sample_id in sorted(rows_by_sample)
            if tumor_relationships.intersection(mappings[sample_id].relationships)
        )
        normals_by_subject: dict[str, dict[str, tuple[SpecimenObservation, ...]]] = defaultdict(
            dict
        )
        for sample_id, rows in rows_by_sample.items():
            mapping = mappings[sample_id]
            if (
                len(mapping.relationships) == 1
                and mapping.relationships[0] in normal_relationships
                and len(mapping.subject_ids) == 1
            ):
                normals_by_subject[mapping.subject_ids[0]][sample_id] = tuple(rows)
        pairs: list[MatchedNormalPair] = []
        for tumor_sample_id in tumor_sample_ids:
            tumor_mapping = mappings[tumor_sample_id]
            tumor_rows = tuple(rows_by_sample[tumor_sample_id])
            reasons: list[str] = []
            if tumor_mapping.state == SpecimenEvidenceState.AMBIGUOUS:
                state = SpecimenEvidenceState.AMBIGUOUS
                subject_id = (
                    tumor_mapping.subject_ids[0] if len(tumor_mapping.subject_ids) == 1 else None
                )
                normal_rows: tuple[SpecimenObservation, ...] = ()
                reasons.append("tumor sample has conflicting specimen context declarations")
            elif len(tumor_mapping.subject_ids) != 1:
                state = SpecimenEvidenceState.ABSTAINED
                subject_id = None
                normal_rows = ()
                reasons.append("tumor subject identifier is missing")
            else:
                subject_id = tumor_mapping.subject_ids[0]
                same_subject_normals = normals_by_subject.get(subject_id, {})
                candidate_normal_ids = tuple(
                    sample_id
                    for sample_id in sorted(same_subject_normals)
                    if sample_id != tumor_sample_id
                )
                if len(candidate_normal_ids) > 1:
                    state = SpecimenEvidenceState.AMBIGUOUS
                    normal_rows = tuple(
                        row
                        for sample_id in candidate_normal_ids
                        for row in same_subject_normals[sample_id]
                    )
                    reasons.append("multiple same-subject normal samples are available")
                elif len(candidate_normal_ids) == 1:
                    normal_sample_id = candidate_normal_ids[0]
                    normal_rows = same_subject_normals[normal_sample_id]
                    normal_mapping = mappings[normal_sample_id]
                    if normal_mapping.state == SpecimenEvidenceState.AMBIGUOUS:
                        state = SpecimenEvidenceState.AMBIGUOUS
                        reasons.append(
                            "matched normal sample has conflicting specimen declarations"
                        )
                    elif (
                        tumor_mapping.state == SpecimenEvidenceState.PARTIAL
                        or normal_mapping.state == SpecimenEvidenceState.PARTIAL
                    ):
                        state = SpecimenEvidenceState.PARTIAL
                        reasons.append("tumor or normal specimen context is incomplete")
                    else:
                        state = SpecimenEvidenceState.SUPPORTED
                else:
                    state = SpecimenEvidenceState.ABSTAINED
                    normal_rows = ()
                    reasons.append("no same-subject normal sample was declared")
            normal_sample_ids = tuple(sorted({row.sample_id for row in normal_rows}))
            source_ids = tuple(
                sorted({row.observation_id for row in (*tumor_rows, *normal_rows)})
            )
            body = {
                "tumor": tumor_sample_id,
                "subject": subject_id,
                "normals": normal_sample_ids,
                "source_observation_ids": source_ids,
                "state": state,
                "reasons": tuple(reasons),
            }
            pairs.append(
                MatchedNormalPair(
                    tumor_sample_id=tumor_sample_id,
                    subject_id=subject_id,
                    normal_sample_ids=normal_sample_ids,
                    state=state,
                    reasons=tuple(reasons),
                    source_observation_ids=source_ids,
                    content_address=content_hash(body),
                )
            )
        result_body = {"pairs": pairs, "issues": ()}
        return MatchedNormalResult(
            pairs=tuple(pairs),
            issues=(),
            content_address=content_hash(result_body),
        )


@dataclass(frozen=True, slots=True)
class PurityPloidyRecord:
    """One caller-produced purity/ploidy measurement with source receipt fields."""

    sample_id: str
    caller_id: str
    caller_version: str
    purity: float
    ploidy: float
    source_id: str
    raw_hash: str
    source_line: int | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("sample_id", "caller_id", "caller_version", "source_id", "raw_hash"):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 2_048
                or any(ord(character) < 32 for character in value)
            ):
                raise ValidationError(f"purity/ploidy {name} must be bounded nonempty text")
        for name in ("purity", "ploidy"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(f"purity/ploidy {name} must be numeric")
            try:
                finite = math.isfinite(float(value))
            except (OverflowError, TypeError, ValueError):
                finite = False
            if not finite:
                raise ValidationError(f"purity/ploidy {name} must be finite")
        if self.source_line is not None and (
            isinstance(self.source_line, bool)
            or not isinstance(self.source_line, int)
            or self.source_line < 1
        ):
            raise ValidationError("purity/ploidy source_line must be a positive integer or null")
        if not isinstance(self.attributes, Mapping):
            raise ValidationError("purity/ploidy attributes must be a mapping")
        if not 0.0 <= self.purity <= 1.0:
            raise ValidationError("purity must be between 0 and 1")
        if self.ploidy <= 0:
            raise ValidationError("ploidy must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PurityPloidyBatch:
    source_id: str
    input_hash: str
    records: tuple[PurityPloidyRecord, ...]
    issues: tuple[SpecimenIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PurityPloidyImporter:
    """Parse common TSV/JSON purity and ploidy tables with anomaly logging."""

    @staticmethod
    def _row_hash(row: Any) -> str:
        if isinstance(row, Mapping):
            entries = [[key, value] for key, value in row.items()]
            return content_hash({"ordered_entries": entries})
        return content_hash(row)

    @staticmethod
    def _numeric_value(row: Mapping[str, Any], *names: str, label: str) -> float:
        raw_value = _row_value(row, *names)
        if raw_value is None or isinstance(raw_value, bool):
            raise ValidationError(f"purity/ploidy {label} must be numeric")
        if not isinstance(raw_value, (str, int, float)):
            raise ValidationError(f"purity/ploidy {label} must be numeric")
        try:
            value = float(raw_value)
        except (TypeError, ValueError, OverflowError):
            raise ValidationError(f"purity/ploidy {label} must be numeric") from None
        if not math.isfinite(value):
            raise ValidationError(f"purity/ploidy {label} must be finite")
        return value

    @staticmethod
    def _identifier(value: Any, label: str) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValidationError(f"purity/ploidy {label} is required")
        normalized = str(value)
        if (
            not normalized.strip()
            or len(normalized) > 2_048
            or any(ord(character) < 32 for character in normalized)
        ):
            raise ValidationError(f"purity/ploidy {label} must be bounded nonempty text")
        return normalized

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        input_format: str | None = None,
    ) -> PurityPloidyBatch:
        if not isinstance(text, str):
            raise ValidationError("purity/ploidy input must be text")
        if len(text) > MAX_PURITY_PLOIDY_INPUT_BYTES:
            raise ValidationError("purity/ploidy input exceeds its size limit")
        byte_count = 0
        try:
            for start in range(0, len(text), 8_192):
                byte_count += len(text[start : start + 8_192].encode("utf-8"))
                if byte_count > MAX_PURITY_PLOIDY_INPUT_BYTES:
                    raise ValidationError("purity/ploidy input exceeds its size limit")
        except UnicodeEncodeError:
            raise ValidationError("purity/ploidy input must be valid UTF-8 text") from None
        if not text.strip():
            raise ValidationError("purity/ploidy input must not be empty")
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 2_048:
            raise ValidationError("purity/ploidy source_id must be bounded nonempty text")
        if any(ord(character) < 32 for character in source_id):
            raise ValidationError("purity/ploidy source_id contains control characters")
        first = next((line.strip() for line in io.StringIO(text) if line.strip()), "")
        selected = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected == "json":
            try:
                payload = _strict_json_loads(text)
            except ValueError:
                raise ValidationError(
                    "purity/ploidy JSON is malformed or contains duplicate/non-finite values"
                ) from None
            rows = payload.get("records", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("purity/ploidy JSON must contain a records list")
            if len(rows) > MAX_PURITY_PLOIDY_ROWS:
                raise ValidationError("purity/ploidy input exceeds its row limit")
            return self._parse_rows(rows, source_id, text, json_mode=True)
        if selected != "tsv":
            raise ValidationError("unsupported purity/ploidy format")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        try:
            fieldnames = reader.fieldnames
        except csv.Error:
            raise ValidationError("purity/ploidy TSV contains malformed delimited text") from None
        if not fieldnames:
            raise ValidationError("purity/ploidy TSV requires a header")
        headers = [header.strip() for header in fieldnames]
        normalized_headers = [header.casefold() for header in headers]
        if any(not header for header in headers) or len(set(normalized_headers)) != len(headers):
            raise ValidationError("purity/ploidy TSV headers must be nonempty and unique")
        reader.fieldnames = headers
        try:
            return self._parse_rows(reader, source_id, text, json_mode=False)
        except csv.Error:
            raise ValidationError("purity/ploidy TSV contains malformed delimited text") from None

    def _parse_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        source_id: str,
        text: str,
        *,
        json_mode: bool,
    ) -> PurityPloidyBatch:
        records: list[PurityPloidyRecord] = []
        issues: list[SpecimenIssue] = []
        row_count = 0
        for row in rows:
            row_count += 1
            if row_count > MAX_PURITY_PLOIDY_ROWS:
                raise ValidationError("purity/ploidy input exceeds its row limit")
            index = row_count if json_mode else row_count + 1
            raw_hash = self._row_hash(row)
            if not isinstance(row, Mapping):
                issues.append(
                    SpecimenIssue(
                        "invalid_purity_ploidy_row",
                        SpecimenIssueSeverity.ERROR,
                        "measurement row must be an object",
                        None if json_mode else index,
                        raw_hash,
                    )
                )
                continue
            if not json_mode and (None in row or any(value is None for value in row.values())):
                issues.append(
                    SpecimenIssue(
                        "invalid_purity_ploidy_row",
                        SpecimenIssueSeverity.ERROR,
                        "row field count does not match the TSV header",
                        index,
                        raw_hash,
                    )
                )
                continue
            try:
                sample_value = _row_value(row, "sample_id", "sample")
                if sample_value is None:
                    raise ValidationError("purity/ploidy sample_id is required")
                purity_value = self._numeric_value(
                    row, "purity", "tumor_purity", label="purity"
                )
                if purity_value > 1.0 and purity_value <= 100.0:
                    purity_value /= 100.0
                records.append(
                    PurityPloidyRecord(
                        sample_id=self._identifier(sample_value, "sample_id"),
                        caller_id=self._identifier(
                            _row_value(row, "caller_id", "caller", default="unspecified"),
                            "caller_id",
                        ),
                        caller_version=self._identifier(
                            _row_value(row, "caller_version", "version", default="unspecified"),
                            "caller_version",
                        ),
                        purity=purity_value,
                        ploidy=self._numeric_value(
                            row, "ploidy", "tumor_ploidy", label="ploidy"
                        ),
                        source_id=source_id,
                        raw_hash=raw_hash,
                        source_line=None if json_mode else index,
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SpecimenIssue(
                        "invalid_purity_ploidy_row",
                        SpecimenIssueSeverity.ERROR,
                        str(exc)
                        if isinstance(exc, ValidationError)
                        else "measurement contains an invalid numeric value",
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        if row_count == 0:
            raise ValidationError("purity/ploidy input contains no measurement rows")
        input_hash = content_hash(text)
        body = {
            "source_id": source_id,
            "input_hash": input_hash,
            "records": tuple(records),
            "issues": tuple(issues),
        }
        return PurityPloidyBatch(
            source_id=source_id,
            input_hash=input_hash,
            records=tuple(records),
            issues=tuple(issues),
            content_address=content_hash(body),
        )


class SampleIntegrityState(StrEnum):
    CLEAR = "clear"
    WATCH = "watch"
    FLAGGED = "flagged"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class SampleFingerprint:
    """Observed fingerprint measurements used for integrity triage."""

    sample_id: str
    declared_subject_id: str | None
    observed_subject_id: str | None
    contamination_fraction: float | None
    discordance_rate: float | None
    marker_count: int | None
    source_id: str
    raw_hash: str

    def __post_init__(self) -> None:
        if not self.sample_id or not self.source_id or not self.raw_hash:
            raise ValidationError("fingerprint sample and source fields are required")
        for name in ("contamination_fraction", "discordance_rate"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
        if self.marker_count is not None and self.marker_count < 0:
            raise ValidationError("marker_count cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SampleIntegrityAssessment:
    sample_id: str
    state: SampleIntegrityState
    reasons: tuple[str, ...]
    source_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContaminationSwapDetector:
    """Flag declared fingerprint conflicts and abstain on incomplete evidence."""

    def __init__(
        self,
        *,
        contamination_watch: float = 0.02,
        contamination_flag: float = 0.05,
        discordance_watch: float = 0.02,
    ) -> None:
        if not 0 <= contamination_watch <= contamination_flag <= 1:
            raise ValidationError("contamination thresholds must be ordered in [0, 1]")
        if not 0 <= discordance_watch <= 1:
            raise ValidationError("discordance_watch must be between 0 and 1")
        self.contamination_watch = contamination_watch
        self.contamination_flag = contamination_flag
        self.discordance_watch = discordance_watch

    def assess(
        self,
        fingerprints: Iterable[SampleFingerprint],
    ) -> tuple[SampleIntegrityAssessment, ...]:
        assessments: list[SampleIntegrityAssessment] = []
        for fingerprint in sorted(fingerprints, key=lambda item: item.sample_id):
            reasons: list[str] = []
            if fingerprint.declared_subject_id is None or fingerprint.observed_subject_id is None:
                state = SampleIntegrityState.ABSTAINED
                reasons.append("declared and observed subject fingerprints are incomplete")
            elif fingerprint.declared_subject_id != fingerprint.observed_subject_id:
                state = SampleIntegrityState.FLAGGED
                reasons.append("observed subject fingerprint conflicts with declared subject")
            elif fingerprint.contamination_fraction is None or fingerprint.discordance_rate is None:
                state = SampleIntegrityState.ABSTAINED
                reasons.append("contamination and discordance metrics are incomplete")
            elif fingerprint.contamination_fraction >= self.contamination_flag:
                state = SampleIntegrityState.FLAGGED
                reasons.append("contamination exceeds the configured flag threshold")
            elif (
                fingerprint.contamination_fraction >= self.contamination_watch
                or fingerprint.discordance_rate >= self.discordance_watch
            ):
                state = SampleIntegrityState.WATCH
                reasons.append("fingerprint quality exceeds a configured watch threshold")
            else:
                state = SampleIntegrityState.CLEAR
            body = {
                "sample_id": fingerprint.sample_id,
                "state": state,
                "reasons": tuple(reasons),
                "raw_hash": fingerprint.raw_hash,
            }
            assessments.append(
                SampleIntegrityAssessment(
                    sample_id=fingerprint.sample_id,
                    state=state,
                    reasons=tuple(reasons),
                    source_id=fingerprint.source_id,
                    content_address=content_hash(body),
                )
            )
        return tuple(assessments)


__all__ = [
    "ContaminationSwapDetector",
    "MatchedNormalPair",
    "MatchedNormalResolver",
    "MatchedNormalResult",
    "PurityPloidyBatch",
    "PurityPloidyImporter",
    "PurityPloidyRecord",
    "SampleFingerprint",
    "SampleIntegrityAssessment",
    "SampleIntegrityState",
    "SpecimenEvidenceState",
    "SpecimenIssue",
    "SpecimenIssueSeverity",
    "SpecimenMapping",
    "SpecimenObservation",
    "SpecimenOntologyMapper",
    "SpecimenOntologyResult",
]
