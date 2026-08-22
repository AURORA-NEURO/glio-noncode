"""Closed public aggregate fixture for Domain 06 C09-C12.

The fixture joins four sequence-regulation operations to source receipts,
context constraints, expected states, and boundary controls.  Records are
synthetic aggregate examples built from public sequence-rule references; no
subject-level fields are accepted and no biological effect is asserted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

SEQUENCE_REGULATION_FIXTURE_VERSION = "2026.08.d06-c09-c12.v1"
SEQUENCE_REGULATION_CONTEXT_KEY = (
    "GRCh38|diffuse_glioma|adult|bulk_tumor|noncoding_sequence|baseline"
)
SEQUENCE_REGULATION_BOUNDARY = "public_aggregate_non_patient"
SEQUENCE_REGULATION_POSITIVE_COUNT = 4
SEQUENCE_REGULATION_CONTROL_COUNT = 12
SEQUENCE_REGULATION_SOURCE_COUNT = 4


class SequenceRegulationOperation(StrEnum):
    """The four operations covered by this release slice."""

    NUCLEOSOME_PROPENSITY = "nucleosome_propensity"
    SPLICE_REGULATION = "splice_regulation"
    UTR_REGULATION = "utr_regulation"
    PROMOTER_GRAMMAR = "promoter_grammar"


class SequenceRegulationRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class SequenceRegulationState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class SequenceRegulationSourceReceipt:
    """A public aggregate source with an immutable content receipt."""

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
class SequenceRegulationRecord:
    """One operation payload and its expected boundary behavior."""

    record_id: str
    operation: SequenceRegulationOperation
    role: SequenceRegulationRole
    expected_state: SequenceRegulationState
    expected_issue_codes: tuple[str, ...]
    payload: Mapping[str, Any]
    source_ids: tuple[str, ...]
    context_key: str = SEQUENCE_REGULATION_CONTEXT_KEY
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.source_ids:
            raise ValidationError("record identity and source IDs are required")
        if self.context_key != SEQUENCE_REGULATION_CONTEXT_KEY:
            raise ValidationError("record context is outside the fixture boundary")
        if not isinstance(self.payload, Mapping) or not self.payload:
            raise ValidationError("record payload must be a non-empty object")
        forbidden = {
            "subject",
            "patient",
            "sample_id",
            "donor_id",
            "participant_id",
            "individual_id",
        }
        if any(str(key).lower() in forbidden for key in self.payload):
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
class SequenceRegulationFixture:
    """A reproducible four-positive/twelve-control public fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[SequenceRegulationSourceReceipt, ...]
    records: tuple[SequenceRegulationRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != SEQUENCE_REGULATION_FIXTURE_VERSION:
            raise ValidationError("unsupported sequence-regulation fixture version")
        if self.context_key != SEQUENCE_REGULATION_CONTEXT_KEY:
            raise ValidationError("fixture context does not match checked-in boundary")
        if self.evidence_boundary != SEQUENCE_REGULATION_BOUNDARY:
            raise ValidationError("fixture evidence boundary is not public aggregate data")
        if len(self.sources) != SEQUENCE_REGULATION_SOURCE_COUNT:
            raise ValidationError("fixture requires four independent source receipts")
        expected = SEQUENCE_REGULATION_POSITIVE_COUNT + SEQUENCE_REGULATION_CONTROL_COUNT
        if len(self.records) != expected:
            raise ValidationError("fixture requires four positive and twelve controls")
        if len(self.positive_records) != SEQUENCE_REGULATION_POSITIVE_COUNT:
            raise ValidationError("fixture positive count is not four")
        if len(self.control_records) != SEQUENCE_REGULATION_CONTROL_COUNT:
            raise ValidationError("fixture control count is not twelve")
        source_ids = {source.source_id for source in self.sources}
        if any(set(record.source_ids) - source_ids for record in self.records):
            raise ValidationError("record references an undeclared source")
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
    def positive_records(self) -> tuple[SequenceRegulationRecord, ...]:
        return tuple(
            record for record in self.records if record.role is SequenceRegulationRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[SequenceRegulationRecord, ...]:
        return tuple(
            record for record in self.records if record.role is SequenceRegulationRole.CONTROL
        )

    def operation_records(
        self, operation: SequenceRegulationOperation
    ) -> tuple[SequenceRegulationRecord, ...]:
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
class SequenceRegulationDataCheck:
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
class SequenceRegulationDataAudit:
    accepted: bool
    checks: tuple[SequenceRegulationDataCheck, ...]
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
class SequenceRegulationCatalog:
    fixture_id: str
    context_key: str
    operations: tuple[str, ...]
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, uri: str, version: str) -> SequenceRegulationSourceReceipt:
    return SequenceRegulationSourceReceipt(
        source_id=source_id,
        uri=uri,
        source_version=version,
        checksum=content_hash({"source_id": source_id, "version": version}),
        context_key=SEQUENCE_REGULATION_CONTEXT_KEY,
    )


def _record(
    record_id: str,
    operation: SequenceRegulationOperation,
    role: SequenceRegulationRole,
    state: SequenceRegulationState,
    issue_codes: tuple[str, ...],
    payload: Mapping[str, Any],
    *source_ids: str,
) -> SequenceRegulationRecord:
    return SequenceRegulationRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        expected_state=state,
        expected_issue_codes=issue_codes,
        payload=payload,
        source_ids=tuple(source_ids),
    )


def _splice_motif(motif_id: str = "splice-donor") -> dict[str, Any]:
    return {
        "motif_id": motif_id,
        "name": "aggregate splice donor pattern",
        "consensus": "GT",
        "role": "donor",
        "source_id": "splice-aggregate",
        "source_version": "2026.1",
        "threshold": 1.0,
        "strand_aware": False,
    }


def _utr_motifs() -> list[dict[str, Any]]:
    return [
        {
            "motif_id": "utr-uorf-start",
            "name": "aggregate upstream start",
            "consensus": "ATG",
            "element_kind": "uorf_start",
            "region": "5utr",
            "source_id": "utr-aggregate",
            "source_version": "2026.1",
            "threshold": 1.0,
            "strand_aware": False,
        },
        {
            "motif_id": "utr-mirna-seed",
            "name": "aggregate seed pattern",
            "consensus": "TGTA",
            "element_kind": "mirna_seed",
            "region": "3utr",
            "source_id": "utr-aggregate",
            "source_version": "2026.1",
            "threshold": 1.0,
            "strand_aware": False,
        },
    ]


def _promoter_motifs() -> list[dict[str, Any]]:
    return [
        {
            "motif_id": "prom-tata",
            "name": "aggregate TATA pattern",
            "consensus": "TATA",
            "element_kind": "tata",
            "source_id": "promoter-aggregate",
            "source_version": "2026.1",
            "threshold": 1.0,
            "strand_aware": False,
        },
        {
            "motif_id": "prom-inr",
            "name": "aggregate initiator pattern",
            "consensus": "CA",
            "element_kind": "initiator",
            "source_id": "promoter-aggregate",
            "source_version": "2026.1",
            "threshold": 1.0,
            "strand_aware": False,
        },
    ]


def _promoter_rules() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": "prom-tata-inr",
            "motif_a": "prom-tata",
            "motif_b": "prom-inr",
            "minimum_spacing": 2,
            "maximum_spacing": 4,
            "allowed_orientations": ["same"],
            "source_id": "promoter-grammar-aggregate",
            "source_version": "2026.1",
        }
    ]


def default_sequence_regulation_fixture() -> SequenceRegulationFixture:
    """Build the deterministic four-positive/twelve-control fixture."""

    sources = (
        _source("encode-regulation", "https://www.encodeproject.org/", "2025.4"),
        _source("jaspar-motifs", "https://jaspar.genereg.net/", "2026.1"),
        _source("ncbi-reference", "https://www.ncbi.nlm.nih.gov/", "2026.1"),
        _source("ensembl-reference", "https://www.ensembl.org/", "release-114"),
    )
    context = SEQUENCE_REGULATION_CONTEXT_KEY
    nucleosome_payload = {
        "sequence_id": "aggregate-nucleosome-1",
        "chrom": "7",
        "start": 1001,
        "sequence": "AA" * 74,
        "context_key": context,
        "source_id": "ncbi-reference",
        "source_version": "2026.1",
    }
    splice_payload = {
        "sequence_id": "aggregate-splice-1",
        "chrom": "7",
        "start": 2001,
        "reference_sequence": "AACGTAA",
        "alternate_sequence": "AACATAA",
        "context_key": context,
        "motifs": [_splice_motif()],
    }
    utr_payload = {
        "utr_id": "aggregate-utr-1",
        "region": "5utr",
        "chrom": "7",
        "start": 3001,
        "sequence": "CCCATGAAATAACCC",
        "context_key": context,
        "motifs": _utr_motifs(),
    }
    promoter_payload = {
        "promoter_id": "aggregate-promoter-1",
        "chrom": "7",
        "start": 4001,
        "sequence": "AAAATATAAAACAGG",
        "context_key": context,
        "motifs": _promoter_motifs(),
        "rules": _promoter_rules(),
    }
    records = (
        _record(
            "C09-POS-001",
            SequenceRegulationOperation.NUCLEOSOME_PROPENSITY,
            SequenceRegulationRole.POSITIVE,
            SequenceRegulationState.SUPPORTED,
            ("propensity_observed",),
            nucleosome_payload,
            "ncbi-reference",
            "ensembl-reference",
        ),
        _record(
            "C09-CTRL-001",
            SequenceRegulationOperation.NUCLEOSOME_PROPENSITY,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.PARTIAL,
            ("short_window",),
            {
                **nucleosome_payload,
                "sequence_id": "aggregate-nucleosome-short",
                "sequence": "ACGT" * 10,
            },
            "ncbi-reference",
        ),
        _record(
            "C09-CTRL-002",
            SequenceRegulationOperation.NUCLEOSOME_PROPENSITY,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.INVALID,
            ("invalid_sequence_alphabet",),
            {
                **nucleosome_payload,
                "sequence_id": "aggregate-nucleosome-invalid",
                "sequence": "AAAX" * 40,
            },
            "ncbi-reference",
        ),
        _record(
            "C09-CTRL-003",
            SequenceRegulationOperation.NUCLEOSOME_PROPENSITY,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            {
                **nucleosome_payload,
                "sequence_id": "aggregate-nucleosome-context",
                "context_key": "GRCh38|other|adult|bulk_tumor|noncoding_sequence|baseline",
            },
            "ncbi-reference",
        ),
        _record(
            "C10-POS-001",
            SequenceRegulationOperation.SPLICE_REGULATION,
            SequenceRegulationRole.POSITIVE,
            SequenceRegulationState.SUPPORTED,
            ("motif_disrupted",),
            splice_payload,
            "encode-regulation",
            "jaspar-motifs",
        ),
        _record(
            "C10-CTRL-001",
            SequenceRegulationOperation.SPLICE_REGULATION,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.INVALID,
            ("invalid_sequence_alphabet",),
            {
                **splice_payload,
                "sequence_id": "aggregate-splice-invalid",
                "reference_sequence": "AACXTAA",
            },
            "encode-regulation",
        ),
        _record(
            "C10-CTRL-002",
            SequenceRegulationOperation.SPLICE_REGULATION,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.ABSTAINED,
            ("no_motif_change",),
            {
                **splice_payload,
                "sequence_id": "aggregate-splice-stable",
                "alternate_sequence": "AACGTAA",
            },
            "encode-regulation",
        ),
        _record(
            "C10-CTRL-003",
            SequenceRegulationOperation.SPLICE_REGULATION,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            {
                **splice_payload,
                "sequence_id": "aggregate-splice-context",
                "context_key": "GRCh38|other|adult|bulk_tumor|noncoding_sequence|baseline",
            },
            "encode-regulation",
        ),
        _record(
            "C11-POS-001",
            SequenceRegulationOperation.UTR_REGULATION,
            SequenceRegulationRole.POSITIVE,
            SequenceRegulationState.SUPPORTED,
            ("utr_element_observed", "uorf_observed"),
            utr_payload,
            "encode-regulation",
            "ncbi-reference",
        ),
        _record(
            "C11-CTRL-001",
            SequenceRegulationOperation.UTR_REGULATION,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.PARTIAL,
            ("ambiguous_bases",),
            {**utr_payload, "utr_id": "aggregate-utr-ambiguous", "sequence": "CCCATGAAATNACCC"},
            "encode-regulation",
        ),
        _record(
            "C11-CTRL-002",
            SequenceRegulationOperation.UTR_REGULATION,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.ABSTAINED,
            ("no_utr_observation",),
            {
                **utr_payload,
                "utr_id": "aggregate-utr-empty",
                "region": "3utr",
                "sequence": "CCCCCCCCCCCC",
                "motifs": _utr_motifs(),
            },
            "encode-regulation",
        ),
        _record(
            "C11-CTRL-003",
            SequenceRegulationOperation.UTR_REGULATION,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.INVALID,
            ("invalid_utr_region",),
            {**utr_payload, "utr_id": "aggregate-utr-invalid", "region": "intron"},
            "encode-regulation",
        ),
        _record(
            "C12-POS-001",
            SequenceRegulationOperation.PROMOTER_GRAMMAR,
            SequenceRegulationRole.POSITIVE,
            SequenceRegulationState.SUPPORTED,
            ("grammar_rule_matched",),
            promoter_payload,
            "jaspar-motifs",
            "encode-regulation",
        ),
        _record(
            "C12-CTRL-001",
            SequenceRegulationOperation.PROMOTER_GRAMMAR,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.ABSTAINED,
            ("no_grammar_pair",),
            {
                **promoter_payload,
                "promoter_id": "aggregate-promoter-empty",
                "sequence": "CCCCCCCCCCCCCCCC",
            },
            "jaspar-motifs",
        ),
        _record(
            "C12-CTRL-002",
            SequenceRegulationOperation.PROMOTER_GRAMMAR,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.INVALID,
            ("invalid_sequence_alphabet",),
            {
                **promoter_payload,
                "promoter_id": "aggregate-promoter-invalid",
                "sequence": "AAAATATXAAACAGG",
            },
            "jaspar-motifs",
        ),
        _record(
            "C12-CTRL-003",
            SequenceRegulationOperation.PROMOTER_GRAMMAR,
            SequenceRegulationRole.CONTROL,
            SequenceRegulationState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            {
                **promoter_payload,
                "promoter_id": "aggregate-promoter-context",
                "context_key": "GRCh38|other|adult|bulk_tumor|noncoding_sequence|baseline",
            },
            "jaspar-motifs",
        ),
    )
    return SequenceRegulationFixture(
        fixture_id="sequence-regulation-frontier-public-aggregate",
        fixture_version=SEQUENCE_REGULATION_FIXTURE_VERSION,
        context_key=context,
        evidence_boundary=SEQUENCE_REGULATION_BOUNDARY,
        sources=sources,
        records=records,
    )


def audit_sequence_regulation_data(
    fixture: SequenceRegulationFixture | None = None,
) -> SequenceRegulationDataAudit:
    """Run structural checks before any operation is executed."""

    fixture = fixture or default_sequence_regulation_fixture()
    checks = (
        SequenceRegulationDataCheck(
            "fixture_version",
            fixture.fixture_version == SEQUENCE_REGULATION_FIXTURE_VERSION,
            "fixture version is supported",
        ),
        SequenceRegulationDataCheck(
            "public_boundary",
            fixture.evidence_boundary == SEQUENCE_REGULATION_BOUNDARY,
            "fixture boundary is public aggregate",
        ),
        SequenceRegulationDataCheck(
            "source_count", len(fixture.sources) == 4, "four source receipts are present"
        ),
        SequenceRegulationDataCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "four positive records are present",
        ),
        SequenceRegulationDataCheck(
            "control_count", len(fixture.control_records) == 12, "twelve controls are present"
        ),
        SequenceRegulationDataCheck(
            "operation_coverage",
            {record.operation for record in fixture.records} == set(SequenceRegulationOperation),
            "all four operations are represented",
        ),
        SequenceRegulationDataCheck(
            "source_receipts",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "source receipts are content addressed",
        ),
        SequenceRegulationDataCheck(
            "record_receipts",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "record receipts are content addressed",
        ),
        SequenceRegulationDataCheck(
            "context_lock",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "records use the checked-in context",
        ),
        SequenceRegulationDataCheck(
            "payload_boundary",
            all(
                not {str(key).lower() for key in record.payload}
                & {"patient", "subject", "sample_id", "donor_id", "participant_id"}
                for record in fixture.records
            ),
            "payloads remain aggregate",
        ),
    )
    return SequenceRegulationDataAudit(
        accepted=all(check.passed for check in checks),
        checks=checks,
        fixture_id=fixture.fixture_id,
    )


def build_sequence_regulation_catalog(
    fixture: SequenceRegulationFixture | None = None,
) -> SequenceRegulationCatalog:
    """Build the inspectable operation/source/issue catalog."""

    fixture = fixture or default_sequence_regulation_fixture()
    issue_codes = tuple(
        sorted({code for record in fixture.records for code in record.expected_issue_codes})
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "operations": tuple(operation.value for operation in SequenceRegulationOperation),
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "issue_codes": issue_codes,
    }
    return SequenceRegulationCatalog(**body, content_address=content_hash(body))


__all__ = [
    "SEQUENCE_REGULATION_BOUNDARY",
    "SEQUENCE_REGULATION_CONTEXT_KEY",
    "SEQUENCE_REGULATION_FIXTURE_VERSION",
    "SequenceRegulationCatalog",
    "SequenceRegulationDataAudit",
    "SequenceRegulationDataCheck",
    "SequenceRegulationFixture",
    "SequenceRegulationOperation",
    "SequenceRegulationRecord",
    "SequenceRegulationRole",
    "SequenceRegulationSourceReceipt",
    "SequenceRegulationState",
    "audit_sequence_regulation_data",
    "build_sequence_regulation_catalog",
    "default_sequence_regulation_fixture",
]
