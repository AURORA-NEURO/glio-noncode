"""Public, non-patient research data contracts for frontier fixtures.

This module provides the data boundary used by the frontier evidence gate. It
does not retrieve external records and it does not infer biology. Instead, it
turns declared public identifiers and aggregate measurements into typed,
context-qualified records with source receipts, duplicate detection, and
explicit rejection of patient-level or secret-like fields.

The boundary is intentionally stricter than the capability implementations:
an operation can accept a mapping, while the fixture catalog requires every
record to be attributable to a declared source and exact context.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class PublicDataState(StrEnum):
    """Quality state for the public fixture data boundary."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    REJECTED = "rejected"


class PublicRecordKind(StrEnum):
    """Normalized record families retained by the catalog."""

    SOURCE = "source"
    TARGET = "target"
    EXPERIMENT = "experiment"
    EVIDENCE = "evidence"
    CLAIM = "claim"
    WORKBENCH = "workbench"
    DEPLOYMENT = "deployment"


_CONTEXT_FIELDS = (
    "genome_build",
    "disease_class",
    "age_group",
    "cell_state",
    "territory",
    "treatment_phase",
)
_SENSITIVE_KEYS = frozenset({"patient_id", "sample_id", "subject_id", "genotype"})
_SECRET_KEYS = frozenset({"password", "token", "api_key"})


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _sequence(value: Any, *, label: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{label} must be an array")
    return tuple(value)


def _text(value: Any, *, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    return value.strip()


def _required_text(value: Any, *, field: str) -> str:
    return require_non_empty(_text(value, field=field), field)


def _bounded(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ValidationError(f"{field} must be between zero and one")
    return round(number, 9)


def _context_from_key(value: Any, *, field: str) -> ContextFingerprint:
    key = _required_text(value, field=field)
    pieces = tuple(key.split("|"))
    if len(pieces) != len(_CONTEXT_FIELDS) or any(not piece for piece in pieces):
        raise ValidationError(f"{field} must contain six non-empty context components")
    return ContextFingerprint(*pieces)


def _context_from_mapping(value: Mapping[str, Any], *, label: str) -> ContextFingerprint:
    return ContextFingerprint(
        *(_required_text(value.get(field), field=f"{label}.{field}") for field in _CONTEXT_FIELDS)
    )


@dataclass(frozen=True, slots=True)
class ContextFingerprint:
    """Exact context identity used for joins at the data boundary."""

    genome_build: str
    disease_class: str
    age_group: str
    cell_state: str
    territory: str
    treatment_phase: str

    @property
    def key(self) -> str:
        return "|".join(
            (
                self.genome_build,
                self.disease_class,
                self.age_group,
                self.cell_state,
                self.territory,
                self.treatment_phase,
            )
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "genome_build": self.genome_build,
            "disease_class": self.disease_class,
            "age_group": self.age_group,
            "cell_state": self.cell_state,
            "territory": self.territory,
            "treatment_phase": self.treatment_phase,
            "key": self.key,
        }

    @classmethod
    def from_value(cls, value: Any, *, field: str = "context") -> ContextFingerprint:
        if isinstance(value, Mapping):
            return _context_from_mapping(value, label=field)
        return _context_from_key(value, field=field)

    def matches(self, other: ContextFingerprint) -> bool:
        return self == other

    def differing_fields(self, other: ContextFingerprint) -> tuple[str, ...]:
        return tuple(
            field for field in _CONTEXT_FIELDS if getattr(self, field) != getattr(other, field)
        )


@dataclass(frozen=True, slots=True)
class SourceReceipt:
    """Attribution metadata for one public or aggregate source bundle."""

    source_id: str
    record_type: str
    accession: str
    coordinate_system: str
    retrieval_mode: str
    content_address: str
    patient_level_data: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, default_patient_level: bool) -> SourceReceipt:
        data = _mapping(raw, label="source receipt")
        source_id = _required_text(data.get("source_id"), field="source_id")
        record_type = _required_text(data.get("record_type"), field="record_type")
        accession = _required_text(data.get("accession"), field="accession")
        coordinate_system = (
            _text(data.get("coordinate_system", "unspecified"), field="coordinate_system")
            or "unspecified"
        )
        retrieval_mode = _required_text(
            data.get("retrieval_mode", "declared"), field="retrieval_mode"
        )
        patient_level = data.get("patient_level_data", default_patient_level)
        if not isinstance(patient_level, bool):
            raise ValidationError("source receipt patient_level_data must be boolean")
        address = content_hash(
            {
                "source_id": source_id,
                "record_type": record_type,
                "accession": accession,
                "coordinate_system": coordinate_system,
                "retrieval_mode": retrieval_mode,
                "patient_level_data": patient_level,
            }
        )
        return cls(
            source_id,
            record_type,
            accession,
            coordinate_system,
            retrieval_mode,
            address,
            patient_level,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PublicResearchRecord:
    """A normalized public identifier or aggregate measurement record."""

    record_id: str
    kind: PublicRecordKind
    source_id: str
    context: ContextFingerprint
    label: str
    attributes: Mapping[str, Any]
    content_address: str

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        kind: PublicRecordKind,
        source_id: str,
        default_context: ContextFingerprint,
        fallback_id: str,
    ) -> PublicResearchRecord:
        data = _mapping(raw, label=f"{kind.value} record")
        record_id = (
            _text(
                data.get(
                    "record_id",
                    data.get(
                        "id",
                        data.get(
                            "target_id",
                            data.get("claim_id", data.get("experiment_id", data.get("node_id"))),
                        ),
                    ),
                ),
                field="record_id",
            )
            or fallback_id
        )
        label = (
            _text(
                data.get(
                    "title", data.get("name", data.get("gene", data.get("target", record_id)))
                ),
                field="label",
            )
            or record_id
        )
        row_context = data.get("context_key", data.get("context"))
        context = (
            default_context if row_context is None else ContextFingerprint.from_value(row_context)
        )
        attributes = {
            str(key): jsonable(value)
            for key, value in data.items()
            if str(key) not in {"context", "context_key"}
        }
        address = content_hash(
            {
                "record_id": record_id,
                "kind": kind.value,
                "source_id": source_id,
                "context": context.key,
                "attributes": attributes,
            }
        )
        return cls(record_id, kind, source_id, context, label, attributes, address)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """One data-boundary issue with a stable path and severity."""

    code: str
    path: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PublicDataQualityReport:
    """Audit result for a public fixture catalog."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    record_count: int
    counts_by_kind: Mapping[str, int]
    duplicate_ids: tuple[str, ...]
    context_mismatch_ids: tuple[str, ...]
    sensitive_paths: tuple[str, ...]
    issues: tuple[DataQualityIssue, ...]
    state: PublicDataState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == PublicDataState.ACCEPTED and not self.issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        return result


class PublicFixtureCatalog:
    """Index and audit the public records embedded in a frontier fixture."""

    def __init__(
        self,
        *,
        fixture_id: str,
        context: ContextFingerprint,
        receipts: Sequence[SourceReceipt],
        records: Sequence[PublicResearchRecord],
        issues: Sequence[DataQualityIssue] = (),
    ) -> None:
        self.fixture_id = require_non_empty(fixture_id, "fixture_id")
        self.context = context
        self.receipts = tuple(receipts)
        self.records = tuple(records)
        self._initial_issues = tuple(issues)
        self._by_id: dict[str, PublicResearchRecord] = {}
        self._ambiguous_ids: set[str] = set()
        for record in self.records:
            if record.record_id in self._by_id:
                self._ambiguous_ids.add(record.record_id)
                self._by_id.pop(record.record_id, None)
            elif record.record_id not in self._ambiguous_ids:
                self._by_id[record.record_id] = record

    @classmethod
    def from_file(cls, path: str | Path) -> PublicFixtureCatalog:
        fixture_path = Path(path)
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("public fixture must be an object")
        return cls.from_fixture(raw)

    @classmethod
    def from_fixture(cls, raw: Mapping[str, Any]) -> PublicFixtureCatalog:
        data = _mapping(raw, label="public fixture")
        fixture_id = _required_text(data.get("fixture_id"), field="fixture_id")
        context = ContextFingerprint.from_value(data.get("context"))
        provenance = _mapping(data.get("provenance", {}), label="provenance")
        default_patient_level = provenance.get("patient_level_data", True)
        if not isinstance(default_patient_level, bool):
            raise ValidationError("provenance.patient_level_data must be boolean")
        receipts = tuple(
            SourceReceipt.from_mapping(item, default_patient_level=default_patient_level)
            for item in _sequence(data.get("source_receipts", ()), label="source_receipts")
        )
        issues: list[DataQualityIssue] = []
        source_ids = {receipt.source_id for receipt in receipts}
        if not receipts:
            issues.append(
                DataQualityIssue(
                    "no_source_receipts",
                    "source_receipts",
                    "blocking",
                    "public records require at least one declared source receipt",
                )
            )
        if len(source_ids) != len(receipts):
            issues.append(
                DataQualityIssue(
                    "duplicate_source_id",
                    "source_receipts",
                    "blocking",
                    "source IDs must be unique",
                )
            )
        if any(receipt.patient_level_data for receipt in receipts):
            issues.append(
                DataQualityIssue(
                    "patient_level_source",
                    "source_receipts",
                    "blocking",
                    "patient-level source is outside this fixture boundary",
                )
            )
        for index, receipt in enumerate(
            _sequence(data.get("source_receipts", ()), label="source_receipts")
        ):
            cls._scan_for_sensitive(receipt, issues, f"source_receipts[{index}]")
        records: list[PublicResearchRecord] = []
        cls._collect_records(data, context, records)
        for record in records:
            cls._scan_for_sensitive(
                record.attributes,
                issues,
                f"records[{record.record_id}]",
            )
        if not records:
            issues.append(
                DataQualityIssue(
                    "no_public_records",
                    "pipelines",
                    "blocking",
                    "fixture contains no indexable public records",
                )
            )
        known_sources = source_ids
        for index, record in enumerate(records, start=1):
            if record.source_id not in known_sources:
                issues.append(
                    DataQualityIssue(
                        "unknown_source",
                        f"records[{index}].source_id",
                        "blocking",
                        f"record source {record.source_id} has no declared receipt",
                    )
                )
        return cls(
            fixture_id=fixture_id,
            context=context,
            receipts=receipts,
            records=records,
            issues=issues,
        )

    @staticmethod
    def _scan_for_sensitive(value: Any, issues: list[DataQualityIssue], path: str = "") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                lowered = key_text.lower()
                if lowered in _SENSITIVE_KEYS:
                    issues.append(
                        DataQualityIssue(
                            "sensitive_field",
                            child_path,
                            "blocking",
                            "patient or specimen identifier is not permitted",
                        )
                    )
                elif lowered in _SECRET_KEYS or any(token in lowered for token in _SECRET_KEYS):
                    issues.append(
                        DataQualityIssue(
                            "secret_like_field",
                            child_path,
                            "blocking",
                            "secret-like field is not permitted in public data",
                        )
                    )
                PublicFixtureCatalog._scan_for_sensitive(child, issues, child_path)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for index, child in enumerate(value):
                PublicFixtureCatalog._scan_for_sensitive(child, issues, f"{path}[{index}]")

    @classmethod
    def _collect_records(
        cls,
        data: Mapping[str, Any],
        context: ContextFingerprint,
        records: list[PublicResearchRecord],
    ) -> None:
        sources = tuple(data.get("source_receipts", ()))
        source_id = (
            _text(_mapping(sources[0], label="source receipt").get("source_id"), field="source_id")
            if sources
            else "undeclared"
        ) or "undeclared"
        pipelines = _mapping(data.get("pipelines", {}), label="pipelines")
        validation = _mapping(pipelines.get("validation", {}), label="validation pipeline")
        evidence = _mapping(pipelines.get("evidence", {}), label="evidence pipeline")
        workbench = _mapping(pipelines.get("workbench", {}), label="workbench pipeline")
        deployment = _mapping(pipelines.get("deployment", {}), label="deployment pipeline")
        for index, row in enumerate(validation.get("risk_records", ()), start=1):
            records.append(
                PublicResearchRecord.from_mapping(
                    _mapping(row, label="risk record"),
                    kind=PublicRecordKind.TARGET,
                    source_id=source_id,
                    default_context=context,
                    fallback_id=f"target:{index}",
                )
            )
        for index, row in enumerate(validation.get("voi_records", ()), start=1):
            records.append(
                PublicResearchRecord.from_mapping(
                    _mapping(row, label="VOI record"),
                    kind=PublicRecordKind.EXPERIMENT,
                    source_id=source_id,
                    default_context=context,
                    fallback_id=f"experiment:{index}",
                )
            )
        for index, row in enumerate(evidence.get("nodes", ()), start=1):
            records.append(
                PublicResearchRecord.from_mapping(
                    _mapping(row, label="evidence node"),
                    kind=PublicRecordKind.EVIDENCE,
                    source_id=source_id,
                    default_context=context,
                    fallback_id=f"evidence:{index}",
                )
            )
        for index, row in enumerate(evidence.get("claims", ()), start=1):
            records.append(
                PublicResearchRecord.from_mapping(
                    _mapping(row, label="claim record"),
                    kind=PublicRecordKind.CLAIM,
                    source_id=source_id,
                    default_context=context,
                    fallback_id=f"claim:{index}",
                )
            )
        for index, row in enumerate(workbench.get("records", ()), start=1):
            records.append(
                PublicResearchRecord.from_mapping(
                    _mapping(row, label="workbench record"),
                    kind=PublicRecordKind.WORKBENCH,
                    source_id=source_id,
                    default_context=context,
                    fallback_id=f"workbench:{index}",
                )
            )
        for index, row in enumerate(deployment.get("services", ()), start=1):
            records.append(
                PublicResearchRecord.from_mapping(
                    _mapping(row, label="deployment service"),
                    kind=PublicRecordKind.DEPLOYMENT,
                    source_id=source_id,
                    default_context=context,
                    fallback_id=f"service:{index}",
                )
            )

    def audit(self) -> PublicDataQualityReport:
        """Audit duplicates, context, source attribution, and sensitive paths."""

        issues = list(self._initial_issues)
        by_id: defaultdict[tuple[PublicRecordKind, str], list[PublicResearchRecord]] = defaultdict(
            list
        )
        for record in self.records:
            by_id[(record.kind, record.record_id)].append(record)
        duplicate_ids = tuple(
            sorted(
                f"{kind.value}:{record_id}"
                for (kind, record_id), rows in by_id.items()
                if len(rows) > 1
            )
        )
        for record_id in duplicate_ids:
            issues.append(
                DataQualityIssue(
                    "duplicate_record_id",
                    f"records[{record_id}]",
                    "blocking",
                    "record ID is reused within one record family",
                )
            )
        mismatches = tuple(
            sorted(
                {
                    record.record_id
                    for record in self.records
                    if not record.context.matches(self.context)
                }
            )
        )
        for record_id in mismatches:
            issues.append(
                DataQualityIssue(
                    "context_mismatch",
                    f"records[{record_id}].context",
                    "blocking",
                    "record context differs from fixture context",
                )
            )
        sensitive_paths = tuple(
            sorted(
                issue.path
                for issue in issues
                if issue.code in {"sensitive_field", "secret_like_field"}
            )
        )
        counts = Counter(record.kind.value for record in self.records)
        state = PublicDataState.ACCEPTED if not issues else PublicDataState.REVIEW
        return PublicDataQualityReport(
            self.fixture_id,
            self.context.key,
            tuple(sorted(receipt.source_id for receipt in self.receipts)),
            len(self.records),
            dict(sorted(counts.items())),
            duplicate_ids,
            mismatches,
            sensitive_paths,
            tuple(issues),
            state,
            content_hash(
                {
                    "fixture_id": self.fixture_id,
                    "context": self.context.key,
                    "records": self.records,
                    "issues": issues,
                }
            ),
        )

    def records_by_kind(self, kind: PublicRecordKind) -> tuple[PublicResearchRecord, ...]:
        return tuple(record for record in self.records if record.kind == kind)

    def find(self, record_id: str) -> PublicResearchRecord | None:
        if record_id in self._ambiguous_ids:
            return None
        return self._by_id.get(record_id)

    def search_label(
        self, query: str, *, kind: PublicRecordKind | None = None
    ) -> tuple[PublicResearchRecord, ...]:
        query = require_non_empty(query, "query").casefold()
        matches = (
            record
            for record in self.records
            if query in record.label.casefold() and (kind is None or record.kind == kind)
        )
        return tuple(sorted(matches, key=lambda record: (record.kind.value, record.record_id)))

    def source_manifest(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "context": self.context.to_dict(),
            "sources": [receipt.to_dict() for receipt in self.receipts],
            "record_count": len(self.records),
            "record_addresses": [record.content_address for record in self.records],
            "manifest_address": content_hash(
                {
                    "fixture_id": self.fixture_id,
                    "context": self.context.key,
                    "sources": self.receipts,
                    "records": self.records,
                }
            ),
        }


def audit_public_fixture(path: str | Path) -> PublicDataQualityReport:
    """Load and audit one public fixture from disk."""

    return PublicFixtureCatalog.from_file(path).audit()


__all__ = [
    "ContextFingerprint",
    "DataQualityIssue",
    "PublicDataQualityReport",
    "PublicDataState",
    "PublicFixtureCatalog",
    "PublicRecordKind",
    "PublicResearchRecord",
    "SourceReceipt",
    "audit_public_fixture",
]
