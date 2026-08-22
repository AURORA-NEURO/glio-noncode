"""Closed aggregate fixture for Domain 07 C01-C04.

The fixture is deliberately small enough to inspect and rich enough to exercise
the complete context track boundary.  It keeps parser failures, replicate
ambiguity, missing measurements, and foreign contexts beside supported rows.
No row is interpreted as a clinical conclusion; the records are public
aggregate-shaped examples used to prove deterministic plumbing and refusal
paths.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CHROMATIN_CONTEXT_FRONTIER_FIXTURE_VERSION = "2026.08.d07-c01-c04.v1"
CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CHROMATIN_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|tumor|unknown"
CHROMATIN_CONTEXT_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
CHROMATIN_CONTEXT_FRONTIER_POSITIVE_COUNT = 4
CHROMATIN_CONTEXT_FRONTIER_CONTROL_COUNT = 12
CHROMATIN_CONTEXT_FRONTIER_SOURCE_COUNT = 5


class ChromatinContextFrontierOperation(StrEnum):
    TRACK_RETRIEVAL = "track_retrieval"
    ACCESSIBILITY_DELTA = "accessibility_delta"
    HISTONE_CONTEXT = "histone_context"
    H3K27AC_ACTIVITY = "h3k27ac_activity"


class ChromatinContextFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class ChromatinContextFrontierExpectedState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    context_key: str
    public_aggregate: bool = True
    content_address: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "scope",
            "context_key",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.uri.startswith("https://"):
            raise ValidationError("source receipt URI must use HTTPS")
        if self.context_key != CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("source receipt context is outside the tranche")
        if not self.public_aggregate:
            raise ValidationError("source receipt must be public aggregate")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(self.to_dict(include_address=False)),
            )

    def to_dict(self, *, include_address: bool = True) -> dict[str, Any]:
        result = {
            "source_id": self.source_id,
            "title": self.title,
            "uri": self.uri,
            "source_kind": self.source_kind,
            "release": self.release,
            "scope": self.scope,
            "context_key": self.context_key,
            "public_aggregate": self.public_aggregate,
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierRecord:
    record_id: str
    operation: ChromatinContextFrontierOperation
    role: ChromatinContextFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: ChromatinContextFrontierExpectedState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for field_name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key != CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("record context is outside the tranche")
        if not self.source_ids:
            raise ValidationError("record requires at least one source receipt")
        if not self.payload:
            raise ValidationError("record payload is empty")
        if not isinstance(self.operation, ChromatinContextFrontierOperation):
            raise ValidationError("record operation is not declared")
        if not isinstance(self.role, ChromatinContextFrontierRole):
            raise ValidationError("record role is not declared")
        if not isinstance(self.expected_state, ChromatinContextFrontierExpectedState):
            raise ValidationError("record expected state is not declared")
        restricted = {
            "patient",
            "subject",
            "sample_id",
            "donor_id",
            "participant_id",
            "individual_id",
        }
        if any(str(key).lower() in restricted for key in self.payload):
            raise ValidationError("subject-level payload keys are not permitted")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "context_key": self.context_key,
                        "source_ids": self.source_ids,
                        "payload": self.payload,
                        "expected_state": self.expected_state,
                        "expected_issue_codes": self.expected_issue_codes,
                        "description": self.description,
                    }
                ),
            )

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        result = {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "role": self.role.value,
            "context_key": self.context_key,
            "source_ids": list(self.source_ids),
            "expected_state": self.expected_state.value,
            "expected_issue_codes": list(self.expected_issue_codes),
            "description": self.description,
            "content_address": self.content_address,
        }
        if include_payload:
            result["payload"] = jsonable(self.payload)
        return result


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ChromatinContextFrontierSourceReceipt, ...]
    records: tuple[ChromatinContextFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != CHROMATIN_CONTEXT_FRONTIER_FIXTURE_VERSION:
            raise ValidationError("unsupported context frontier fixture version")
        if self.context_key != CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("fixture context does not match the tranche")
        if self.evidence_boundary != CHROMATIN_CONTEXT_FRONTIER_BOUNDARY:
            raise ValidationError("fixture boundary must be aggregate")
        if len(self.sources) != CHROMATIN_CONTEXT_FRONTIER_SOURCE_COUNT:
            raise ValidationError("fixture requires five source receipts")
        expected_records = (
            CHROMATIN_CONTEXT_FRONTIER_POSITIVE_COUNT + CHROMATIN_CONTEXT_FRONTIER_CONTROL_COUNT
        )
        if len(self.records) != expected_records:
            raise ValidationError("fixture requires four positive and twelve control records")
        if len(self.positive_records) != CHROMATIN_CONTEXT_FRONTIER_POSITIVE_COUNT:
            raise ValidationError("fixture positive count is not four")
        if len(self.control_records) != CHROMATIN_CONTEXT_FRONTIER_CONTROL_COUNT:
            raise ValidationError("fixture control count is not twelve")
        source_ids = {item.source_id for item in self.sources}
        if any(set(record.source_ids) - source_ids for record in self.records):
            raise ValidationError("record references an undeclared source")
        if len({record.record_id for record in self.records}) != len(self.records):
            raise ValidationError("record IDs must be unique")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(self.to_dict(include_payload=True, include_address=False)),
            )

    @property
    def positive_records(self) -> tuple[ChromatinContextFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is ChromatinContextFrontierRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[ChromatinContextFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is ChromatinContextFrontierRole.CONTROL
        )

    def operation_records(
        self, operation: ChromatinContextFrontierOperation
    ) -> tuple[ChromatinContextFrontierRecord, ...]:
        return tuple(item for item in self.records if item.operation is operation)

    def source_map(self) -> dict[str, ChromatinContextFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, ChromatinContextFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(
        self, *, include_payload: bool = False, include_address: bool = True
    ) -> dict[str, Any]:
        result = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "evidence_boundary": self.evidence_boundary,
            "sources": [item.to_dict() for item in self.sources],
            "records": [item.to_dict(include_payload=include_payload) for item in self.records],
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierDataAudit:
    fixture_id: str
    checks: tuple[ChromatinContextFrontierDataCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("data audit is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _track_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"observations": rows}, sort_keys=True, separators=(",", ":"))


def _track_row(
    track_id: str,
    signal: float,
    *,
    context_key: str = CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY,
    replicate: str = "r1",
    kind: str | None = None,
    mark: str | None = None,
    chromosome: str = "chr7",
    start: int = 100,
    end: int = 140,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "track_id": track_id,
        "signal": signal,
        "context_key": context_key,
        "source_version": "aggregate-2026-01",
        "replicate": replicate,
    }
    if kind is not None:
        row["kind"] = kind
    if mark is not None:
        row["mark"] = mark
    return row


def _record(
    record_id: str,
    operation: ChromatinContextFrontierOperation,
    role: ChromatinContextFrontierRole,
    payload: Mapping[str, Any],
    expected_state: ChromatinContextFrontierExpectedState,
    expected_issue_codes: tuple[str, ...],
    description: str,
    source_ids: tuple[str, ...] = ("encode-aggregate",),
) -> ChromatinContextFrontierRecord:
    return ChromatinContextFrontierRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        context_key=CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY,
        source_ids=source_ids,
        payload=payload,
        expected_state=expected_state,
        expected_issue_codes=expected_issue_codes,
        description=description,
    )


def _sources() -> tuple[ChromatinContextFrontierSourceReceipt, ...]:
    common = CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY
    return (
        ChromatinContextFrontierSourceReceipt(
            "encode-aggregate",
            "ENCODE aggregate chromatin assay index",
            "https://www.encodeproject.org/",
            "assay_index",
            "2026-01",
            "public aggregate ATAC, DNase, and histone metadata",
            common,
        ),
        ChromatinContextFrontierSourceReceipt(
            "roadmap-aggregate",
            "Roadmap Epigenomics public signal summaries",
            "https://egg2.wustl.edu/roadmap/web_portal/",
            "signal_summary",
            "2025-12",
            "public aggregate chromatin signal summaries",
            common,
        ),
        ChromatinContextFrontierSourceReceipt(
            "ihec-aggregate",
            "International Human Epigenome Consortium portal",
            "https://ihec-epigenomes.org/",
            "epigenome_index",
            "2025-11",
            "public aggregate epigenome assay descriptors",
            common,
        ),
        ChromatinContextFrontierSourceReceipt(
            "geo-aggregate",
            "NCBI GEO public study metadata",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "study_metadata",
            "2026-02",
            "public aggregate study and assay metadata",
            common,
        ),
        ChromatinContextFrontierSourceReceipt(
            "ucsc-aggregate",
            "UCSC Genome Browser public track catalogue",
            "https://genome.ucsc.edu/",
            "track_catalogue",
            "2026-01",
            "public aggregate coordinate and track metadata",
            common,
        ),
    )


def default_chromatin_context_frontier_fixture() -> ChromatinContextFrontierFixture:
    """Return the deterministic public aggregate fixture for C01-C04."""

    context = CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY
    foreign = CHROMATIN_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY
    track_positive = _track_json([_track_row("atac-supported", 8.0, kind="atac")])
    track_partial = _track_json(
        [
            _track_row("atac-partial", 6.0, kind="atac"),
            {"chromosome": "chr7", "start": "bad", "end": 140, "signal": 2.0},
        ]
    )
    track_ambiguous = _track_json(
        [
            _track_row("atac-r1", 6.0, replicate="r1", kind="atac"),
            _track_row("atac-r2", 7.0, replicate="r2", kind="atac"),
        ]
    )
    track_foreign = _track_json([_track_row("atac-foreign", 6.0, context_key=foreign, kind="atac")])

    h3_positive = _track_json([_track_row("h3-supported", 9.0, kind="h3k27ac", mark="H3K27ac")])
    h3_partial = _track_json(
        [
            _track_row("h3-partial", 4.0, kind="h3k27ac", mark="H3K27ac"),
            {"chromosome": "chr7", "start": 100, "end": "bad", "signal": 3.0},
        ]
    )
    h3_ambiguous = _track_json(
        [
            _track_row("h3-r1", 4.0, replicate="r1", kind="h3k27ac", mark="H3K27ac"),
            _track_row("h3-r2", 8.0, replicate="r2", kind="h3k27ac", mark="H3K27ac"),
        ]
    )
    h3_foreign = _track_json([_track_row("h3-foreign", 7.0, context_key=foreign, kind="h3k27ac")])

    records = (
        _record(
            "d07-c01-positive",
            ChromatinContextFrontierOperation.TRACK_RETRIEVAL,
            ChromatinContextFrontierRole.POSITIVE,
            {
                "track_kind": "atac",
                "track_text": track_positive,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
            },
            ChromatinContextFrontierExpectedState.SUPPORTED,
            (),
            "one context-matched ATAC interval is retrieved",
        ),
        _record(
            "d07-c01-partial",
            ChromatinContextFrontierOperation.TRACK_RETRIEVAL,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "atac",
                "track_text": track_partial,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
            },
            ChromatinContextFrontierExpectedState.PARTIAL,
            ("invalid_chromatin_row",),
            "one usable ATAC row survives beside a quarantined malformed row",
        ),
        _record(
            "d07-c01-ambiguous",
            ChromatinContextFrontierOperation.TRACK_RETRIEVAL,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "atac",
                "track_text": track_ambiguous,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
            },
            ChromatinContextFrontierExpectedState.AMBIGUOUS,
            (),
            "two context-matched ATAC replicates remain ambiguous",
        ),
        _record(
            "d07-c01-out-domain",
            ChromatinContextFrontierOperation.TRACK_RETRIEVAL,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "atac",
                "track_text": track_foreign,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
            },
            ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign-context ATAC overlap is refused",
        ),
        _record(
            "d07-c02-positive",
            ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA,
            ChromatinContextFrontierRole.POSITIVE,
            {
                "measurement_id": "acc-supported",
                "variant_id": "variant-1",
                "assay": "atac",
                "reference_signal": 10.0,
                "alternate_signal": 15.0,
                "source_id": "encode-aggregate",
                "raw_hash": "sha256:acc1",
                "replicate_count": 3,
            },
            ChromatinContextFrontierExpectedState.SUPPORTED,
            (),
            "reference-to-alternate ATAC delta is measured with a nonzero baseline",
        ),
        _record(
            "d07-c02-partial",
            ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA,
            ChromatinContextFrontierRole.CONTROL,
            {
                "measurement_id": "acc-missing",
                "variant_id": "variant-2",
                "assay": "dnase",
                "reference_signal": 10.0,
                "alternate_signal": None,
                "source_id": "roadmap-aggregate",
                "raw_hash": "sha256:acc2",
                "replicate_count": 2,
            },
            ChromatinContextFrontierExpectedState.ABSTAINED,
            (),
            "missing alternate measurement prevents an accessibility delta",
        ),
        _record(
            "d07-c02-ambiguous",
            ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA,
            ChromatinContextFrontierRole.CONTROL,
            {
                "measurement_id": "acc-zero",
                "variant_id": "variant-3",
                "assay": "atac",
                "reference_signal": 0.0,
                "alternate_signal": 3.0,
                "source_id": "ihec-aggregate",
                "raw_hash": "sha256:acc3",
                "replicate_count": 1,
            },
            ChromatinContextFrontierExpectedState.SUPPORTED,
            (),
            "absolute accessibility delta is retained while relative normalization abstains",
        ),
        _record(
            "d07-c02-out-domain",
            ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA,
            ChromatinContextFrontierRole.CONTROL,
            {
                "measurement_id": "acc-foreign",
                "variant_id": "variant-4",
                "assay": "atac",
                "reference_signal": 4.0,
                "alternate_signal": 6.0,
                "context_key": foreign,
                "source_id": "geo-aggregate",
                "raw_hash": "sha256:acc4",
                "replicate_count": 1,
            },
            ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "measurement context outside the declared context is refused",
        ),
        _record(
            "d07-c03-positive",
            ChromatinContextFrontierOperation.HISTONE_CONTEXT,
            ChromatinContextFrontierRole.POSITIVE,
            {
                "track_kind": "histone",
                "track_text": _track_json(
                    [_track_row("histone-supported", 5.0, kind="histone", mark="H3K4me3")]
                ),
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "mark": "H3K4me3",
            },
            ChromatinContextFrontierExpectedState.SUPPORTED,
            (),
            "one context-matched histone observation is retrieved with mark metadata",
            ("ihec-aggregate",),
        ),
        _record(
            "d07-c03-partial",
            ChromatinContextFrontierOperation.HISTONE_CONTEXT,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "histone",
                "track_text": h3_partial.replace("h3k27ac", "histone"),
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "mark": "H3K27ac",
            },
            ChromatinContextFrontierExpectedState.PARTIAL,
            ("invalid_chromatin_row",),
            "histone track parsing retains a valid row and quarantines malformed input",
            ("ihec-aggregate",),
        ),
        _record(
            "d07-c03-ambiguous",
            ChromatinContextFrontierOperation.HISTONE_CONTEXT,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "histone",
                "track_text": h3_ambiguous.replace("h3k27ac", "histone"),
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "mark": "H3K27ac",
            },
            ChromatinContextFrontierExpectedState.AMBIGUOUS,
            (),
            "replicate spread remains visible rather than being collapsed to certainty",
            ("ihec-aggregate",),
        ),
        _record(
            "d07-c03-out-domain",
            ChromatinContextFrontierOperation.HISTONE_CONTEXT,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "histone",
                "track_text": h3_foreign.replace("h3k27ac", "histone"),
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "mark": "H3K27ac",
            },
            ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign-context histone overlap is visible as out of domain",
            ("ihec-aggregate",),
        ),
        _record(
            "d07-c04-positive",
            ChromatinContextFrontierOperation.H3K27AC_ACTIVITY,
            ChromatinContextFrontierRole.POSITIVE,
            {
                "track_kind": "h3k27ac",
                "track_text": h3_positive,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "element_id": "enhancer-1",
            },
            ChromatinContextFrontierExpectedState.SUPPORTED,
            (),
            "H3K27ac signal is returned as a context-qualified observation",
            ("roadmap-aggregate",),
        ),
        _record(
            "d07-c04-partial",
            ChromatinContextFrontierOperation.H3K27AC_ACTIVITY,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "h3k27ac",
                "track_text": '{"observations": []}',
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "element_id": "enhancer-2",
            },
            ChromatinContextFrontierExpectedState.ABSTAINED,
            (),
            "no H3K27ac observation yields an explicit abstention",
            ("roadmap-aggregate",),
        ),
        _record(
            "d07-c04-ambiguous",
            ChromatinContextFrontierOperation.H3K27AC_ACTIVITY,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "h3k27ac",
                "track_text": h3_ambiguous,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "element_id": "enhancer-3",
            },
            ChromatinContextFrontierExpectedState.AMBIGUOUS,
            (),
            "replicate-aware H3K27ac activity preserves signal ambiguity",
            ("roadmap-aggregate",),
        ),
        _record(
            "d07-c04-out-domain",
            ChromatinContextFrontierOperation.H3K27AC_ACTIVITY,
            ChromatinContextFrontierRole.CONTROL,
            {
                "track_kind": "h3k27ac",
                "track_text": h3_foreign,
                "chromosome": "chr7",
                "start": 100,
                "end": 120,
                "element_id": "enhancer-4",
            },
            ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign-context H3K27ac signal is not promoted into activity",
            ("roadmap-aggregate",),
        ),
    )
    return ChromatinContextFrontierFixture(
        fixture_id="glio-noncode-d07-c01-c04-public",
        fixture_version=CHROMATIN_CONTEXT_FRONTIER_FIXTURE_VERSION,
        context_key=context,
        evidence_boundary=CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
        sources=_sources(),
        records=records,
    )


def audit_chromatin_context_frontier_data(
    fixture: ChromatinContextFrontierFixture,
) -> ChromatinContextFrontierDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    checks = (
        ChromatinContextFrontierDataCheck(
            "fixture_version",
            fixture.fixture_version == CHROMATIN_CONTEXT_FRONTIER_FIXTURE_VERSION,
            "fixture version is supported",
            fixture.fixture_version,
            CHROMATIN_CONTEXT_FRONTIER_FIXTURE_VERSION,
        ),
        ChromatinContextFrontierDataCheck(
            "aggregate_boundary",
            fixture.evidence_boundary == CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
            "aggregate-only boundary is retained",
            fixture.evidence_boundary,
            CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
        ),
        ChromatinContextFrontierDataCheck(
            "source_count",
            len(fixture.sources) == 5,
            "five public source receipts are present",
            len(fixture.sources),
            5,
        ),
        ChromatinContextFrontierDataCheck(
            "source_addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            "source receipts are content addressed",
        ),
        ChromatinContextFrontierDataCheck(
            "record_count",
            len(fixture.records) == 16,
            "sixteen positive and control records are present",
            len(fixture.records),
            16,
        ),
        ChromatinContextFrontierDataCheck(
            "operation_balance",
            all(
                len(fixture.operation_records(item)) == 4
                for item in ChromatinContextFrontierOperation
            ),
            "each operation has four records",
        ),
        ChromatinContextFrontierDataCheck(
            "context_lock",
            all(item.context_key == fixture.context_key for item in fixture.records),
            "record context keys are locked to the fixture",
        ),
        ChromatinContextFrontierDataCheck(
            "source_links",
            all(not set(item.source_ids) - source_ids for item in fixture.records),
            "every record links to a declared source",
        ),
        ChromatinContextFrontierDataCheck(
            "role_balance",
            len(fixture.positive_records) == 4 and len(fixture.control_records) == 12,
            "positive and control roles are balanced",
            {"positive": len(fixture.positive_records), "control": len(fixture.control_records)},
            {"positive": 4, "control": 12},
        ),
        ChromatinContextFrontierDataCheck(
            "record_addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.records),
            "record payloads are content addressed",
        ),
    )
    accepted = all(item.passed for item in checks)
    return ChromatinContextFrontierDataAudit(fixture.fixture_id, checks, accepted)


__all__ = [
    "CHROMATIN_CONTEXT_FRONTIER_BOUNDARY",
    "CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY",
    "CHROMATIN_CONTEXT_FRONTIER_FIXTURE_VERSION",
    "CHROMATIN_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY",
    "CHROMATIN_CONTEXT_FRONTIER_POSITIVE_COUNT",
    "CHROMATIN_CONTEXT_FRONTIER_CONTROL_COUNT",
    "CHROMATIN_CONTEXT_FRONTIER_SOURCE_COUNT",
    "ChromatinContextFrontierDataAudit",
    "ChromatinContextFrontierDataCheck",
    "ChromatinContextFrontierExpectedState",
    "ChromatinContextFrontierFixture",
    "ChromatinContextFrontierOperation",
    "ChromatinContextFrontierRecord",
    "ChromatinContextFrontierRole",
    "ChromatinContextFrontierSourceReceipt",
    "audit_chromatin_context_frontier_data",
    "default_chromatin_context_frontier_fixture",
]
