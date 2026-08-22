"""Public aggregate data contracts for Domain 06 C05-C08.

The motif-grammar tranche is deliberately separated from the low-level
consensus scanners.  This module supplies a closed fixture with source
receipts, operation records, expected boundary states, and deterministic
content addresses.  It is an aggregate mechanics fixture: it exercises
sequence comparison, motif catalog handling, spacing rules, and cooperative
interaction paths without representing a person or a clinical conclusion.
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

SEQUENCE_GRAMMAR_FIXTURE_VERSION = "2026.08.d06-c05-c08.v1"
SEQUENCE_GRAMMAR_CONTEXT_KEY = (
    "GRCh38|diffuse_glioma|adult|bulk_tumor|cis_regulatory_grammar|baseline"
)
SEQUENCE_GRAMMAR_BOUNDARY = "public_aggregate_non_patient"
SEQUENCE_GRAMMAR_POSITIVE_COUNT = 4
SEQUENCE_GRAMMAR_CONTROL_COUNT = 12
SEQUENCE_GRAMMAR_SOURCE_COUNT = 4


class SequenceGrammarOperation(StrEnum):
    """The four Domain 06 beta operations."""

    MOTIF_DISRUPTION = "motif_disruption"
    MOTIF_CREATION = "motif_creation"
    SPACING_GRAMMAR = "motif_spacing_grammar"
    COOPERATIVE_GRAMMAR = "cooperative_tf_grammar"


class SequenceGrammarRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class SequenceGrammarState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class SequenceGrammarSourceReceipt:
    """A public aggregate source with a reproducible receipt."""

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
class SequenceGrammarRecord:
    """One positive or control operation with its expected boundary state."""

    record_id: str
    operation: SequenceGrammarOperation
    role: SequenceGrammarRole
    expected_state: SequenceGrammarState
    expected_issue_codes: tuple[str, ...]
    payload: Mapping[str, Any]
    source_ids: tuple[str, ...]
    context_key: str = SEQUENCE_GRAMMAR_CONTEXT_KEY
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.source_ids:
            raise ValidationError("record identity and source IDs are required")
        if self.context_key != SEQUENCE_GRAMMAR_CONTEXT_KEY:
            raise ValidationError("record context is outside the fixture boundary")
        if not isinstance(self.payload, Mapping) or not self.payload:
            raise ValidationError("record payload must be a non-empty object")
        forbidden_keys = {"subject", "patient", "sample_id", "donor_id", "participant_id"}
        if any(str(key).lower() in forbidden_keys for key in self.payload):
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
        result: dict[str, Any] = {
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
            result["payload"] = jsonable(self.payload)
        return result


@dataclass(frozen=True, slots=True)
class SequenceGrammarFixture:
    """Closed public aggregate fixture for C05-C08."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[SequenceGrammarSourceReceipt, ...]
    records: tuple[SequenceGrammarRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != SEQUENCE_GRAMMAR_FIXTURE_VERSION:
            raise ValidationError("unsupported sequence-grammar fixture version")
        if self.context_key != SEQUENCE_GRAMMAR_CONTEXT_KEY:
            raise ValidationError("fixture context does not match the checked-in boundary")
        if self.evidence_boundary != SEQUENCE_GRAMMAR_BOUNDARY:
            raise ValidationError("fixture evidence boundary is not public aggregate data")
        if len(self.sources) != SEQUENCE_GRAMMAR_SOURCE_COUNT:
            raise ValidationError("fixture requires four independent source receipts")
        if len(self.records) != SEQUENCE_GRAMMAR_POSITIVE_COUNT + SEQUENCE_GRAMMAR_CONTROL_COUNT:
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
    def positive_records(self) -> tuple[SequenceGrammarRecord, ...]:
        return tuple(
            record for record in self.records if record.role is SequenceGrammarRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[SequenceGrammarRecord, ...]:
        return tuple(
            record for record in self.records if record.role is SequenceGrammarRole.CONTROL
        )

    def operation_records(
        self, operation: SequenceGrammarOperation
    ) -> tuple[SequenceGrammarRecord, ...]:
        return tuple(record for record in self.records if record.operation is operation)

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
class SequenceGrammarDataCheck:
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
class SequenceGrammarDataAudit:
    accepted: bool
    checks: tuple[SequenceGrammarDataCheck, ...]
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
class SequenceGrammarCatalog:
    fixture_id: str
    context_key: str
    operations: tuple[str, ...]
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, uri: str, version: str) -> SequenceGrammarSourceReceipt:
    return SequenceGrammarSourceReceipt(
        source_id=source_id,
        uri=uri,
        source_version=version,
        checksum=content_hash({"source_id": source_id, "version": version}),
        context_key=SEQUENCE_GRAMMAR_CONTEXT_KEY,
    )


def _record(
    record_id: str,
    operation: SequenceGrammarOperation,
    role: SequenceGrammarRole,
    state: SequenceGrammarState,
    issue_codes: tuple[str, ...],
    payload: Mapping[str, Any],
    *source_ids: str,
) -> SequenceGrammarRecord:
    return SequenceGrammarRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        expected_state=state,
        expected_issue_codes=issue_codes,
        payload=payload,
        source_ids=tuple(source_ids),
    )


def _motif(motif_id: str, name: str, consensus: str) -> dict[str, Any]:
    return {
        "motif_id": motif_id,
        "name": name,
        "consensus": consensus,
        "source_id": "jaspar-aggregate",
        "source_version": "2026.1",
        "threshold": 1.0,
        "strand_aware": True,
    }


def _hit(motif_id: str, start: int, end: int, strand: str = "+") -> dict[str, Any]:
    return {
        "motif_id": motif_id,
        "motif_name": motif_id,
        "start": start,
        "end": end,
        "strand": strand,
        "matched_sequence": "ACGT",
        "score": 1.0,
        "source_id": "jaspar-aggregate",
        "source_version": "2026.1",
    }


def default_sequence_grammar_fixture() -> SequenceGrammarFixture:
    """Build the deterministic four-positive/twelve-control fixture."""

    sources = (
        _source("jaspar-aggregate", "https://jaspar.genereg.net/", "2026.1"),
        _source("encode-cis-regulatory", "https://www.encodeproject.org/", "2025.4"),
        _source("hocomoco-motif-set", "https://hocomoco11.autosome.org/", "11.0"),
        _source("grammar-benchmark", "https://www.ncbi.nlm.nih.gov/pmc/", "aggregate-2026.1"),
    )
    gata = _motif("TF:GATA", "GATA factor", "GATA")
    acgt = _motif("TF:ACGT", "ACGT factor", "ACGT")
    records = (
        _record(
            "C05-POS-001",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarRole.POSITIVE,
            SequenceGrammarState.SUPPORTED,
            ("motif_loss",),
            {
                "variant_id": "aggregate-disruption-1",
                "reference": "TTTGATATTT",
                "alternate": "TTTGCTATTT",
                "window_start": 101,
                "motifs": [gata, acgt],
                "context_key": SEQUENCE_GRAMMAR_CONTEXT_KEY,
            },
            "jaspar-aggregate",
            "encode-cis-regulatory",
        ),
        _record(
            "C05-CTRL-001",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.INVALID,
            ("invalid_sequence_alphabet",),
            {
                "variant_id": "control-disruption-alphabet",
                "reference": "TTTGATXTTT",
                "alternate": "TTTGCTATTT",
                "window_start": 101,
                "motifs": [gata],
            },
            "jaspar-aggregate",
        ),
        _record(
            "C05-CTRL-002",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("empty_sequence_window",),
            {
                "variant_id": "control-disruption-empty",
                "reference": "",
                "alternate": "",
                "motifs": [gata],
            },
            "jaspar-aggregate",
        ),
        _record(
            "C05-CTRL-003",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("empty_motif_catalog",),
            {
                "variant_id": "control-disruption-catalog",
                "reference": "TTTGATATTT",
                "alternate": "TTTGCTATTT",
                "motifs": [],
            },
            "jaspar-aggregate",
        ),
        _record(
            "C06-POS-001",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarRole.POSITIVE,
            SequenceGrammarState.SUPPORTED,
            ("motif_gain",),
            {
                "variant_id": "aggregate-creation-1",
                "reference": "TTTCCCCAAA",
                "alternate": "TTTGATAAAA",
                "window_start": 201,
                "motifs": [gata],
                "context_key": SEQUENCE_GRAMMAR_CONTEXT_KEY,
            },
            "jaspar-aggregate",
            "encode-cis-regulatory",
        ),
        _record(
            "C06-CTRL-001",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.INVALID,
            ("invalid_sequence_alphabet",),
            {
                "variant_id": "control-creation-alphabet",
                "reference": "TTTCCCCAAA",
                "alternate": "TTTGATXAAA",
                "motifs": [gata],
            },
            "jaspar-aggregate",
        ),
        _record(
            "C06-CTRL-002",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("empty_sequence_window",),
            {
                "variant_id": "control-creation-empty",
                "reference": "",
                "alternate": "",
                "motifs": [gata],
            },
            "jaspar-aggregate",
        ),
        _record(
            "C06-CTRL-003",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("empty_motif_catalog",),
            {
                "variant_id": "control-creation-catalog",
                "reference": "TTTCCCCAAA",
                "alternate": "TTTGATAAAA",
                "motifs": [],
            },
            "jaspar-aggregate",
        ),
        _record(
            "C07-POS-001",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarRole.POSITIVE,
            SequenceGrammarState.SUPPORTED,
            ("compatible_spacing",),
            {
                "context_key": SEQUENCE_GRAMMAR_CONTEXT_KEY,
                "hits": [_hit("TF:GATA", 10, 13), _hit("TF:ACGT", 22, 25)],
                "rules": [
                    {
                        "rule_id": "enhancer-pair-1",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "minimum_spacing": 6,
                        "maximum_spacing": 10,
                        "allowed_orientations": ["same"],
                        "source_id": "grammar-benchmark",
                        "source_version": "aggregate-2026.1",
                    }
                ],
            },
            "grammar-benchmark",
            "jaspar-aggregate",
        ),
        _record(
            "C07-CTRL-001",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("empty_hit_set",),
            {
                "context_key": SEQUENCE_GRAMMAR_CONTEXT_KEY,
                "hits": [],
                "rules": [
                    {
                        "rule_id": "empty-hit-rule",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "minimum_spacing": 1,
                        "maximum_spacing": 20,
                    }
                ],
            },
            "grammar-benchmark",
        ),
        _record(
            "C07-CTRL-002",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("unmatched_rule",),
            {
                "context_key": SEQUENCE_GRAMMAR_CONTEXT_KEY,
                "hits": [_hit("TF:GATA", 10, 13), _hit("TF:ACGT", 22, 25)],
                "rules": [
                    {
                        "rule_id": "too-close-rule",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "minimum_spacing": 0,
                        "maximum_spacing": 2,
                    }
                ],
            },
            "grammar-benchmark",
        ),
        _record(
            "C07-CTRL-003",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.INVALID,
            ("invalid_hit",),
            {
                "context_key": SEQUENCE_GRAMMAR_CONTEXT_KEY,
                "hits": [{"motif_id": "TF:GATA", "start": 0, "end": 3}],
                "rules": [],
            },
            "grammar-benchmark",
        ),
        _record(
            "C08-POS-001",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarRole.POSITIVE,
            SequenceGrammarState.SUPPORTED,
            ("interaction_supported",),
            {
                "sequence_id": "aggregate-cooperative-1",
                "sequence": "ACGT" * 16,
                "model_id": "grammar-model-aggregate",
                "model_version": "2.1",
                "baseline": 0.15,
                "hits": [_hit("TF:GATA", 10, 13), _hit("TF:ACGT", 22, 25)],
                "interactions": [
                    {
                        "interaction_id": "pair-activation",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "weight": 0.7,
                        "maximum_spacing": 10,
                        "required": True,
                        "source_id": "grammar-benchmark",
                        "source_version": "aggregate-2026.1",
                    }
                ],
            },
            "grammar-benchmark",
            "hocomoco-motif-set",
        ),
        _record(
            "C08-CTRL-001",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("missing_required_interaction",),
            {
                "sequence_id": "control-cooperative-missing",
                "sequence": "ACGT" * 16,
                "model_id": "grammar-model-aggregate",
                "model_version": "2.1",
                "hits": [_hit("TF:GATA", 10, 13)],
                "interactions": [
                    {
                        "interaction_id": "pair-required",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "weight": 0.7,
                        "maximum_spacing": 10,
                        "required": True,
                    }
                ],
            },
            "grammar-benchmark",
        ),
        _record(
            "C08-CTRL-002",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.ABSTAINED,
            ("empty_interaction_catalog",),
            {
                "sequence_id": "control-cooperative-empty",
                "sequence": "ACGT" * 16,
                "model_id": "grammar-model-aggregate",
                "model_version": "2.1",
                "hits": [_hit("TF:GATA", 10, 13)],
                "interactions": [],
            },
            "grammar-benchmark",
        ),
        _record(
            "C08-CTRL-003",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarRole.CONTROL,
            SequenceGrammarState.INVALID,
            ("invalid_sequence_alphabet",),
            {
                "sequence_id": "control-cooperative-alphabet",
                "sequence": "ACGTX",
                "model_id": "grammar-model-aggregate",
                "model_version": "2.1",
                "hits": [_hit("TF:GATA", 1, 4)],
                "interactions": [],
            },
            "grammar-benchmark",
        ),
    )
    return SequenceGrammarFixture(
        fixture_id="sequence-grammar-public-aggregate",
        fixture_version=SEQUENCE_GRAMMAR_FIXTURE_VERSION,
        context_key=SEQUENCE_GRAMMAR_CONTEXT_KEY,
        evidence_boundary=SEQUENCE_GRAMMAR_BOUNDARY,
        sources=sources,
        records=records,
    )


def build_sequence_grammar_catalog(fixture: SequenceGrammarFixture) -> SequenceGrammarCatalog:
    """Index operations, sources, records, and declared issue vocabulary."""

    issue_codes = tuple(
        sorted({code for record in fixture.records for code in record.expected_issue_codes})
    )
    return SequenceGrammarCatalog(
        fixture_id=fixture.fixture_id,
        context_key=fixture.context_key,
        operations=tuple(sorted(operation.value for operation in SequenceGrammarOperation)),
        source_ids=tuple(sorted(source.source_id for source in fixture.sources)),
        record_ids=tuple(record.record_id for record in fixture.records),
        issue_codes=issue_codes,
        content_address=content_hash(
            {
                "fixture_id": fixture.fixture_id,
                "context_key": fixture.context_key,
                "operations": tuple(
                    sorted(operation.value for operation in SequenceGrammarOperation)
                ),
                "source_ids": tuple(sorted(source.source_id for source in fixture.sources)),
                "record_ids": tuple(record.record_id for record in fixture.records),
                "issue_codes": issue_codes,
            }
        ),
    )


def audit_sequence_grammar_data(fixture: SequenceGrammarFixture) -> SequenceGrammarDataAudit:
    """Audit fixture closure before any operation is executed."""

    checks: list[SequenceGrammarDataCheck] = []
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.version",
            fixture.fixture_version == SEQUENCE_GRAMMAR_FIXTURE_VERSION,
            "version is locked",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.context",
            fixture.context_key == SEQUENCE_GRAMMAR_CONTEXT_KEY,
            "context is exact",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.boundary",
            fixture.evidence_boundary == SEQUENCE_GRAMMAR_BOUNDARY,
            "boundary is aggregate-only",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.sources", len(fixture.sources) == 4, "four sources are present"
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.records", len(fixture.records) == 16, "sixteen records are present"
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.positive_count",
            len(fixture.positive_records) == 4,
            "four positive records are present",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "fixture.control_count",
            len(fixture.control_records) == 12,
            "twelve controls are present",
        )
    )
    source_ids = [source.source_id for source in fixture.sources]
    checks.append(
        SequenceGrammarDataCheck(
            "sources.unique", len(set(source_ids)) == len(source_ids), "source IDs are unique"
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "sources.public",
            all(source.public_aggregate and not source.patient_level for source in fixture.sources),
            "all sources are aggregate",
        )
    )
    record_ids = [record.record_id for record in fixture.records]
    checks.append(
        SequenceGrammarDataCheck(
            "records.unique", len(set(record_ids)) == len(record_ids), "record IDs are unique"
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "records.closed_operations",
            {record.operation for record in fixture.records} == set(SequenceGrammarOperation),
            "all operations are represented",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "records.source_links",
            all(set(record.source_ids) <= set(source_ids) for record in fixture.records),
            "record source links resolve",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "records.control_paths",
            all(record.expected_issue_codes for record in fixture.control_records),
            "every control declares a boundary path",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "records.addressed",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "records are content addressed",
        )
    )
    checks.append(
        SequenceGrammarDataCheck(
            "sources.addressed",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "sources are content addressed",
        )
    )
    accepted = all(check.passed for check in checks)
    return SequenceGrammarDataAudit(accepted, tuple(checks), fixture.fixture_id)


def load_sequence_grammar_fixture(path: str | Path) -> SequenceGrammarFixture:
    """Load a complete fixture JSON document and preserve its supplied hashes."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValidationError("sequence-grammar fixture must be an object")
    sources = tuple(SequenceGrammarSourceReceipt(**dict(item)) for item in raw.get("sources", ()))
    records = tuple(
        SequenceGrammarRecord(
            record_id=str(item.get("record_id", "")),
            operation=SequenceGrammarOperation(str(item.get("operation", ""))),
            role=SequenceGrammarRole(str(item.get("role", ""))),
            expected_state=SequenceGrammarState(str(item.get("expected_state", ""))),
            expected_issue_codes=tuple(
                str(value) for value in item.get("expected_issue_codes", ())
            ),
            payload=item.get("payload", {}),
            source_ids=tuple(str(value) for value in item.get("source_ids", ())),
            context_key=str(item.get("context_key", SEQUENCE_GRAMMAR_CONTEXT_KEY)),
            content_address=str(item.get("content_address", "")),
        )
        for item in raw.get("records", ())
    )
    return SequenceGrammarFixture(
        fixture_id=str(raw.get("fixture_id", "")),
        fixture_version=str(raw.get("fixture_version", "")),
        context_key=str(raw.get("context_key", "")),
        evidence_boundary=str(raw.get("evidence_boundary", "")),
        sources=sources,
        records=records,
        content_address=str(raw.get("content_address", "")),
    )


__all__ = [
    "SEQUENCE_GRAMMAR_BOUNDARY",
    "SEQUENCE_GRAMMAR_CONTEXT_KEY",
    "SEQUENCE_GRAMMAR_CONTROL_COUNT",
    "SEQUENCE_GRAMMAR_FIXTURE_VERSION",
    "SEQUENCE_GRAMMAR_POSITIVE_COUNT",
    "SEQUENCE_GRAMMAR_SOURCE_COUNT",
    "SequenceGrammarCatalog",
    "SequenceGrammarDataAudit",
    "SequenceGrammarDataCheck",
    "SequenceGrammarFixture",
    "SequenceGrammarOperation",
    "SequenceGrammarRecord",
    "SequenceGrammarRole",
    "SequenceGrammarSourceReceipt",
    "SequenceGrammarState",
    "audit_sequence_grammar_data",
    "build_sequence_grammar_catalog",
    "default_sequence_grammar_fixture",
    "load_sequence_grammar_fixture",
]
