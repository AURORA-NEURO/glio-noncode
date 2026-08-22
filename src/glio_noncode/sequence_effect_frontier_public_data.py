"""Public aggregate fixture for the Domain 06 sequence-effect frontier.

The fixture is intentionally small enough to replay in tests while retaining
the operational boundaries required by the sequence plane: exact context,
public aggregate sources, deterministic identities, explicit controls, and no
promotion of model deltas into clinical claims.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

SEQUENCE_EFFECT_FIXTURE_VERSION = "2026.08.d06-c01-c04.v1"
SEQUENCE_EFFECT_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|bulk_tumor|regulatory_sequence|baseline"
SEQUENCE_EFFECT_BOUNDARY = "public_aggregate_non_patient"
SEQUENCE_EFFECT_POSITIVE_COUNT = 4
SEQUENCE_EFFECT_CONTROL_COUNT = 12
SEQUENCE_EFFECT_SOURCE_COUNT = 4


class SequenceEffectOperation(StrEnum):
    """The four capabilities covered by this frontier package."""

    CONTEXT_ENCODING = "context_encoding"
    FOUNDATION_MODEL = "foundation_model_adapter"
    LONG_CONTEXT = "long_context_variant_effect"
    REGULATORY_ENSEMBLE = "regulatory_track_delta_ensemble"


class SequenceEffectRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class SequenceEffectState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class SequenceEffectSourceReceipt:
    source_id: str
    uri: str
    source_version: str
    checksum: str
    context_key: str
    public_aggregate: bool = True
    patient_level: bool = False
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.source_version.strip():
            raise ValidationError("source identity and version are required")
        if not self.uri.startswith("https://"):
            raise ValidationError("source URI must use https")
        if not self.checksum.strip() or not self.context_key.strip():
            raise ValidationError("source checksum and context are required")
        if not self.public_aggregate or self.patient_level:
            raise ValidationError("fixture sources must be public aggregate data")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "source_id": self.source_id,
                        "uri": self.uri,
                        "source_version": self.source_version,
                        "checksum": self.checksum,
                        "context_key": self.context_key,
                        "public_aggregate": self.public_aggregate,
                        "patient_level": self.patient_level,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectRecord:
    record_id: str
    operation: SequenceEffectOperation
    role: SequenceEffectRole
    expected_state: SequenceEffectState
    expected_issue_codes: tuple[str, ...]
    payload: Mapping[str, Any]
    source_ids: tuple[str, ...]
    context_key: str = SEQUENCE_EFFECT_CONTEXT_KEY
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.source_ids:
            raise ValidationError("record identity and source IDs are required")
        if self.context_key != SEQUENCE_EFFECT_CONTEXT_KEY:
            raise ValidationError("record context is outside the fixture boundary")
        if not isinstance(self.payload, Mapping) or not self.payload:
            raise ValidationError("record payload must be a non-empty object")
        if any(
            key.lower() in {"subject", "patient", "sample_id", "donor_id"} for key in self.payload
        ):
            raise ValidationError("subject-level fields are not permitted in public fixture")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "expected_state": self.expected_state,
                        "expected_issue_codes": self.expected_issue_codes,
                        "payload": self.payload,
                        "source_ids": self.source_ids,
                        "context_key": self.context_key,
                    }
                ),
            )

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        data = {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "role": self.role.value,
            "expected_state": self.expected_state.value,
            "expected_issue_codes": list(self.expected_issue_codes),
            "source_ids": list(self.source_ids),
            "context_key": self.context_key,
            "content_address": self.content_address,
        }
        if include_payload:
            data["payload"] = jsonable(self.payload)
        return data


@dataclass(frozen=True, slots=True)
class SequenceEffectFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[SequenceEffectSourceReceipt, ...]
    records: tuple[SequenceEffectRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != SEQUENCE_EFFECT_FIXTURE_VERSION:
            raise ValidationError("unsupported sequence-effect fixture version")
        if self.context_key != SEQUENCE_EFFECT_CONTEXT_KEY:
            raise ValidationError("fixture context does not match the checked-in boundary")
        if self.evidence_boundary != SEQUENCE_EFFECT_BOUNDARY:
            raise ValidationError("fixture evidence boundary is not public aggregate data")
        if len(self.sources) != SEQUENCE_EFFECT_SOURCE_COUNT:
            raise ValidationError("fixture requires four independent source receipts")
        if len(self.records) != SEQUENCE_EFFECT_POSITIVE_COUNT + SEQUENCE_EFFECT_CONTROL_COUNT:
            raise ValidationError("fixture requires four positive and twelve control records")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "fixture_version": self.fixture_version,
                        "context_key": self.context_key,
                        "evidence_boundary": self.evidence_boundary,
                        "sources": tuple(source.to_dict() for source in self.sources),
                        "records": tuple(record.to_dict() for record in self.records),
                    }
                ),
            )

    @property
    def positive_records(self) -> tuple[SequenceEffectRecord, ...]:
        return tuple(
            record for record in self.records if record.role is SequenceEffectRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[SequenceEffectRecord, ...]:
        return tuple(record for record in self.records if record.role is SequenceEffectRole.CONTROL)

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "evidence_boundary": self.evidence_boundary,
            "sources": [source.to_dict() for source in self.sources],
            "records": [record.to_dict(include_payload=include_payload) for record in self.records],
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.detail.strip():
            raise ValidationError("data checks require an ID and detail")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"check_id": self.check_id, "passed": self.passed, "detail": self.detail}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectDataAudit:
    accepted: bool
    checks: tuple[SequenceEffectDataCheck, ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("data audit requires checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "check_count": len(self.checks),
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [check.to_dict() for check in self.checks],
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectCatalog:
    fixture_id: str
    context_key: str
    operations: tuple[str, ...]
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, uri: str, version: str) -> SequenceEffectSourceReceipt:
    return SequenceEffectSourceReceipt(
        source_id=source_id,
        uri=uri,
        source_version=version,
        checksum=content_hash({"source_id": source_id, "version": version}),
        context_key=SEQUENCE_EFFECT_CONTEXT_KEY,
    )


def _record(
    record_id: str,
    operation: SequenceEffectOperation,
    role: SequenceEffectRole,
    state: SequenceEffectState,
    issues: tuple[str, ...],
    payload: Mapping[str, Any],
    *source_ids: str,
) -> SequenceEffectRecord:
    return SequenceEffectRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        expected_state=state,
        expected_issue_codes=issues,
        payload=payload,
        source_ids=tuple(source_ids),
    )


_MODEL_HEADER = (
    "model_id\tmodel_version\tvariant_id\treference_score\talternate_score\tcontext_length"
)
_MODEL_HEADER_UNCERTAINTY = _MODEL_HEADER + "\tuncertainty"
_MODEL_HEADER_DELTA = _MODEL_HEADER.replace("\tcontext_length", "\tdelta\tcontext_length")


def default_sequence_effect_fixture() -> SequenceEffectFixture:
    """Return the deterministic four-positive/twelve-control public fixture."""

    sources = (
        _source("seq-refseq", "https://www.ncbi.nlm.nih.gov/refseq/", "2026-01"),
        _source("seq-ensembl", "https://www.ensembl.org/info/data/", "release-114"),
        _source("seq-model-card", "https://example.org/sequence-model-card", "v1"),
        _source("seq-regulatory-track", "https://example.org/regulatory-track", "2026.1"),
    )
    records = (
        _record(
            "C01-POS-001",
            SequenceEffectOperation.CONTEXT_ENCODING,
            SequenceEffectRole.POSITIVE,
            SequenceEffectState.SUPPORTED,
            (),
            {
                "sequence_id": "aggregate-context-1",
                "source_id": "seq-refseq",
                "sequence": "ACGTACGTACGTACGT",
                "kmer_size": 3,
            },
            "seq-refseq",
        ),
        _record(
            "C01-CTRL-001",
            SequenceEffectOperation.CONTEXT_ENCODING,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.INVALID,
            ("invalid_alphabet",),
            {
                "sequence_id": "control-invalid",
                "source_id": "seq-refseq",
                "sequence": "ACGTX",
                "kmer_size": 3,
            },
            "seq-refseq",
        ),
        _record(
            "C01-CTRL-002",
            SequenceEffectOperation.CONTEXT_ENCODING,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.ABSTAINED,
            ("empty_sequence",),
            {
                "sequence_id": "control-empty",
                "source_id": "seq-refseq",
                "sequence": "",
                "kmer_size": 3,
            },
            "seq-refseq",
        ),
        _record(
            "C01-CTRL-003",
            SequenceEffectOperation.CONTEXT_ENCODING,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.PARTIAL,
            ("ambiguous_bases",),
            {
                "sequence_id": "control-ambiguous",
                "source_id": "seq-refseq",
                "sequence": "NNNNACGT",
                "kmer_size": 3,
            },
            "seq-refseq",
        ),
        _record(
            "C02-POS-001",
            SequenceEffectOperation.FOUNDATION_MODEL,
            SequenceEffectRole.POSITIVE,
            SequenceEffectState.SUPPORTED,
            (),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER
                + "\nm1\t1.0\tvar-1\t0.20\t0.80\t512\nm2\t1.1\tvar-1\t0.25\t0.75\t512",
            },
            "seq-model-card",
        ),
        _record(
            "C02-CTRL-001",
            SequenceEffectOperation.FOUNDATION_MODEL,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.INVALID,
            ("invalid_effect_row",),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER + "\nm1\t1.0\tvar-2\tbad\t0.80\t512",
            },
            "seq-model-card",
        ),
        _record(
            "C02-CTRL-002",
            SequenceEffectOperation.FOUNDATION_MODEL,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.INVALID,
            ("missing_model_id",),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER_UNCERTAINTY + "\t\tvar-3\t0.20\t0.80\t512\t0.2",
            },
            "seq-model-card",
        ),
        _record(
            "C02-CTRL-003",
            SequenceEffectOperation.FOUNDATION_MODEL,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.INVALID,
            ("delta_mismatch",),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER_DELTA + "\nm1\t1.0\tvar-4\t0.20\t0.80\t0.10\t512",
            },
            "seq-model-card",
        ),
        _record(
            "C03-POS-001",
            SequenceEffectOperation.LONG_CONTEXT,
            SequenceEffectRole.POSITIVE,
            SequenceEffectState.SUPPORTED,
            (),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER + "\nm-long\t2.0\tvar-5\t0.10\t0.70\t2048",
            },
            "seq-model-card",
        ),
        _record(
            "C03-CTRL-001",
            SequenceEffectOperation.LONG_CONTEXT,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.INVALID,
            ("context_too_short",),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER + "\nm-short\t2.0\tvar-6\t0.10\t0.70\t512",
            },
            "seq-model-card",
        ),
        _record(
            "C03-CTRL-002",
            SequenceEffectOperation.LONG_CONTEXT,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.INVALID,
            ("invalid_effect_row",),
            {
                "source_id": "seq-model-card",
                "text": _MODEL_HEADER + "\nm-long\t2.0\tvar-7\t0.10\tbad\t2048",
            },
            "seq-model-card",
        ),
        _record(
            "C03-CTRL-003",
            SequenceEffectOperation.LONG_CONTEXT,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.ABSTAINED,
            ("empty_effect_input",),
            {"source_id": "seq-model-card", "text": ""},
            "seq-model-card",
        ),
        _record(
            "C04-POS-001",
            SequenceEffectOperation.REGULATORY_ENSEMBLE,
            SequenceEffectRole.POSITIVE,
            SequenceEffectState.SUPPORTED,
            (),
            {
                "observations": [
                    {
                        "observation_id": "o1",
                        "model_id": "m1",
                        "model_version": "1",
                        "variant_id": "var-8",
                        "reference_score": 0.1,
                        "alternate_score": 0.8,
                        "context_length": 1024,
                        "source_id": "seq-regulatory-track",
                        "raw_hash": "r1",
                    },
                    {
                        "observation_id": "o2",
                        "model_id": "m2",
                        "model_version": "1",
                        "variant_id": "var-8",
                        "reference_score": 0.2,
                        "alternate_score": 0.85,
                        "context_length": 1024,
                        "source_id": "seq-regulatory-track",
                        "raw_hash": "r2",
                    },
                ]
            },
            "seq-regulatory-track",
        ),
        _record(
            "C04-CTRL-001",
            SequenceEffectOperation.REGULATORY_ENSEMBLE,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.PARTIAL,
            ("single_model",),
            {
                "observations": [
                    {
                        "observation_id": "o3",
                        "model_id": "m1",
                        "model_version": "1",
                        "variant_id": "var-9",
                        "reference_score": 0.1,
                        "alternate_score": 0.8,
                        "context_length": 1024,
                        "source_id": "seq-regulatory-track",
                        "raw_hash": "r3",
                    }
                ]
            },
            "seq-regulatory-track",
        ),
        _record(
            "C04-CTRL-002",
            SequenceEffectOperation.REGULATORY_ENSEMBLE,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.AMBIGUOUS,
            ("model_disagreement",),
            {
                "observations": [
                    {
                        "observation_id": "o4",
                        "model_id": "m1",
                        "model_version": "1",
                        "variant_id": "var-10",
                        "reference_score": 0.1,
                        "alternate_score": 0.9,
                        "context_length": 1024,
                        "source_id": "seq-regulatory-track",
                        "raw_hash": "r4",
                    },
                    {
                        "observation_id": "o5",
                        "model_id": "m2",
                        "model_version": "1",
                        "variant_id": "var-10",
                        "reference_score": 0.8,
                        "alternate_score": 0.2,
                        "context_length": 1024,
                        "source_id": "seq-regulatory-track",
                        "raw_hash": "r5",
                    },
                ]
            },
            "seq-regulatory-track",
        ),
        _record(
            "C04-CTRL-003",
            SequenceEffectOperation.REGULATORY_ENSEMBLE,
            SequenceEffectRole.CONTROL,
            SequenceEffectState.ABSTAINED,
            ("no_observations",),
            {"observations": []},
            "seq-regulatory-track",
        ),
    )
    return SequenceEffectFixture(
        fixture_id="sequence-effect-frontier-public-v1",
        fixture_version=SEQUENCE_EFFECT_FIXTURE_VERSION,
        context_key=SEQUENCE_EFFECT_CONTEXT_KEY,
        evidence_boundary=SEQUENCE_EFFECT_BOUNDARY,
        sources=sources,
        records=records,
    )


def build_sequence_effect_catalog(fixture: SequenceEffectFixture) -> SequenceEffectCatalog:
    source_ids = tuple(source.source_id for source in fixture.sources)
    operations = tuple(operation.value for operation in SequenceEffectOperation)
    return SequenceEffectCatalog(
        fixture_id=fixture.fixture_id,
        context_key=fixture.context_key,
        operations=operations,
        source_ids=source_ids,
        record_ids=tuple(record.record_id for record in fixture.records),
        content_address=content_hash(
            {
                "fixture_id": fixture.fixture_id,
                "operations": operations,
                "source_ids": source_ids,
                "record_ids": tuple(record.record_id for record in fixture.records),
            }
        ),
    )


def audit_sequence_effect_data(fixture: SequenceEffectFixture) -> SequenceEffectDataAudit:
    source_ids = {source.source_id for source in fixture.sources}
    checks = (
        SequenceEffectDataCheck(
            "fixture-version",
            fixture.fixture_version == SEQUENCE_EFFECT_FIXTURE_VERSION,
            "fixture version is locked",
        ),
        SequenceEffectDataCheck(
            "fixture-context",
            fixture.context_key == SEQUENCE_EFFECT_CONTEXT_KEY,
            "fixture context is exact",
        ),
        SequenceEffectDataCheck(
            "public-boundary",
            fixture.evidence_boundary == SEQUENCE_EFFECT_BOUNDARY,
            "data boundary is public aggregate",
        ),
        SequenceEffectDataCheck(
            "source-count", len(fixture.sources) == 4, "four independent sources are declared"
        ),
        SequenceEffectDataCheck(
            "source-closure",
            all(set(record.source_ids) <= source_ids for record in fixture.records),
            "every record source is declared",
        ),
        SequenceEffectDataCheck(
            "source-addresses",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "source receipts are addressed",
        ),
        SequenceEffectDataCheck(
            "record-addresses",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "records are addressed",
        ),
        SequenceEffectDataCheck(
            "record-ids-unique",
            len({record.record_id for record in fixture.records}) == len(fixture.records),
            "record identities are unique",
        ),
        SequenceEffectDataCheck(
            "positive-controls",
            (len(fixture.positive_records), len(fixture.control_records)) == (4, 12),
            "positive/control balance is explicit",
        ),
        SequenceEffectDataCheck(
            "no-subject-identifiers",
            not any(
                any(
                    key.lower() in {"subject", "patient", "sample_id", "donor_id"}
                    for key in record.payload
                )
                for record in fixture.records
            ),
            "payloads contain no subject-level fields",
        ),
        SequenceEffectDataCheck(
            "operation-coverage",
            {record.operation for record in fixture.records} == set(SequenceEffectOperation),
            "all four operations are represented",
        ),
        SequenceEffectDataCheck(
            "context-closure",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "records retain the fixture context",
        ),
    )
    return SequenceEffectDataAudit(
        accepted=all(check.passed for check in checks),
        checks=checks,
        fixture_id=fixture.fixture_id,
    )


def load_sequence_effect_fixture(path: str | Path) -> SequenceEffectFixture:
    """Load a sanitized fixture mapping; payloads are retained for execution only."""

    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"unable to load sequence-effect fixture: {path}") from exc
    if not isinstance(raw, Mapping):
        raise ValidationError("sequence-effect fixture must be an object")
    source_rows = raw.get("sources", [])
    record_rows = raw.get("records", [])
    if not isinstance(source_rows, list) or not isinstance(record_rows, list):
        raise ValidationError("fixture sources and records must be arrays")
    sources = tuple(SequenceEffectSourceReceipt(**dict(row)) for row in source_rows)
    records = tuple(
        SequenceEffectRecord(
            record_id=str(row["record_id"]),
            operation=SequenceEffectOperation(str(row["operation"])),
            role=SequenceEffectRole(str(row["role"])),
            expected_state=SequenceEffectState(str(row["expected_state"])),
            expected_issue_codes=tuple(str(item) for item in row.get("expected_issue_codes", [])),
            payload=dict(row.get("payload", {})),
            source_ids=tuple(str(item) for item in row.get("source_ids", [])),
            context_key=str(row.get("context_key", SEQUENCE_EFFECT_CONTEXT_KEY)),
            content_address=str(row.get("content_address", "")),
        )
        for row in record_rows
    )
    return SequenceEffectFixture(
        fixture_id=str(raw["fixture_id"]),
        fixture_version=str(raw["fixture_version"]),
        context_key=str(raw["context_key"]),
        evidence_boundary=str(raw["evidence_boundary"]),
        sources=sources,
        records=records,
        content_address=str(raw.get("content_address", "")),
    )


__all__ = [
    "SEQUENCE_EFFECT_BOUNDARY",
    "SEQUENCE_EFFECT_CONTEXT_KEY",
    "SEQUENCE_EFFECT_CONTROL_COUNT",
    "SEQUENCE_EFFECT_FIXTURE_VERSION",
    "SEQUENCE_EFFECT_POSITIVE_COUNT",
    "SEQUENCE_EFFECT_SOURCE_COUNT",
    "SequenceEffectCatalog",
    "SequenceEffectDataAudit",
    "SequenceEffectDataCheck",
    "SequenceEffectFixture",
    "SequenceEffectOperation",
    "SequenceEffectRecord",
    "SequenceEffectRole",
    "SequenceEffectSourceReceipt",
    "SequenceEffectState",
    "audit_sequence_effect_data",
    "build_sequence_effect_catalog",
    "default_sequence_effect_fixture",
    "load_sequence_effect_fixture",
]
