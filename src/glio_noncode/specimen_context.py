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
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


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
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"specimen {name} is required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenMapping:
    """Candidate ontology mapping for one sample with no hidden fallback."""

    sample_id: str
    candidate_observation_ids: tuple[str, ...]
    subject_ids: tuple[str, ...]
    relationships: tuple[str, ...]
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


class SpecimenOntologyMapper:
    """Map declared sample/specimen rows while exposing contradictory labels."""

    def map(self, observations: Iterable[SpecimenObservation]) -> SpecimenOntologyResult:
        values = tuple(observations)
        grouped: dict[str, list[SpecimenObservation]] = defaultdict(list)
        for observation in values:
            grouped[observation.sample_id].append(observation)
        mappings: list[SpecimenMapping] = []
        for sample_id in sorted(grouped):
            rows = tuple(grouped[sample_id])
            subject_ids = tuple(sorted({row.subject_id for row in rows if row.subject_id}))
            relationships = tuple(sorted({row.relationship for row in rows}))
            reasons: list[str] = []
            if len(subject_ids) > 1:
                state = SpecimenEvidenceState.AMBIGUOUS
                reasons.append("one sample is declared against multiple subject identifiers")
            elif not subject_ids:
                state = SpecimenEvidenceState.PARTIAL
                reasons.append("subject identifier was not declared")
            else:
                state = SpecimenEvidenceState.SUPPORTED
            if len(relationships) > 1:
                state = SpecimenEvidenceState.AMBIGUOUS
                reasons.append("one sample has conflicting relationship labels")
            body = {
                "sample_id": sample_id,
                "observation_ids": tuple(row.observation_id for row in rows),
                "subject_ids": subject_ids,
                "relationships": relationships,
                "state": state,
            }
            mappings.append(
                SpecimenMapping(
                    sample_id=sample_id,
                    candidate_observation_ids=tuple(row.observation_id for row in rows),
                    subject_ids=subject_ids,
                    relationships=relationships,
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
        observations: list[SpecimenObservation] = []
        issues: list[SpecimenIssue] = []
        for line_number, row in enumerate(rows, start=1):
            raw_hash = content_hash(row)
            try:
                sample_id = str(_row_value(row, "sample_id", "sample"))
                specimen_id = str(_row_value(row, "specimen_id", "specimen", default=sample_id))
                subject_value = _row_value(row, "subject_id", "patient_id", "participant_id")
                relationship = str(
                    _row_value(row, "relationship", "sample_type", default="unspecified")
                )
                specimen_type = str(
                    _row_value(row, "specimen_type", "material", default="unspecified")
                )
                timepoint = str(_row_value(row, "timepoint", "visit", default="unspecified"))
                if not sample_id.strip():
                    raise ValidationError("sample_id is required")
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
        values = tuple(observations)
        tumors = tuple(
            row
            for row in values
            if row.relationship.lower() in {"tumor", "tumour", "case", "somatic"}
        )
        normals_by_subject: dict[str, list[SpecimenObservation]] = defaultdict(list)
        for row in values:
            if row.relationship.lower() in {"normal", "germline", "control"} and row.subject_id:
                normals_by_subject[row.subject_id].append(row)
        pairs: list[MatchedNormalPair] = []
        for tumor in sorted(tumors, key=lambda row: row.sample_id):
            reasons: list[str] = []
            if not tumor.subject_id:
                state = SpecimenEvidenceState.ABSTAINED
                normal_rows: tuple[SpecimenObservation, ...] = ()
                reasons.append("tumor subject identifier is missing")
            else:
                normal_rows = tuple(normals_by_subject.get(tumor.subject_id, ()))
                if len(normal_rows) == 1:
                    state = SpecimenEvidenceState.SUPPORTED
                elif len(normal_rows) > 1:
                    state = SpecimenEvidenceState.AMBIGUOUS
                    reasons.append("multiple same-subject normal samples are available")
                else:
                    state = SpecimenEvidenceState.ABSTAINED
                    reasons.append("no same-subject normal sample was declared")
            source_ids = (tumor.observation_id,) + tuple(
                row.observation_id for row in normal_rows
            )
            body = {
                "tumor": tumor.sample_id,
                "subject": tumor.subject_id,
                "normals": tuple(row.sample_id for row in normal_rows),
                "state": state,
            }
            pairs.append(
                MatchedNormalPair(
                    tumor_sample_id=tumor.sample_id,
                    subject_id=tumor.subject_id,
                    normal_sample_ids=tuple(row.sample_id for row in normal_rows),
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
        if not self.sample_id or not self.caller_id or not self.source_id or not self.raw_hash:
            raise ValidationError("purity/ploidy identifiers and source are required")
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

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        input_format: str | None = None,
    ) -> PurityPloidyBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("purity/ploidy input must not be empty")
        first = next(line.strip() for line in text.splitlines() if line.strip())
        selected = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid purity/ploidy JSON: {exc}") from exc
            rows = payload.get("records", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("purity/ploidy JSON must contain a records list")
            return self._parse_rows(rows, source_id, text, json_mode=True)
        if selected != "tsv":
            raise ValidationError(f"unsupported purity/ploidy format: {selected}")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("purity/ploidy TSV requires a header")
        return self._parse_rows(tuple(reader), source_id, text, json_mode=False)

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
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            raw_hash = content_hash(row)
            try:
                purity_value = float(_row_value(row, "purity", "tumor_purity"))
                if purity_value > 1.0 and purity_value <= 100.0:
                    purity_value /= 100.0
                records.append(
                    PurityPloidyRecord(
                        sample_id=str(_row_value(row, "sample_id", "sample")),
                        caller_id=str(
                            _row_value(row, "caller_id", "caller", default="unspecified")
                        ),
                        caller_version=str(
                            _row_value(row, "caller_version", "version", default="unspecified")
                        ),
                        purity=purity_value,
                        ploidy=float(_row_value(row, "ploidy", "tumor_ploidy")),
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
        return PurityPloidyBatch(
            source_id=source_id,
            input_hash=content_hash(text),
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
