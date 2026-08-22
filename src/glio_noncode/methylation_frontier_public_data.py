"""Closed public aggregate fixture for Domain 07 C05-C08.

The fixture binds measured methylation records, sequence-only CpG changes,
methylation-sensitive motif observations, and a descriptive IDH panel model to
public source receipts.  It contains positive and control paths for every
operation and never carries subject-level fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

METHYLATION_FRONTIER_FIXTURE_VERSION = "2026.08.d07-c05-c08.v1"
METHYLATION_FRONTIER_CONTEXT_KEY = (
    "GRCh38|diffuse_glioma|adult|bulk_tumor|epigenomic_assay|baseline"
)
METHYLATION_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
METHYLATION_FRONTIER_POSITIVE_COUNT = 4
METHYLATION_FRONTIER_CONTROL_COUNT = 12
METHYLATION_FRONTIER_SOURCE_COUNT = 4


class MethylationFrontierOperation(StrEnum):
    """The four methylation operations covered by this release slice."""

    CONTEXT_RETRIEVAL = "methylation_context_retrieval"
    CPG_CHANGE = "cpg_creation_loss"
    SENSITIVE_MOTIF = "methylation_sensitive_motif"
    IDH_CONTEXT = "idh_hypermethylation_context"


class MethylationFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class MethylationFrontierState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    INVALID = "invalid"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class MethylationFrontierSourceReceipt:
    """Public source receipt with version and checksum identity."""

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
class MethylationFrontierRecord:
    """One positive or control operation payload."""

    record_id: str
    operation: MethylationFrontierOperation
    role: MethylationFrontierRole
    expected_state: MethylationFrontierState
    expected_issue_codes: tuple[str, ...]
    payload: Mapping[str, Any]
    source_ids: tuple[str, ...]
    context_key: str = METHYLATION_FRONTIER_CONTEXT_KEY
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.source_ids:
            raise ValidationError("record identity and source IDs are required")
        if self.context_key != METHYLATION_FRONTIER_CONTEXT_KEY:
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
class MethylationFrontierFixture:
    """Four positive and twelve control records with public source receipts."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[MethylationFrontierSourceReceipt, ...]
    records: tuple[MethylationFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != METHYLATION_FRONTIER_FIXTURE_VERSION:
            raise ValidationError("unsupported methylation frontier fixture version")
        if self.context_key != METHYLATION_FRONTIER_CONTEXT_KEY:
            raise ValidationError("fixture context does not match checked-in boundary")
        if self.evidence_boundary != METHYLATION_FRONTIER_BOUNDARY:
            raise ValidationError("fixture boundary is not public aggregate data")
        if len(self.sources) != METHYLATION_FRONTIER_SOURCE_COUNT:
            raise ValidationError("fixture requires four source receipts")
        if (
            len(self.records)
            != METHYLATION_FRONTIER_POSITIVE_COUNT + METHYLATION_FRONTIER_CONTROL_COUNT
        ):
            raise ValidationError("fixture requires four positive and twelve controls")
        if len(self.positive_records) != METHYLATION_FRONTIER_POSITIVE_COUNT:
            raise ValidationError("fixture positive count is not four")
        if len(self.control_records) != METHYLATION_FRONTIER_CONTROL_COUNT:
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
    def positive_records(self) -> tuple[MethylationFrontierRecord, ...]:
        return tuple(
            record for record in self.records if record.role is MethylationFrontierRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[MethylationFrontierRecord, ...]:
        return tuple(
            record for record in self.records if record.role is MethylationFrontierRole.CONTROL
        )

    def operation_records(
        self, operation: MethylationFrontierOperation
    ) -> tuple[MethylationFrontierRecord, ...]:
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
class MethylationFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.detail.strip():
            raise ValidationError("data check requires ID and detail")
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
class MethylationFrontierDataAudit:
    accepted: bool
    checks: tuple[MethylationFrontierDataCheck, ...]
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
class MethylationFrontierCatalog:
    fixture_id: str
    context_key: str
    operations: tuple[str, ...]
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, uri: str, version: str) -> MethylationFrontierSourceReceipt:
    return MethylationFrontierSourceReceipt(
        source_id=source_id,
        uri=uri,
        source_version=version,
        checksum=content_hash({"source_id": source_id, "version": version}),
        context_key=METHYLATION_FRONTIER_CONTEXT_KEY,
    )


def _record(
    record_id: str,
    operation: MethylationFrontierOperation,
    role: MethylationFrontierRole,
    state: MethylationFrontierState,
    issue_codes: tuple[str, ...],
    payload: Mapping[str, Any],
    *source_ids: str,
) -> MethylationFrontierRecord:
    return MethylationFrontierRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        expected_state=state,
        expected_issue_codes=issue_codes,
        payload=payload,
        source_ids=tuple(source_ids),
    )


def _tsv(rows: tuple[tuple[str, ...], ...]) -> str:
    return "\n".join("\t".join(row) for row in rows) + "\n"


def _methylation_rows(
    context: str,
    *,
    target_state: str = "IDH-mutant",
    target_values: tuple[str, ...] = ("0.80", "0.85", "0.90"),
    start: int = 100,
) -> str:
    header = ("chromosome", "position", "beta_value", "context_key", "coverage", "molecular_state")
    rows = tuple(
        ("7", str(start + index), value, context, "50", target_state)
        for index, value in enumerate(target_values)
    )
    return _tsv((header, *rows))


def _record_payloads() -> dict[str, Mapping[str, Any]]:
    context = METHYLATION_FRONTIER_CONTEXT_KEY
    other_context = "GRCh38|other|adult|bulk_tumor|epigenomic_assay|baseline"
    parser_positive = {
        "text": _methylation_rows(context),
        "source_id": "encode-methylation",
        "source_version": "2025.4",
        "coordinate_system": "one_based",
        "query": {"chromosome": "7", "start": 100, "end": 101},
        "beta_spread_tolerance": 0.20,
        "context_key": context,
    }
    cpg_positive = {
        "reference_sequence": "AAGTT",
        "alternate_sequence": "ACGTT",
        "variant_id": "aggregate-cpg-create-1",
        "window_start": 99,
        "chromosome": "7",
        "context_key": context,
        "methylated_threshold": 0.50,
        "methylation_records": [
            {
                "record_id": "aggregate-meth-100",
                "chromosome": "7",
                "position": 100,
                "beta_value": 0.80,
                "context_key": context,
                "source_id": "encode-methylation",
                "source_version": "2025.4",
                "coverage": 50,
            }
        ],
    }
    motif_positive = {
        "sequence": "ACGTT",
        "sequence_id": "aggregate-motif-1",
        "window_start": 99,
        "chromosome": "7",
        "context_key": context,
        "motifs": [
            {
                "motif_id": "C05:CG-sensitive",
                "name": "aggregate CG-sensitive motif",
                "consensus": "CG",
                "source_id": "cpg-motif-catalog",
                "source_version": "2026.1",
                "sensitive_positions": [0],
                "threshold": 1.0,
                "methylated_threshold": 0.50,
                "strand_aware": False,
            }
        ],
        "methylation_records": [
            {
                "record_id": "aggregate-meth-100",
                "chromosome": "7",
                "position": 100,
                "beta_value": 0.80,
                "context_key": context,
                "source_id": "encode-methylation",
                "source_version": "2025.4",
            }
        ],
    }
    idh_target = [
        {
            "record_id": f"aggregate-idh-target-{index}",
            "chromosome": "7",
            "position": 100 + index,
            "beta_value": value,
            "context_key": context,
            "source_id": "encode-methylation",
            "source_version": "2025.4",
            "coverage": 100,
            "molecular_state": "IDH-mutant",
        }
        for index, value in enumerate((0.80, 0.85, 0.90))
    ]
    idh_comparator = [
        {
            "record_id": f"aggregate-idh-comparator-{index}",
            "chromosome": "7",
            "position": 100 + index,
            "beta_value": 0.20,
            "context_key": context,
            "source_id": "encode-methylation",
            "source_version": "2025.4",
            "coverage": 100,
            "molecular_state": "IDH-wildtype",
        }
        for index in range(3)
    ]
    idh_positive = {
        "target_records": idh_target,
        "comparator_records": idh_comparator,
        "context_key": context,
        "molecular_state": "IDH-mutant",
        "comparator_state": "IDH-wildtype",
        "model_id": "aggregate-idh-panel",
        "model_version": "2026.1",
        "methylated_threshold": 0.70,
        "minimum_sites": 3,
    }
    return {
        "c05_positive": parser_positive,
        "c06_positive": cpg_positive,
        "c07_positive": motif_positive,
        "c08_positive": idh_positive,
        "c05_malformed": {
            **parser_positive,
            "text": _tsv(
                (
                    ("chromosome", "position", "beta_value", "context_key"),
                    ("7", "100", "0.80", context),
                    ("7", "bad", "0.70", context),
                )
            ),
        },
        "c05_empty": {**parser_positive, "text": ""},
        "c05_context": {
            **parser_positive,
            "text": _methylation_rows(other_context),
        },
        "c06_invalid": {**cpg_positive, "reference_sequence": "AAXTT"},
        "c06_length": {**cpg_positive, "alternate_sequence": "ACGTTT"},
        "c06_absent": {
            **cpg_positive,
            "reference_sequence": "AAGTT",
            "alternate_sequence": "AATTT",
        },
        "c07_missing": {**motif_positive, "methylation_records": []},
        "c07_invalid": {**motif_positive, "sequence": "ACXTT"},
        "c07_context": {
            **motif_positive,
            "methylation_records": [
                {
                    **motif_positive["methylation_records"][0],
                    "context_key": other_context,
                }
            ],
        },
        "c08_partial": {**idh_positive, "comparator_records": idh_comparator[:1]},
        "c08_context": {
            **idh_positive,
            "target_records": [{**record, "context_key": other_context} for record in idh_target],
        },
        "c08_empty": {**idh_positive, "target_records": [], "comparator_records": []},
    }


def default_methylation_frontier_fixture() -> MethylationFrontierFixture:
    """Build the deterministic four-positive/twelve-control fixture."""

    sources = (
        _source("encode-methylation", "https://www.encodeproject.org/", "2025.4"),
        _source("roadmap-epigenomics", "https://egg2.wustl.edu/roadmap/web_portal/", "2025.1"),
        _source("ncbi-reference", "https://www.ncbi.nlm.nih.gov/", "2026.1"),
        _source("cpg-motif-catalog", "https://jaspar.genereg.net/", "2026.1"),
    )
    payloads = _record_payloads()
    records = (
        _record(
            "C05-POS-001",
            MethylationFrontierOperation.CONTEXT_RETRIEVAL,
            MethylationFrontierRole.POSITIVE,
            MethylationFrontierState.SUPPORTED,
            ("context_query_supported",),
            payloads["c05_positive"],
            "encode-methylation",
            "ncbi-reference",
        ),
        _record(
            "C05-CTRL-001",
            MethylationFrontierOperation.CONTEXT_RETRIEVAL,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.PARTIAL,
            ("parse_issue",),
            payloads["c05_malformed"],
            "encode-methylation",
        ),
        _record(
            "C05-CTRL-002",
            MethylationFrontierOperation.CONTEXT_RETRIEVAL,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.INVALID,
            ("empty_input",),
            payloads["c05_empty"],
            "encode-methylation",
        ),
        _record(
            "C05-CTRL-003",
            MethylationFrontierOperation.CONTEXT_RETRIEVAL,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            payloads["c05_context"],
            "encode-methylation",
        ),
        _record(
            "C06-POS-001",
            MethylationFrontierOperation.CPG_CHANGE,
            MethylationFrontierRole.POSITIVE,
            MethylationFrontierState.SUPPORTED,
            ("cpg_created", "methylation_supported"),
            payloads["c06_positive"],
            "encode-methylation",
            "ncbi-reference",
        ),
        _record(
            "C06-CTRL-001",
            MethylationFrontierOperation.CPG_CHANGE,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.INVALID,
            ("invalid_sequence_alphabet",),
            payloads["c06_invalid"],
            "encode-methylation",
        ),
        _record(
            "C06-CTRL-002",
            MethylationFrontierOperation.CPG_CHANGE,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.OUT_OF_DOMAIN,
            ("length_change_out_of_domain",),
            payloads["c06_length"],
            "encode-methylation",
        ),
        _record(
            "C06-CTRL-003",
            MethylationFrontierOperation.CPG_CHANGE,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.ABSTAINED,
            ("no_cpg_change",),
            payloads["c06_absent"],
            "encode-methylation",
        ),
        _record(
            "C07-POS-001",
            MethylationFrontierOperation.SENSITIVE_MOTIF,
            MethylationFrontierRole.POSITIVE,
            MethylationFrontierState.SUPPORTED,
            ("sensitive_motif_observed", "methylation_supported"),
            payloads["c07_positive"],
            "cpg-motif-catalog",
            "encode-methylation",
        ),
        _record(
            "C07-CTRL-001",
            MethylationFrontierOperation.SENSITIVE_MOTIF,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.PARTIAL,
            ("missing_methylation",),
            payloads["c07_missing"],
            "cpg-motif-catalog",
        ),
        _record(
            "C07-CTRL-002",
            MethylationFrontierOperation.SENSITIVE_MOTIF,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.INVALID,
            ("invalid_sequence_window",),
            payloads["c07_invalid"],
            "cpg-motif-catalog",
        ),
        _record(
            "C07-CTRL-003",
            MethylationFrontierOperation.SENSITIVE_MOTIF,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.PARTIAL,
            ("context_mismatch", "missing_methylation"),
            payloads["c07_context"],
            "cpg-motif-catalog",
        ),
        _record(
            "C08-POS-001",
            MethylationFrontierOperation.IDH_CONTEXT,
            MethylationFrontierRole.POSITIVE,
            MethylationFrontierState.SUPPORTED,
            ("idh_panel_supported", "comparator_supported"),
            payloads["c08_positive"],
            "encode-methylation",
            "roadmap-epigenomics",
        ),
        _record(
            "C08-CTRL-001",
            MethylationFrontierOperation.IDH_CONTEXT,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.PARTIAL,
            ("comparator_support_incomplete",),
            payloads["c08_partial"],
            "encode-methylation",
        ),
        _record(
            "C08-CTRL-002",
            MethylationFrontierOperation.IDH_CONTEXT,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            payloads["c08_context"],
            "encode-methylation",
        ),
        _record(
            "C08-CTRL-003",
            MethylationFrontierOperation.IDH_CONTEXT,
            MethylationFrontierRole.CONTROL,
            MethylationFrontierState.ABSTAINED,
            ("target_support_absent",),
            payloads["c08_empty"],
            "encode-methylation",
        ),
    )
    return MethylationFrontierFixture(
        fixture_id="methylation-frontier-public-aggregate",
        fixture_version=METHYLATION_FRONTIER_FIXTURE_VERSION,
        context_key=METHYLATION_FRONTIER_CONTEXT_KEY,
        evidence_boundary=METHYLATION_FRONTIER_BOUNDARY,
        sources=sources,
        records=records,
    )


def audit_methylation_frontier_data(
    fixture: MethylationFrontierFixture | None = None,
) -> MethylationFrontierDataAudit:
    """Run structural checks before low-level methylation execution."""

    fixture = fixture or default_methylation_frontier_fixture()
    forbidden = {"patient", "subject", "sample_id", "donor_id", "participant_id"}
    checks = (
        MethylationFrontierDataCheck(
            "fixture_version",
            fixture.fixture_version == METHYLATION_FRONTIER_FIXTURE_VERSION,
            "fixture version is supported",
        ),
        MethylationFrontierDataCheck(
            "public_boundary",
            fixture.evidence_boundary == METHYLATION_FRONTIER_BOUNDARY,
            "fixture boundary is public aggregate",
        ),
        MethylationFrontierDataCheck(
            "source_count", len(fixture.sources) == 4, "four source receipts are present"
        ),
        MethylationFrontierDataCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "four positive records are present",
        ),
        MethylationFrontierDataCheck(
            "control_count", len(fixture.control_records) == 12, "twelve controls are present"
        ),
        MethylationFrontierDataCheck(
            "operation_coverage",
            {record.operation for record in fixture.records} == set(MethylationFrontierOperation),
            "all four operations are represented",
        ),
        MethylationFrontierDataCheck(
            "source_receipts",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "source receipts are content addressed",
        ),
        MethylationFrontierDataCheck(
            "record_receipts",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "record receipts are content addressed",
        ),
        MethylationFrontierDataCheck(
            "context_lock",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "record contexts are locked",
        ),
        MethylationFrontierDataCheck(
            "payload_boundary",
            all(
                not forbidden & {str(key).lower() for key in record.payload}
                for record in fixture.records
            ),
            "payloads remain aggregate",
        ),
        MethylationFrontierDataCheck(
            "source_links",
            all(
                set(record.source_ids) <= {source.source_id for source in fixture.sources}
                for record in fixture.records
            ),
            "record source links are declared",
        ),
        MethylationFrontierDataCheck(
            "positive_operation_balance",
            {record.operation for record in fixture.positive_records}
            == set(MethylationFrontierOperation),
            "one positive path covers every operation",
        ),
    )
    return MethylationFrontierDataAudit(
        accepted=all(check.passed for check in checks),
        checks=checks,
        fixture_id=fixture.fixture_id,
    )


def build_methylation_frontier_catalog(
    fixture: MethylationFrontierFixture | None = None,
) -> MethylationFrontierCatalog:
    """Build the operation, source, record, and issue catalog."""

    fixture = fixture or default_methylation_frontier_fixture()
    issue_codes = tuple(
        sorted({code for record in fixture.records for code in record.expected_issue_codes})
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "operations": tuple(operation.value for operation in MethylationFrontierOperation),
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "issue_codes": issue_codes,
    }
    return MethylationFrontierCatalog(**body, content_address=content_hash(body))


__all__ = [
    "METHYLATION_FRONTIER_BOUNDARY",
    "METHYLATION_FRONTIER_CONTEXT_KEY",
    "METHYLATION_FRONTIER_CONTROL_COUNT",
    "METHYLATION_FRONTIER_FIXTURE_VERSION",
    "METHYLATION_FRONTIER_POSITIVE_COUNT",
    "METHYLATION_FRONTIER_SOURCE_COUNT",
    "MethylationFrontierCatalog",
    "MethylationFrontierDataAudit",
    "MethylationFrontierDataCheck",
    "MethylationFrontierFixture",
    "MethylationFrontierOperation",
    "MethylationFrontierRecord",
    "MethylationFrontierRole",
    "MethylationFrontierSourceReceipt",
    "MethylationFrontierState",
    "audit_methylation_frontier_data",
    "build_methylation_frontier_catalog",
    "default_methylation_frontier_fixture",
]
