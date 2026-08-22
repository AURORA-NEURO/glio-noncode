"""Closed public aggregate fixture for Domain 09 C01-C04."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

TOPOLOGY_CONTEXT_FRONTIER_FIXTURE_VERSION = "2026.08.d09-c01-c04.v1"
TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
TOPOLOGY_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
TOPOLOGY_CONTEXT_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
TOPOLOGY_CONTEXT_FRONTIER_POSITIVE_COUNT = 4
TOPOLOGY_CONTEXT_FRONTIER_CONTROL_COUNT = 12
TOPOLOGY_CONTEXT_FRONTIER_SOURCE_COUNT = 4


class TopologyContextFrontierOperation(StrEnum):
    CONTACT_IMPORT = "contact_import"
    MATRIX_QC = "matrix_qc"
    BOUNDARY_ENSEMBLE = "boundary_ensemble"
    INSULATION_DELTA = "insulation_delta"


class TopologyContextFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class TopologyContextFrontierExpectedState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierSourceReceipt:
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
        for name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "scope",
            "context_key",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("topology source receipt must use HTTPS")
        if self.context_key != TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("topology source receipt must use the anchor context")
        if not self.public_aggregate:
            raise ValidationError("topology source receipt must be aggregate")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
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
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierRecord:
    record_id: str
    operation: TopologyContextFrontierOperation
    role: TopologyContextFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: TopologyContextFrontierExpectedState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("topology record requires source IDs")
        if not isinstance(self.payload, Mapping):
            raise ValidationError("topology record payload must be a mapping")
        if not self.payload.get("public_aggregate", False):
            raise ValidationError("topology record must be aggregate")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
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
        if include_address:
            value["content_address"] = self.content_address
        return jsonable(value)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[TopologyContextFrontierSourceReceipt, ...]
    records: tuple[TopologyContextFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.version, "version")
        if self.boundary != TOPOLOGY_CONTEXT_FRONTIER_BOUNDARY:
            raise ValidationError("topology fixture boundary is not supported")
        if self.context_key != TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("topology fixture context is not the anchor")
        if len(self.records) != 16:
            raise ValidationError("topology fixture requires sixteen records")
        source_ids = {item.source_id for item in self.sources}
        if len(source_ids) != TOPOLOGY_CONTEXT_FRONTIER_SOURCE_COUNT:
            raise ValidationError("topology fixture requires four source receipts")
        if any(not set(item.source_ids) <= source_ids for item in self.records):
            raise ValidationError("topology record references an unknown source")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def positive_records(self) -> tuple[TopologyContextFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is TopologyContextFrontierRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[TopologyContextFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is TopologyContextFrontierRole.CONTROL
        )

    def operation_records(
        self, operation: TopologyContextFrontierOperation | str
    ) -> tuple[TopologyContextFrontierRecord, ...]:
        value = TopologyContextFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "boundary": self.boundary,
            "context_key": self.context_key,
            "sources": [item.to_dict() for item in self.sources],
            "records": [item.to_dict() for item in self.records],
        }
        if include_address:
            value["content_address"] = self.content_address
        return jsonable(value)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierDataCheck:
    check_id: str
    passed: bool
    observed: int | str
    expected: int | str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierDataAudit:
    checks: tuple[TopologyContextFrontierDataCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "failed_ids": self.failed_ids,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def _contact_row(
    row_id: str,
    *,
    context_key: str = TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
    signal: float = 10.0,
    start_a: int = 99,
    end_a: int = 120,
    start_b: int = 299,
    end_b: int = 320,
    assay: str = "hi-c",
) -> dict[str, Any]:
    return {
        "interaction_id": row_id,
        "assay": assay,
        "chromosome_a": "7",
        "start_a": start_a,
        "end_a": end_a,
        "chromosome_b": "7",
        "start_b": start_b,
        "end_b": end_b,
        "signal": signal,
        "context_key": context_key,
        "source_version": "aggregate-topology-2026-01",
    }


def _boundary_row(
    row_id: str,
    *,
    context_key: str = TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
    position: int = 1000,
    assay: str = "hi-c",
    score: float = 0.8,
) -> dict[str, Any]:
    return {
        "boundary_id": row_id,
        "assay": assay,
        "chromosome": "7",
        "position": position,
        "score": score,
        "context_key": context_key,
        "source_version": "aggregate-boundary-2026-01",
        "caller_id": f"caller-{assay}",
    }


def _payload(
    *,
    target_context_key: str = TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
    contacts: list[dict[str, Any]] | None = None,
    boundaries: list[dict[str, Any]] | None = None,
    measurement: dict[str, Any] | None = None,
    normalization_method: str = "mean",
) -> dict[str, Any]:
    return {
        "public_aggregate": True,
        "target_context_key": target_context_key,
        "normalization_method": normalization_method,
        "contacts": contacts or [],
        "boundaries": boundaries or [],
        "measurement": measurement,
    }


def _record(
    record_id: str,
    operation: TopologyContextFrontierOperation,
    role: TopologyContextFrontierRole,
    payload: dict[str, Any],
    expected_state: TopologyContextFrontierExpectedState,
    issue_codes: tuple[str, ...],
    description: str,
    *,
    context_key: str = TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
    source_id: str = "topology-contact-aggregate",
) -> TopologyContextFrontierRecord:
    return TopologyContextFrontierRecord(
        record_id=record_id,
        operation=operation,
        role=role,
        context_key=context_key,
        source_ids=(source_id,),
        payload=payload,
        expected_state=expected_state,
        expected_issue_codes=issue_codes,
        description=description,
    )


def _sources() -> tuple[TopologyContextFrontierSourceReceipt, ...]:
    return (
        TopologyContextFrontierSourceReceipt(
            "topology-contact-aggregate",
            "ENCODE public chromatin contact references",
            "https://www.encodeproject.org/",
            "contact_aggregate",
            "2026-01",
            "aggregate contact observations",
            TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
        ),
        TopologyContextFrontierSourceReceipt(
            "topology-boundary-aggregate",
            "4DN public boundary references",
            "https://data.4dnucleome.org/",
            "boundary_aggregate",
            "2026-01",
            "aggregate boundary calls",
            TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
        ),
        TopologyContextFrontierSourceReceipt(
            "topology-insulation-aggregate",
            "NCBI GEO public topology references",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "insulation_aggregate",
            "2026-01",
            "aggregate insulation comparisons",
            TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
        ),
        TopologyContextFrontierSourceReceipt(
            "topology-method-aggregate",
            "ENCODE data standards and assay descriptions",
            "https://www.encodeproject.org/data-standards/",
            "method_reference",
            "2026-01",
            "assay and coordinate interpretation",
            TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
        ),
    )


def default_topology_context_frontier_fixture() -> TopologyContextFrontierFixture:
    invalid_contact = {"interaction_id": "invalid-contact", "context_key": ""}
    records = (
        _record(
            "D09-C01-P",
            TopologyContextFrontierOperation.CONTACT_IMPORT,
            TopologyContextFrontierRole.POSITIVE,
            _payload(contacts=[_contact_row("contact-positive")]),
            TopologyContextFrontierExpectedState.SUPPORTED,
            (),
            "one anchor-context contact is imported and retrieved",
        ),
        _record(
            "D09-C01-I",
            TopologyContextFrontierOperation.CONTACT_IMPORT,
            TopologyContextFrontierRole.CONTROL,
            _payload(contacts=[_contact_row("contact-partial"), invalid_contact]),
            TopologyContextFrontierExpectedState.PARTIAL,
            ("invalid_contact_row",),
            "one malformed contact is quarantined beside a valid row",
        ),
        _record(
            "D09-C01-A",
            TopologyContextFrontierOperation.CONTACT_IMPORT,
            TopologyContextFrontierRole.CONTROL,
            _payload(contacts=[_contact_row("contact-a"), _contact_row("contact-b", signal=7.0)]),
            TopologyContextFrontierExpectedState.AMBIGUOUS,
            (),
            "two matching contacts retain a replicate ambiguity state",
        ),
        _record(
            "D09-C01-O",
            TopologyContextFrontierOperation.CONTACT_IMPORT,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                contacts=[
                    _contact_row(
                        "contact-foreign", context_key=TOPOLOGY_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY
                    )
                ]
            ),
            TopologyContextFrontierExpectedState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            "overlapping contact evidence belongs to a foreign cell context",
        ),
        _record(
            "D09-C02-P",
            TopologyContextFrontierOperation.MATRIX_QC,
            TopologyContextFrontierRole.POSITIVE,
            _payload(
                contacts=[
                    _contact_row("qc-a"),
                    _contact_row(
                        "qc-b", start_a=499, end_a=520, start_b=699, end_b=720, signal=5.0
                    ),
                ]
            ),
            TopologyContextFrontierExpectedState.SUPPORTED,
            (),
            "unique positive contact pairs pass matrix QC",
        ),
        _record(
            "D09-C02-I",
            TopologyContextFrontierOperation.MATRIX_QC,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                contacts=[
                    _contact_row("qc-duplicate"),
                    _contact_row("qc-reverse", signal=4.0),
                    _contact_row(
                        "qc-zero", start_a=499, end_a=520, start_b=699, end_b=720, signal=0.0
                    ),
                ]
            ),
            TopologyContextFrontierExpectedState.PARTIAL,
            (),
            "duplicate and zero-signal rows remain visible in QC",
        ),
        _record(
            "D09-C02-A",
            TopologyContextFrontierOperation.MATRIX_QC,
            TopologyContextFrontierRole.CONTROL,
            _payload(),
            TopologyContextFrontierExpectedState.ABSTAINED,
            ("no_contact_rows",),
            "an empty matrix abstains rather than producing a summary",
        ),
        _record(
            "D09-C02-O",
            TopologyContextFrontierOperation.MATRIX_QC,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                contacts=[
                    _contact_row(
                        "qc-foreign", context_key=TOPOLOGY_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY
                    )
                ]
            ),
            TopologyContextFrontierExpectedState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            "foreign-context matrix rows are excluded from QC",
        ),
        _record(
            "D09-C03-P",
            TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE,
            TopologyContextFrontierRole.POSITIVE,
            _payload(
                boundaries=[
                    _boundary_row("boundary-hi"),
                    _boundary_row("boundary-micro", position=1010, assay="micro-c", score=0.9),
                ]
            ),
            TopologyContextFrontierExpectedState.SUPPORTED,
            (),
            "two assays agree on a context-qualified boundary cluster",
            source_id="topology-boundary-aggregate",
        ),
        _record(
            "D09-C03-I",
            TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE,
            TopologyContextFrontierRole.CONTROL,
            _payload(boundaries=[_boundary_row("boundary-single")]),
            TopologyContextFrontierExpectedState.PARTIAL,
            (),
            "a single assay boundary retains a partial state",
            source_id="topology-boundary-aggregate",
        ),
        _record(
            "D09-C03-A",
            TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                boundaries=[
                    _boundary_row("boundary-left", position=1000),
                    _boundary_row("boundary-right", position=3000, assay="micro-c"),
                ]
            ),
            TopologyContextFrontierExpectedState.AMBIGUOUS,
            (),
            "equally supported boundary clusters remain ambiguous",
            source_id="topology-boundary-aggregate",
        ),
        _record(
            "D09-C03-O",
            TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                boundaries=[
                    _boundary_row(
                        "boundary-foreign",
                        context_key=TOPOLOGY_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY,
                    )
                ]
            ),
            TopologyContextFrontierExpectedState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            "boundary evidence in a foreign context is out of domain",
            source_id="topology-boundary-aggregate",
        ),
        _record(
            "D09-C04-P",
            TopologyContextFrontierOperation.INSULATION_DELTA,
            TopologyContextFrontierRole.POSITIVE,
            _payload(
                measurement={
                    "measurement_id": "insulation-positive",
                    "variant_id": "v-positive",
                    "reference_score": 0.4,
                    "alternate_score": 0.2,
                    "replicate_count": 2,
                }
            ),
            TopologyContextFrontierExpectedState.SUPPORTED,
            (),
            "reference-to-alternate insulation delta is computed",
            source_id="topology-insulation-aggregate",
        ),
        _record(
            "D09-C04-I",
            TopologyContextFrontierOperation.INSULATION_DELTA,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                measurement={
                    "measurement_id": "insulation-missing",
                    "variant_id": "v-missing",
                    "reference_score": None,
                    "alternate_score": 0.2,
                }
            ),
            TopologyContextFrontierExpectedState.ABSTAINED,
            ("missing_insulation_score",),
            "a missing reference score prevents the delta estimate",
            source_id="topology-insulation-aggregate",
        ),
        _record(
            "D09-C04-A",
            TopologyContextFrontierOperation.INSULATION_DELTA,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                measurement={
                    "measurement_id": "insulation-invalid",
                    "variant_id": "v-invalid",
                    "reference_score": "bad",
                    "alternate_score": 0.2,
                }
            ),
            TopologyContextFrontierExpectedState.INVALID,
            ("invalid_insulation_score",),
            "a nonnumeric score is rejected at the adapter boundary",
            source_id="topology-insulation-aggregate",
        ),
        _record(
            "D09-C04-O",
            TopologyContextFrontierOperation.INSULATION_DELTA,
            TopologyContextFrontierRole.CONTROL,
            _payload(
                target_context_key=TOPOLOGY_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY,
                measurement={
                    "measurement_id": "insulation-foreign",
                    "variant_id": "v-foreign",
                    "reference_score": 0.4,
                    "alternate_score": 0.2,
                },
            ),
            TopologyContextFrontierExpectedState.OUT_OF_DOMAIN,
            ("context_mismatch",),
            "an otherwise valid insulation row declares a foreign target context",
            source_id="topology-insulation-aggregate",
        ),
    )
    return TopologyContextFrontierFixture(
        fixture_id="topology-context-frontier-public-aggregate",
        version=TOPOLOGY_CONTEXT_FRONTIER_FIXTURE_VERSION,
        boundary=TOPOLOGY_CONTEXT_FRONTIER_BOUNDARY,
        context_key=TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
        sources=_sources(),
        records=records,
    )


def audit_topology_context_frontier_data(
    fixture: TopologyContextFrontierFixture | None = None,
) -> TopologyContextFrontierDataAudit:
    value = fixture or default_topology_context_frontier_fixture()
    checks = (
        TopologyContextFrontierDataCheck(
            "fixture-record-count",
            len(value.records) == 16,
            len(value.records),
            16,
            "sixteen bounded operation records are present",
        ),
        TopologyContextFrontierDataCheck(
            "positive-record-count",
            len(value.positive_records) == TOPOLOGY_CONTEXT_FRONTIER_POSITIVE_COUNT,
            len(value.positive_records),
            TOPOLOGY_CONTEXT_FRONTIER_POSITIVE_COUNT,
            "one positive path exists for every operation",
        ),
        TopologyContextFrontierDataCheck(
            "control-record-count",
            len(value.control_records) == TOPOLOGY_CONTEXT_FRONTIER_CONTROL_COUNT,
            len(value.control_records),
            TOPOLOGY_CONTEXT_FRONTIER_CONTROL_COUNT,
            "three controls exist for every operation",
        ),
        TopologyContextFrontierDataCheck(
            "source-receipt-count",
            len(value.sources) == TOPOLOGY_CONTEXT_FRONTIER_SOURCE_COUNT,
            len(value.sources),
            TOPOLOGY_CONTEXT_FRONTIER_SOURCE_COUNT,
            "four public source receipts are closed",
        ),
        TopologyContextFrontierDataCheck(
            "anchor-context-closure",
            all(item.context_key == value.context_key for item in value.sources),
            value.context_key,
            TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
            "source receipts share the declared anchor context",
        ),
        TopologyContextFrontierDataCheck(
            "aggregate-payload-closure",
            all(item.payload.get("public_aggregate") is True for item in value.records),
            len(value.records),
            len(value.records),
            "every payload is explicitly aggregate",
        ),
        TopologyContextFrontierDataCheck(
            "no-subject-payload-keys",
            all("subject_id" not in json.dumps(item.payload) for item in value.records),
            0,
            0,
            "no subject-level payload key is present",
        ),
        TopologyContextFrontierDataCheck(
            "content-address-closure",
            bool(value.content_address) and all(item.content_address for item in value.records),
            len(value.records),
            len(value.records),
            "fixture and records have content addresses",
        ),
    )
    return TopologyContextFrontierDataAudit(
        checks=checks,
        accepted=all(item.passed for item in checks),
    )


__all__ = [
    "TOPOLOGY_CONTEXT_FRONTIER_BOUNDARY",
    "TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY",
    "TOPOLOGY_CONTEXT_FRONTIER_CONTROL_COUNT",
    "TOPOLOGY_CONTEXT_FRONTIER_FIXTURE_VERSION",
    "TOPOLOGY_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY",
    "TOPOLOGY_CONTEXT_FRONTIER_POSITIVE_COUNT",
    "TOPOLOGY_CONTEXT_FRONTIER_SOURCE_COUNT",
    "TopologyContextFrontierDataAudit",
    "TopologyContextFrontierDataCheck",
    "TopologyContextFrontierExpectedState",
    "TopologyContextFrontierFixture",
    "TopologyContextFrontierOperation",
    "TopologyContextFrontierRecord",
    "TopologyContextFrontierRole",
    "TopologyContextFrontierSourceReceipt",
    "audit_topology_context_frontier_data",
    "default_topology_context_frontier_fixture",
]
