"""Public aggregate data boundary for the Domain 01 identity fixture.

Identity operations join records from several sources, so their fixture needs a
stronger boundary than an operation-only unit test. This module validates
source receipts, exact context, aggregate scope, stable record identities, and
restricted field names before a fixture can contribute evidence.
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

IDENTITY_FIXTURE_SCHEMA_VERSION = "identity-evidence-v1"


class IdentityRecordKind(StrEnum):
    """Operation families exercised by the public identity fixture."""

    EQUIVALENCE = "equivalence"
    RECONCILIATION = "reconciliation"
    SAMPLE = "sample"
    CUSTODY = "custody"


class IdentityDataState(StrEnum):
    """Data-boundary verdict independent of an operation's scientific state."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class IdentitySourceReceipt:
    """One public aggregate source declaration with exact context."""

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
            raise ValidationError("identity source_url must use https")
        if not isinstance(self.public_aggregate, bool):
            raise ValidationError("public_aggregate must be boolean")
        if not isinstance(self.patient_level_data, bool):
            raise ValidationError("patient_level_data must be boolean")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> IdentitySourceReceipt:
        if not isinstance(raw, Mapping):
            raise ValidationError("identity source receipt must be an object")
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
class IdentityFixtureRecord:
    """One positive operation input with an expected replay state."""

    record_id: str
    kind: IdentityRecordKind
    operation: str
    source_id: str
    context_key: str
    payload: Mapping[str, Any]
    public_identifier: str
    expected_state: str = "supported"
    expected_signals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "operation",
            "source_id",
            "context_key",
            "public_identifier",
            "expected_state",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.payload, Mapping):
            raise ValidationError("identity record payload must be an object")
        if len(self.expected_signals) != len(set(self.expected_signals)):
            raise ValidationError("identity expected signals must be unique")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_context_key: str,
    ) -> IdentityFixtureRecord:
        if not isinstance(raw, Mapping):
            raise ValidationError("identity fixture record must be an object")
        try:
            kind = IdentityRecordKind(str(raw.get("kind", "")))
        except ValueError as exc:
            raise ValidationError("identity record kind is unsupported") from exc
        signals = raw.get("expected_signals", raw.get("expected_issue_codes", ()))
        if not isinstance(signals, Sequence) or isinstance(signals, (str, bytes)):
            raise ValidationError("identity expected_signals must be an array")
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
            tuple(str(item) for item in signals),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityFixtureControl:
    """One negative control that must remain reviewable or abstained."""

    control_id: str
    kind: IdentityRecordKind
    operation: str
    source_id: str
    context_key: str
    payload: Mapping[str, Any]
    public_identifier: str
    expected_state: str
    expected_signals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "control_id",
            "operation",
            "source_id",
            "context_key",
            "public_identifier",
            "expected_state",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.payload, Mapping):
            raise ValidationError("identity control payload must be an object")
        if len(self.expected_signals) != len(set(self.expected_signals)):
            raise ValidationError("identity control signals must be unique")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_context_key: str,
    ) -> IdentityFixtureControl:
        if not isinstance(raw, Mapping):
            raise ValidationError("identity negative control must be an object")
        try:
            kind = IdentityRecordKind(str(raw.get("kind", "")))
        except ValueError as exc:
            raise ValidationError("identity control kind is unsupported") from exc
        signals = raw.get("expected_signals", raw.get("expected_issue_codes", ()))
        if not isinstance(signals, Sequence) or isinstance(signals, (str, bytes)):
            raise ValidationError("identity control expected_signals must be an array")
        control_id = str(raw.get("control_id", raw.get("id", "")))
        return cls(
            control_id,
            kind,
            str(raw.get("operation", "")),
            str(raw.get("source_id", "")),
            str(raw.get("context_key", fallback_context_key)),
            raw.get("payload", {}),
            str(raw.get("public_identifier", control_id)),
            str(raw.get("expected_state", "abstained")),
            tuple(str(item) for item in signals),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityDataIssue:
    """Addressable fixture issue without retaining restricted values."""

    code: str
    path: str
    detail: str

    def __post_init__(self) -> None:
        require_non_empty(self.code, "identity issue code")
        require_non_empty(self.path, "identity issue path")
        require_non_empty(self.detail, "identity issue detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityDataAuditReport:
    """Complete public aggregate boundary result."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    positive_count: int
    negative_control_count: int
    counts_by_kind: Mapping[str, int]
    duplicate_record_ids: tuple[str, ...]
    duplicate_control_ids: tuple[str, ...]
    context_mismatch_ids: tuple[str, ...]
    unknown_source_ids: tuple[str, ...]
    sensitive_paths: tuple[str, ...]
    issues: tuple[IdentityDataIssue, ...]
    state: IdentityDataState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == IdentityDataState.ACCEPTED and not self.issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        return result


class IdentityFixtureCatalog:
    """Parse, index, and audit public identity operation records."""

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
        sources: Sequence[IdentitySourceReceipt],
        records: Sequence[IdentityFixtureRecord],
        controls: Sequence[IdentityFixtureControl],
        provenance: Mapping[str, Any],
        initial_issues: Sequence[IdentityDataIssue] = (),
    ) -> None:
        self.fixture_id = require_non_empty(fixture_id, "fixture_id")
        self.fixture_version = require_non_empty(fixture_version, "fixture_version")
        self.context_key = require_non_empty(context_key, "context_key")
        self.sources = tuple(sources)
        self.records = tuple(records)
        self.controls = tuple(controls)
        self.provenance = dict(provenance)
        self.initial_issues = tuple(initial_issues)

    @classmethod
    def from_file(cls, path: str | Path) -> IdentityFixtureCatalog:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"identity fixture is not valid JSON: {fixture_path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("identity fixture must be an object")
        return cls.from_fixture(raw)

    @classmethod
    def from_fixture(cls, raw: Mapping[str, Any]) -> IdentityFixtureCatalog:
        if not isinstance(raw, Mapping):
            raise ValidationError("identity fixture must be an object")
        context_key = _context_key(raw.get("context"))
        provenance = raw.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise ValidationError("identity fixture provenance must be an object")
        source_values = raw.get("source_receipts", ())
        if not isinstance(source_values, Sequence) or isinstance(source_values, (str, bytes)):
            raise ValidationError("identity source_receipts must be an array")
        sources = tuple(IdentitySourceReceipt.from_mapping(item) for item in source_values)
        record_values = raw.get("records", ())
        if not isinstance(record_values, Sequence) or isinstance(record_values, (str, bytes)):
            raise ValidationError("identity records must be an array")
        records = tuple(
            IdentityFixtureRecord.from_mapping(item, fallback_context_key=context_key)
            for item in record_values
        )
        control_values = raw.get("negative_controls", ())
        if not isinstance(control_values, Sequence) or isinstance(control_values, (str, bytes)):
            raise ValidationError("identity negative_controls must be an array")
        controls = tuple(
            IdentityFixtureControl.from_mapping(item, fallback_context_key=context_key)
            for item in control_values
        )
        initial: list[IdentityDataIssue] = []
        fixture_id = str(raw.get("fixture_id", ""))
        version = str(raw.get("fixture_version", ""))
        if not fixture_id.strip():
            initial.append(
                IdentityDataIssue(
                    "missing_fixture_id",
                    "fixture_id",
                    "fixture ID is required",
                )
            )
            fixture_id = "invalid-identity-fixture"
        if not version.strip():
            initial.append(
                IdentityDataIssue(
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
            controls=controls,
            provenance=provenance,
            initial_issues=initial,
        )

    def record(self, record_id: str) -> IdentityFixtureRecord | None:
        """Return one positive record by stable fixture identity."""

        for record in self.records:
            if record.record_id == record_id:
                return record
        return None

    def control(self, control_id: str) -> IdentityFixtureControl | None:
        """Return one negative control by stable fixture identity."""

        for control in self.controls:
            if control.control_id == control_id:
                return control
        return None

    def audit(self) -> IdentityDataAuditReport:
        issues = list(self.initial_issues)
        source_ids = tuple(source.source_id for source in self.sources)
        source_id_set = set(source_ids)
        if self.fixture_version != IDENTITY_FIXTURE_SCHEMA_VERSION:
            issues.append(
                IdentityDataIssue(
                    "fixture_version_mismatch",
                    "fixture_version",
                    f"expected {IDENTITY_FIXTURE_SCHEMA_VERSION}",
                )
            )
        if not self.sources:
            issues.append(
                IdentityDataIssue(
                    "missing_source_receipts",
                    "source_receipts",
                    "at least one public source receipt is required",
                )
            )
        for source_index, source in enumerate(self.sources):
            prefix = f"source_receipts[{source_index}]"
            if not source.public_aggregate:
                issues.append(
                    IdentityDataIssue(
                        "source_not_public_aggregate",
                        prefix,
                        "identity evidence requires public aggregate sources",
                    )
                )
            if source.patient_level_data:
                issues.append(
                    IdentityDataIssue(
                        "source_patient_scope",
                        prefix,
                        "patient-level source declarations are not allowed",
                    )
                )
            if source.context_key != self.context_key:
                issues.append(
                    IdentityDataIssue(
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
                IdentityDataIssue(
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
                IdentityDataIssue(
                    "duplicate_record_id",
                    f"records[{record_id}]",
                    "record identity is ambiguous",
                )
            )
        control_ids = tuple(control.control_id for control in self.controls)
        duplicate_controls = tuple(
            sorted(control_id for control_id, count in Counter(control_ids).items() if count > 1)
        )
        for control_id in duplicate_controls:
            issues.append(
                IdentityDataIssue(
                    "duplicate_control_id",
                    f"negative_controls[{control_id}]",
                    "control identity is ambiguous",
                )
            )
        if set(record_ids).intersection(control_ids):
            issues.append(
                IdentityDataIssue(
                    "record_control_collision",
                    "records and negative_controls",
                    "positive and negative identities must not collide",
                )
            )
        context_mismatches: list[str] = []
        unknown_sources: list[str] = []
        sensitive_paths: list[str] = []
        for collection_name, values in (
            ("records", self.records),
            ("negative_controls", self.controls),
        ):
            for index, item in enumerate(values):
                prefix = f"{collection_name}[{index}]"
                if item.context_key != self.context_key:
                    context_mismatches.append(
                        item.record_id if hasattr(item, "record_id") else item.control_id
                    )
                    issues.append(
                        IdentityDataIssue(
                            "context_mismatch",
                            prefix,
                            "identity operation context differs from fixture context",
                        )
                    )
                if item.source_id not in source_id_set:
                    unknown_sources.append(item.source_id)
                    issues.append(
                        IdentityDataIssue(
                            "unknown_source_id",
                            f"{prefix}.source_id",
                            f"source ID {item.source_id} has no receipt",
                        )
                    )
                for path, key in _walk_keys(item.payload, f"{prefix}.payload"):
                    lowered = key.casefold()
                    if any(fragment in lowered for fragment in self._sensitive_fragments):
                        sensitive_paths.append(path)
                        issues.append(
                            IdentityDataIssue(
                                "sensitive_record_path",
                                path,
                                "public aggregate fixture contains a restricted field name",
                            )
                        )
        if self.provenance.get("data_scope") != "public_aggregate":
            issues.append(
                IdentityDataIssue(
                    "fixture_scope_mismatch",
                    "provenance.data_scope",
                    "fixture must explicitly declare public_aggregate scope",
                )
            )
        if self.provenance.get("patient_level_data") is not False:
            issues.append(
                IdentityDataIssue(
                    "fixture_patient_scope",
                    "provenance.patient_level_data",
                    "fixture must explicitly declare patient_level_data=false",
                )
            )
        if self.provenance.get("evidence_boundary") in {None, ""}:
            issues.append(
                IdentityDataIssue(
                    "missing_evidence_boundary",
                    "provenance.evidence_boundary",
                    "fixture must state what the evidence does not claim",
                )
            )
        counts = Counter(record.kind.value for record in self.records)
        counts.update(f"negative:{control.kind.value}" for control in self.controls)
        body = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "source_ids": source_ids,
            "record_ids": record_ids,
            "control_ids": control_ids,
            "issues": issues,
        }
        state = IdentityDataState.ACCEPTED if not issues else IdentityDataState.REVIEW
        return IdentityDataAuditReport(
            self.fixture_id,
            self.fixture_version,
            self.context_key,
            tuple(sorted(source_ids)),
            len(self.records),
            len(self.controls),
            dict(sorted(counts.items())),
            duplicate_records,
            duplicate_controls,
            tuple(sorted(set(context_mismatches))),
            tuple(sorted(set(unknown_sources))),
            tuple(sorted(set(sensitive_paths))),
            tuple(issues),
            state,
            content_hash(body),
        )


def _context_key(value: Any) -> str:
    if not isinstance(value, Mapping):
        raise ValidationError("identity fixture context must be an object")
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


def audit_identity_fixture(path: str | Path) -> IdentityDataAuditReport:
    """Audit one checked-in public aggregate identity fixture."""

    return IdentityFixtureCatalog.from_file(path).audit()


__all__ = [
    "IDENTITY_FIXTURE_SCHEMA_VERSION",
    "IdentityDataAuditReport",
    "IdentityDataIssue",
    "IdentityDataState",
    "IdentityFixtureCatalog",
    "IdentityFixtureControl",
    "IdentityFixtureRecord",
    "IdentityRecordKind",
    "IdentitySourceReceipt",
    "audit_identity_fixture",
]
