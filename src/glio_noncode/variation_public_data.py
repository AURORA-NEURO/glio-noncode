"""Public aggregate data boundary for the Domain 01 variation fixture.

The variation operations accept rich records, so the fixture boundary is kept
separate from the normalizers. This module verifies source accounting, exact
context, public-data declarations, duplicate identity, and sensitive-path
absence before an operation is allowed to contribute evidence.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

VARIATION_FIXTURE_SCHEMA_VERSION = "variation-evidence-v1"


class VariationRecordKind(StrEnum):
    """Public aggregate record classes exercised by the variation fixture."""

    VRS = "vrs"
    CATEGORICAL = "categorical"
    ANNOTATION = "annotation"
    MULTIALLELIC = "multiallelic"
    REPEAT = "repeat"


class VariationDataState(StrEnum):
    """Data-boundary verdict for a variation fixture."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class VariationSourceReceipt:
    """One public source declaration with exact context and scope flags."""

    source_id: str
    source_url: str
    source_version: str
    context_key: str
    public_aggregate: bool
    patient_level_data: bool
    license: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "source_url",
            "source_version",
            "context_key",
            "license",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        if not self.source_url.startswith("https://"):
            raise ValidationError("variation source_url must use https")
        if not isinstance(self.public_aggregate, bool):
            raise ValidationError("public_aggregate must be boolean")
        if not isinstance(self.patient_level_data, bool):
            raise ValidationError("patient_level_data must be boolean")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> VariationSourceReceipt:
        if not isinstance(raw, Mapping):
            raise ValidationError("variation source receipt must be an object")
        return cls(
            str(raw.get("source_id", "")),
            str(raw.get("source_url", "")),
            str(raw.get("source_version", "")),
            str(raw.get("context_key", "")),
            raw.get("public_aggregate", False),
            raw.get("patient_level_data", True),
            str(raw.get("license", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationFixtureRecord:
    """One public aggregate operation input retained with source identity."""

    record_id: str
    kind: VariationRecordKind
    operation: str
    source_id: str
    context_key: str
    payload: Mapping[str, Any]
    public_identifier: str
    expected_state: str = "supported"

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "operation",
            "source_id",
            "context_key",
            "public_identifier",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.payload, Mapping):
            raise ValidationError("variation record payload must be an object")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_context_key: str,
    ) -> VariationFixtureRecord:
        if not isinstance(raw, Mapping):
            raise ValidationError("variation fixture record must be an object")
        try:
            kind = VariationRecordKind(str(raw.get("kind", "")))
        except ValueError as exc:
            raise ValidationError("variation record kind is unsupported") from exc
        record_id = str(raw.get("record_id", raw.get("id", "")))
        return cls(
            record_id,
            kind,
            str(raw.get("operation", "")),
            str(raw.get("source_id", "")),
            str(raw.get("context_key", fallback_context_key)),
            raw.get("payload", {}),
            str(raw.get("public_identifier", record_id)),
            str(raw.get("expected_state", "supported")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationDataIssue:
    """Addressable public-data issue without retaining a sensitive value."""

    code: str
    path: str
    detail: str

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.path, "issue path")
        require_non_empty(self.detail, "issue detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationDataAuditReport:
    """Complete data-boundary result for one variation fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    record_count: int
    counts_by_kind: Mapping[str, int]
    duplicate_record_ids: tuple[str, ...]
    context_mismatch_ids: tuple[str, ...]
    unknown_source_ids: tuple[str, ...]
    sensitive_paths: tuple[str, ...]
    issues: tuple[VariationDataIssue, ...]
    state: VariationDataState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == VariationDataState.ACCEPTED and not self.issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        return result


class VariationFixtureCatalog:
    """Parse, index, and audit public aggregate variation records."""

    _sensitive_fragments = (
        "patient",
        "participant",
        "donor",
        "medical_record",
        "medicalrecord",
        "mrn",
        "email",
        "phone",
        "password",
        "token",
        "secret",
    )

    def __init__(
        self,
        *,
        fixture_id: str,
        fixture_version: str,
        context_key: str,
        sources: Sequence[VariationSourceReceipt],
        records: Sequence[VariationFixtureRecord],
        provenance: Mapping[str, Any],
        initial_issues: Sequence[VariationDataIssue] = (),
    ) -> None:
        self.fixture_id = require_non_empty(fixture_id, "fixture_id")
        self.fixture_version = require_non_empty(fixture_version, "fixture_version")
        self.context_key = require_non_empty(context_key, "context_key")
        self.sources = tuple(sources)
        self.records = tuple(records)
        self.provenance = dict(provenance)
        self.initial_issues = tuple(initial_issues)

    @classmethod
    def from_file(cls, path: str | Path) -> VariationFixtureCatalog:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"variation fixture is not valid JSON: {fixture_path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("variation fixture must be an object")
        return cls.from_fixture(raw)

    @classmethod
    def from_fixture(cls, raw: Mapping[str, Any]) -> VariationFixtureCatalog:
        if not isinstance(raw, Mapping):
            raise ValidationError("variation fixture must be an object")
        context_key = _context_key(raw.get("context"))
        provenance = raw.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise ValidationError("variation fixture provenance must be an object")
        source_values = raw.get("source_receipts", ())
        if not isinstance(source_values, Sequence) or isinstance(source_values, (str, bytes)):
            raise ValidationError("variation source_receipts must be an array")
        sources = tuple(VariationSourceReceipt.from_mapping(item) for item in source_values)
        record_values = raw.get("records", ())
        if not isinstance(record_values, Sequence) or isinstance(record_values, (str, bytes)):
            raise ValidationError("variation records must be an array")
        records = tuple(
            VariationFixtureRecord.from_mapping(item, fallback_context_key=context_key)
            for item in record_values
        )
        initial: list[VariationDataIssue] = []
        fixture_id = str(raw.get("fixture_id", ""))
        version = str(raw.get("fixture_version", ""))
        if not fixture_id.strip():
            initial.append(
                VariationDataIssue(
                    "missing_fixture_id",
                    "fixture_id",
                    "fixture ID is required",
                )
            )
            fixture_id = "invalid-variation-fixture"
        if not version.strip():
            initial.append(
                VariationDataIssue(
                    "missing_fixture_version",
                    "fixture_version",
                    "fixture version is required",
                )
            )
            version = "missing"
        return cls(
            fixture_id=fixture_id,
            fixture_version=version,
            context_key=context_key,
            sources=sources,
            records=records,
            provenance=provenance,
            initial_issues=initial,
        )

    def record(self, record_id: str) -> VariationFixtureRecord | None:
        """Return one indexed record by its public fixture identity."""

        for record in self.records:
            if record.record_id == record_id:
                return record
        return None

    def audit(self) -> VariationDataAuditReport:
        issues = list(self.initial_issues)
        source_ids = tuple(source.source_id for source in self.sources)
        source_id_set = set(source_ids)
        if self.fixture_version != VARIATION_FIXTURE_SCHEMA_VERSION:
            issues.append(
                VariationDataIssue(
                    "fixture_version_mismatch",
                    "fixture_version",
                    f"expected {VARIATION_FIXTURE_SCHEMA_VERSION}",
                )
            )
        if not self.sources:
            issues.append(
                VariationDataIssue(
                    "missing_source_receipts",
                    "source_receipts",
                    "at least one public source receipt is required",
                )
            )
        for source_index, source in enumerate(self.sources):
            prefix = f"source_receipts[{source_index}]"
            if not source.public_aggregate:
                issues.append(
                    VariationDataIssue(
                        "source_not_public_aggregate",
                        prefix,
                        "variation evidence requires public aggregate sources",
                    )
                )
            if source.patient_level_data:
                issues.append(
                    VariationDataIssue(
                        "source_patient_scope",
                        prefix,
                        "patient-level source declarations are not allowed",
                    )
                )
            if source.context_key != self.context_key:
                issues.append(
                    VariationDataIssue(
                        "source_context_mismatch",
                        prefix,
                        "source receipt context differs from fixture context",
                    )
                )
        duplicate_sources = tuple(
            sorted(source_id for source_id, count in Counter(source_ids).items() if count > 1)
        )
        for source_id in duplicate_sources:
            issues.append(
                VariationDataIssue(
                    "duplicate_source_id",
                    "source_receipts",
                    f"source ID {source_id} occurs more than once",
                )
            )
        record_ids = tuple(record.record_id for record in self.records)
        duplicate_records = tuple(
            sorted(record_id for record_id, count in Counter(record_ids).items() if count > 1)
        )
        for record_id in duplicate_records:
            issues.append(
                VariationDataIssue(
                    "duplicate_record_id",
                    f"records[{record_id}]",
                    "record identity is ambiguous",
                )
            )
        context_mismatches: list[str] = []
        unknown_sources: list[str] = []
        sensitive_paths: list[str] = []
        for index, record in enumerate(self.records):
            prefix = f"records[{index}]"
            if record.context_key != self.context_key:
                context_mismatches.append(record.record_id)
                issues.append(
                    VariationDataIssue(
                        "record_context_mismatch",
                        prefix,
                        "record context differs from fixture context",
                    )
                )
            if record.source_id not in source_id_set:
                unknown_sources.append(record.source_id)
                issues.append(
                    VariationDataIssue(
                        "unknown_record_source",
                        f"{prefix}.source_id",
                        f"source ID {record.source_id} has no receipt",
                    )
                )
            for path, key in _walk_keys(record.payload, f"{prefix}.payload"):
                lowered = key.casefold()
                if any(fragment in lowered for fragment in self._sensitive_fragments):
                    sensitive_paths.append(path)
                    issues.append(
                        VariationDataIssue(
                            "sensitive_record_path",
                            path,
                            "public aggregate fixture contains a restricted field name",
                        )
                    )
        if self.provenance.get("patient_level_data") is not False:
            issues.append(
                VariationDataIssue(
                    "fixture_patient_scope",
                    "provenance.patient_level_data",
                    "fixture must explicitly declare patient_level_data=false",
                )
            )
        if self.provenance.get("evidence_boundary") in {None, ""}:
            issues.append(
                VariationDataIssue(
                    "missing_evidence_boundary",
                    "provenance.evidence_boundary",
                    "fixture must state what the evidence does not claim",
                )
            )
        counts = Counter(record.kind.value for record in self.records)
        body = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "source_ids": source_ids,
            "records": self.records,
            "issues": issues,
        }
        state = VariationDataState.ACCEPTED if not issues else VariationDataState.REVIEW
        return VariationDataAuditReport(
            self.fixture_id,
            self.fixture_version,
            self.context_key,
            tuple(sorted(source_ids)),
            len(self.records),
            dict(sorted(counts.items())),
            duplicate_records,
            tuple(sorted(set(context_mismatches))),
            tuple(sorted(set(unknown_sources))),
            tuple(sorted(set(sensitive_paths))),
            tuple(issues),
            state,
            content_hash(body),
        )


def _context_key(value: Any) -> str:
    if not isinstance(value, Mapping):
        raise ValidationError("variation fixture context must be an object")
    fields = (
        "genome_build",
        "disease_class",
        "age_group",
        "cell_state",
        "territory",
        "treatment_phase",
    )
    values = tuple(
        require_non_empty(str(value.get(field, "")), f"context.{field}")
        for field in fields
    )
    return "|".join(values)


def _walk_keys(value: Any, prefix: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            found.append((path, str(key)))
            found.extend(_walk_keys(child, path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_walk_keys(child, f"{prefix}[{index}]"))
    return tuple(found)


def audit_variation_fixture(path: str | Path) -> VariationDataAuditReport:
    """Audit one checked-in public aggregate variation fixture."""

    return VariationFixtureCatalog.from_file(path).audit()


__all__ = [
    "VARIATION_FIXTURE_SCHEMA_VERSION",
    "VariationDataAuditReport",
    "VariationDataIssue",
    "VariationDataState",
    "VariationFixtureCatalog",
    "VariationFixtureRecord",
    "VariationRecordKind",
    "VariationSourceReceipt",
    "audit_variation_fixture",
]
