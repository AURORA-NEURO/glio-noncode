"""Closed aggregate fixture for Domain 08 C01-C04 context assembly.

The rows represent public cohort-shaped taxonomy observations.  They are not
case records and carry no clinical interpretation.  Every supported path is
paired with controls for malformed input, ambiguity, contradiction, missing
dimensions, or exact-context refusal so the boundary is executable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CELL_CONTEXT_FRONTIER_FIXTURE_VERSION = "2026.08.d08-c01-c04.v1"
CELL_CONTEXT_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
CELL_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|pediatric|stem_like|core|unknown"
CELL_CONTEXT_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
CELL_CONTEXT_FRONTIER_POSITIVE_COUNT = 4
CELL_CONTEXT_FRONTIER_CONTROL_COUNT = 12
CELL_CONTEXT_FRONTIER_SOURCE_COUNT = 5


class CellContextFrontierOperation(StrEnum):
    DISEASE_ONTOLOGY = "disease_ontology_context"
    AGE_ROUTE = "adult_pediatric_route"
    MOLECULAR_STATE = "molecular_class_state"
    TERRITORY_ASSEMBLY = "territory_context_assembly"


class CellContextFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class CellContextFrontierExpectedState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class CellContextFrontierSourceReceipt:
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
            raise ValidationError("context source receipt must use HTTPS")
        if self.context_key != CELL_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("source context is outside the C01-C04 tranche")
        if not self.public_aggregate:
            raise ValidationError("context source receipt must be aggregate")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(self.to_dict(include_address=False)),
            )

    def to_dict(self, *, include_address: bool = True) -> dict[str, Any]:
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
class CellContextFrontierRecord:
    record_id: str
    operation: CellContextFrontierOperation
    role: CellContextFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CellContextFrontierExpectedState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if self.context_key != CELL_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("record context is outside the C01-C04 tranche")
        if not self.source_ids or not self.payload:
            raise ValidationError("context record requires source IDs and payload")
        if not isinstance(self.operation, CellContextFrontierOperation):
            raise ValidationError("context operation must be declared")
        if not isinstance(self.role, CellContextFrontierRole):
            raise ValidationError("context record role must be declared")
        if not isinstance(self.expected_state, CellContextFrontierExpectedState):
            raise ValidationError("context expected state must be declared")
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
class CellContextFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[CellContextFrontierSourceReceipt, ...]
    records: tuple[CellContextFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != CELL_CONTEXT_FRONTIER_FIXTURE_VERSION:
            raise ValidationError("unsupported context fixture version")
        if self.context_key != CELL_CONTEXT_FRONTIER_CONTEXT_KEY:
            raise ValidationError("fixture context does not match C01-C04")
        if self.evidence_boundary != CELL_CONTEXT_FRONTIER_BOUNDARY:
            raise ValidationError("fixture boundary must be aggregate")
        if len(self.sources) != CELL_CONTEXT_FRONTIER_SOURCE_COUNT:
            raise ValidationError("context fixture requires five source receipts")
        expected_count = CELL_CONTEXT_FRONTIER_POSITIVE_COUNT + CELL_CONTEXT_FRONTIER_CONTROL_COUNT
        if len(self.records) != expected_count:
            raise ValidationError("context fixture requires sixteen records")
        if len(self.positive_records) != CELL_CONTEXT_FRONTIER_POSITIVE_COUNT:
            raise ValidationError("context fixture positive count is not four")
        if len(self.control_records) != CELL_CONTEXT_FRONTIER_CONTROL_COUNT:
            raise ValidationError("context fixture control count is not twelve")
        source_ids = {item.source_id for item in self.sources}
        if any(set(item.source_ids) - source_ids for item in self.records):
            raise ValidationError("context record references undeclared source")
        if len({item.record_id for item in self.records}) != len(self.records):
            raise ValidationError("context record IDs must be unique")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(self.to_dict(include_payload=True, include_address=False)),
            )

    @property
    def positive_records(self) -> tuple[CellContextFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CellContextFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[CellContextFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is CellContextFrontierRole.CONTROL)

    def operation_records(
        self, operation: CellContextFrontierOperation
    ) -> tuple[CellContextFrontierRecord, ...]:
        return tuple(item for item in self.records if item.operation is operation)

    def source_map(self) -> dict[str, CellContextFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CellContextFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(
        self, *, include_payload: bool = False, include_address: bool = True
    ) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "evidence_boundary": self.evidence_boundary,
            "sources": [item.to_dict() for item in self.sources],
            "records": [item.to_dict(include_payload=include_payload) for item in self.records],
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CellContextFrontierDataCheck:
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
class CellContextFrontierDataAudit:
    fixture_id: str
    checks: tuple[CellContextFrontierDataCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("context data audit is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _observation_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"observations": rows}, sort_keys=True, separators=(",", ":"))


def _row(
    observation_id: str,
    dimension: str,
    candidate_id: str,
    candidate_label: str,
    *,
    context_key: str = CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
    confidence: float = 0.9,
    subject_id: str = "aggregate-cohort",
    state: str = "supported",
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "subject_id": subject_id,
        "dimension": dimension,
        "candidate_id": candidate_id,
        "candidate_label": candidate_label,
        "context_key": context_key,
        "source_version": "context-aggregate-2026-01",
        "confidence": confidence,
        "state": state,
    }


def _assembly_rows(
    *,
    territory: str = "malignant_core",
    territory_label: str = "malignant core",
    context_key: str = CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
) -> list[dict[str, Any]]:
    return [
        _row(
            "assembly-disease",
            "disease_ontology",
            "MONDO:001",
            "diffuse glioma",
            context_key=context_key,
        ),
        _row("assembly-age", "age_route", "adult", "adult", context_key=context_key),
        _row(
            "assembly-class", "molecular_class", "IDH_mutant", "IDH-mutant", context_key=context_key
        ),
        _row(
            "assembly-state", "molecular_state", "proneural", "proneural", context_key=context_key
        ),
        _row(
            "assembly-territory", "territory", territory, territory_label, context_key=context_key
        ),
    ]


def _record(
    record_id: str,
    operation: CellContextFrontierOperation,
    role: CellContextFrontierRole,
    payload: Mapping[str, Any],
    expected_state: CellContextFrontierExpectedState,
    expected_issue_codes: tuple[str, ...],
    description: str,
    source_ids: tuple[str, ...] = ("cell-atlas-aggregate",),
) -> CellContextFrontierRecord:
    return CellContextFrontierRecord(
        record_id,
        operation,
        role,
        CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
        source_ids,
        payload,
        expected_state,
        expected_issue_codes,
        description,
    )


def _sources() -> tuple[CellContextFrontierSourceReceipt, ...]:
    context = CELL_CONTEXT_FRONTIER_CONTEXT_KEY
    return (
        CellContextFrontierSourceReceipt(
            "cell-atlas-aggregate",
            "Cell Atlas public metadata index",
            "https://www.humancellatlas.org/",
            "atlas_index",
            "2026-01",
            "public aggregate cell-state context descriptors",
            context,
        ),
        CellContextFrontierSourceReceipt(
            "mondo-aggregate",
            "MONDO disease ontology release",
            "https://mondo.monarchinitiative.org/",
            "ontology_release",
            "2025-12",
            "public aggregate disease term mappings",
            context,
        ),
        CellContextFrontierSourceReceipt(
            "ncit-aggregate",
            "NCIt public terminology service",
            "https://evsexplore.semantics.cancer.gov/evsexplore/",
            "terminology_release",
            "2025-11",
            "public aggregate cancer terminology mappings",
            context,
        ),
        CellContextFrontierSourceReceipt(
            "gtex-aggregate",
            "GTEx public tissue context summaries",
            "https://gtexportal.org/home/",
            "tissue_summary",
            "2025-10",
            "public aggregate tissue and age context",
            context,
        ),
        CellContextFrontierSourceReceipt(
            "hca-aggregate",
            "Human Cell Atlas public data portal",
            "https://data.humancellatlas.org/",
            "cell_context_catalogue",
            "2026-02",
            "public aggregate cell state and territory descriptors",
            context,
        ),
    )


def default_cell_context_frontier_fixture() -> CellContextFrontierFixture:
    """Build the deterministic public aggregate fixture for C01-C04."""

    context = CELL_CONTEXT_FRONTIER_CONTEXT_KEY
    foreign = CELL_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY
    disease_positive = _observation_json(
        [_row("disease-supported", "disease_ontology", "MONDO:001", "diffuse glioma")]
    )
    disease_partial = _observation_json(
        [
            _row("disease-partial", "disease_ontology", "MONDO:001", "diffuse glioma"),
            {"dimension": "disease_ontology", "candidate_id": "MONDO:bad"},
        ]
    )
    disease_ambiguous = _observation_json(
        [
            _row("disease-a", "disease_ontology", "MONDO:001", "diffuse glioma"),
            _row("disease-b", "disease_ontology", "MONDO:002", "other glioma"),
        ]
    )
    disease_foreign = _observation_json(
        [
            _row(
                "disease-foreign",
                "disease_ontology",
                "MONDO:999",
                "foreign context",
                context_key=foreign,
            )
        ]
    )

    age_positive = _observation_json([_row("age-supported", "age_route", "adult", "adult")])
    age_partial = _observation_json(
        [
            _row("age-partial", "age_route", "adult", "adult"),
            {"dimension": "bad_dimension", "candidate_id": "x"},
        ]
    )
    age_conflict = _observation_json([_row("age-conflict", "age_route", "pediatric", "pediatric")])
    age_foreign = _observation_json(
        [_row("age-foreign", "age_route", "pediatric", "pediatric", context_key=foreign)]
    )

    molecular_positive = _observation_json(
        [
            _row("class-supported", "molecular_class", "IDH_mutant", "IDH-mutant"),
            _row("state-supported", "molecular_state", "proneural", "proneural"),
        ]
    )
    molecular_partial = _observation_json(
        [
            _row("class-partial", "molecular_class", "IDH_mutant", "IDH-mutant"),
            {"dimension": "molecular_state", "candidate_id": "bad"},
        ]
    )
    molecular_ambiguous = _observation_json(
        [
            _row("class-a", "molecular_class", "IDH_mutant", "IDH-mutant"),
            _row("class-b", "molecular_class", "IDH_wildtype", "IDH-wildtype"),
            _row("state-a", "molecular_state", "proneural", "proneural"),
        ]
    )
    molecular_foreign = _observation_json(
        [
            _row(
                "class-foreign", "molecular_class", "IDH_mutant", "IDH-mutant", context_key=foreign
            ),
            _row("state-foreign", "molecular_state", "proneural", "proneural", context_key=foreign),
        ]
    )

    territory_positive = _observation_json(_assembly_rows())
    territory_partial = _observation_json(
        _assembly_rows() + [{"dimension": "territory", "candidate_id": "bad"}]
    )
    territory_ambiguous = _observation_json(
        _assembly_rows() + [_row("assembly-territory-2", "territory", "immune_edge", "immune edge")]
    )
    territory_foreign = _observation_json(_assembly_rows(context_key=foreign))

    records = (
        _record(
            "d08-c01-positive",
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            CellContextFrontierRole.POSITIVE,
            {"observation_text": disease_positive},
            CellContextFrontierExpectedState.SUPPORTED,
            (),
            "one exact-context disease ontology candidate remains",
        ),
        _record(
            "d08-c01-partial",
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            CellContextFrontierRole.CONTROL,
            {"observation_text": disease_partial},
            CellContextFrontierExpectedState.PARTIAL,
            ("invalid_context_row",),
            "valid disease context survives beside malformed taxonomy input",
        ),
        _record(
            "d08-c01-ambiguous",
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            CellContextFrontierRole.CONTROL,
            {"observation_text": disease_ambiguous},
            CellContextFrontierExpectedState.AMBIGUOUS,
            (),
            "two exact-context disease candidates remain visible",
        ),
        _record(
            "d08-c01-out-domain",
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            CellContextFrontierRole.CONTROL,
            {"observation_text": disease_foreign},
            CellContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign-context disease term is not transported",
        ),
        _record(
            "d08-c02-positive",
            CellContextFrontierOperation.AGE_ROUTE,
            CellContextFrontierRole.POSITIVE,
            {"observation_text": age_positive},
            CellContextFrontierExpectedState.SUPPORTED,
            (),
            "adult route agrees with declared context",
            ("gtex-aggregate",),
        ),
        _record(
            "d08-c02-partial",
            CellContextFrontierOperation.AGE_ROUTE,
            CellContextFrontierRole.CONTROL,
            {"observation_text": age_partial},
            CellContextFrontierExpectedState.PARTIAL,
            ("invalid_context_row",),
            "age route survives a quarantined malformed row",
            ("gtex-aggregate",),
        ),
        _record(
            "d08-c02-ambiguous",
            CellContextFrontierOperation.AGE_ROUTE,
            CellContextFrontierRole.CONTROL,
            {"observation_text": age_conflict},
            CellContextFrontierExpectedState.CONTRADICTORY,
            (),
            "pediatric evidence conflicts with declared adult route",
            ("gtex-aggregate",),
        ),
        _record(
            "d08-c02-out-domain",
            CellContextFrontierOperation.AGE_ROUTE,
            CellContextFrontierRole.CONTROL,
            {"observation_text": age_foreign},
            CellContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign-context age route is refused",
            ("gtex-aggregate",),
        ),
        _record(
            "d08-c03-positive",
            CellContextFrontierOperation.MOLECULAR_STATE,
            CellContextFrontierRole.POSITIVE,
            {"observation_text": molecular_positive},
            CellContextFrontierExpectedState.SUPPORTED,
            (),
            "molecular class and state resolve separately and agree",
            ("ncit-aggregate",),
        ),
        _record(
            "d08-c03-partial",
            CellContextFrontierOperation.MOLECULAR_STATE,
            CellContextFrontierRole.CONTROL,
            {"observation_text": molecular_partial},
            CellContextFrontierExpectedState.ABSTAINED,
            ("invalid_context_row",),
            "molecular class remains while missing state input abstains",
            ("ncit-aggregate",),
        ),
        _record(
            "d08-c03-ambiguous",
            CellContextFrontierOperation.MOLECULAR_STATE,
            CellContextFrontierRole.CONTROL,
            {"observation_text": molecular_ambiguous},
            CellContextFrontierExpectedState.AMBIGUOUS,
            (),
            "multiple molecular class candidates remain after exact gating",
            ("ncit-aggregate",),
        ),
        _record(
            "d08-c03-out-domain",
            CellContextFrontierOperation.MOLECULAR_STATE,
            CellContextFrontierRole.CONTROL,
            {"observation_text": molecular_foreign},
            CellContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign molecular context is not transported",
            ("ncit-aggregate",),
        ),
        _record(
            "d08-c04-positive",
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            CellContextFrontierRole.POSITIVE,
            {"observation_text": territory_positive},
            CellContextFrontierExpectedState.SUPPORTED,
            (),
            "territory and other context dimensions assemble to supported",
            ("hca-aggregate",),
        ),
        _record(
            "d08-c04-partial",
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            CellContextFrontierRole.CONTROL,
            {"observation_text": territory_partial},
            CellContextFrontierExpectedState.PARTIAL,
            ("invalid_context_row",),
            "context assembly retains valid dimensions beside malformed input",
            ("hca-aggregate",),
        ),
        _record(
            "d08-c04-ambiguous",
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            CellContextFrontierRole.CONTROL,
            {"observation_text": territory_ambiguous},
            CellContextFrontierExpectedState.AMBIGUOUS,
            (),
            "one-to-many territory candidates propagate through assembly",
            ("hca-aggregate",),
        ),
        _record(
            "d08-c04-out-domain",
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            CellContextFrontierRole.CONTROL,
            {"observation_text": territory_foreign},
            CellContextFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign territory bundle is refused",
            ("hca-aggregate",),
        ),
    )
    return CellContextFrontierFixture(
        "glio-noncode-d08-c01-c04-public",
        CELL_CONTEXT_FRONTIER_FIXTURE_VERSION,
        context,
        CELL_CONTEXT_FRONTIER_BOUNDARY,
        _sources(),
        records,
    )


def audit_cell_context_frontier_data(
    fixture: CellContextFrontierFixture,
) -> CellContextFrontierDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    checks = (
        CellContextFrontierDataCheck(
            "fixture_version",
            fixture.fixture_version == CELL_CONTEXT_FRONTIER_FIXTURE_VERSION,
            "fixture version is supported",
            fixture.fixture_version,
            CELL_CONTEXT_FRONTIER_FIXTURE_VERSION,
        ),
        CellContextFrontierDataCheck(
            "aggregate_boundary",
            fixture.evidence_boundary == CELL_CONTEXT_FRONTIER_BOUNDARY,
            "aggregate boundary is exact",
            fixture.evidence_boundary,
            CELL_CONTEXT_FRONTIER_BOUNDARY,
        ),
        CellContextFrontierDataCheck(
            "source_count",
            len(fixture.sources) == 5,
            "five public source receipts are present",
            len(fixture.sources),
            5,
        ),
        CellContextFrontierDataCheck(
            "source_addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            "source receipts are content addressed",
        ),
        CellContextFrontierDataCheck(
            "record_count",
            len(fixture.records) == 16,
            "sixteen positive and control records are present",
            len(fixture.records),
            16,
        ),
        CellContextFrontierDataCheck(
            "operation_balance",
            all(len(fixture.operation_records(item)) == 4 for item in CellContextFrontierOperation),
            "each context operation has four records",
        ),
        CellContextFrontierDataCheck(
            "context_lock",
            all(item.context_key == fixture.context_key for item in fixture.records),
            "record context keys are locked",
        ),
        CellContextFrontierDataCheck(
            "source_links",
            all(not set(item.source_ids) - source_ids for item in fixture.records),
            "every record links to a declared source",
        ),
        CellContextFrontierDataCheck(
            "role_balance",
            len(fixture.positive_records) == 4 and len(fixture.control_records) == 12,
            "positive and control roles are balanced",
        ),
        CellContextFrontierDataCheck(
            "record_addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.records),
            "record payloads are content addressed",
        ),
    )
    return CellContextFrontierDataAudit(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CELL_CONTEXT_FRONTIER_BOUNDARY",
    "CELL_CONTEXT_FRONTIER_CONTEXT_KEY",
    "CELL_CONTEXT_FRONTIER_CONTROL_COUNT",
    "CELL_CONTEXT_FRONTIER_FIXTURE_VERSION",
    "CELL_CONTEXT_FRONTIER_FOREIGN_CONTEXT_KEY",
    "CELL_CONTEXT_FRONTIER_POSITIVE_COUNT",
    "CELL_CONTEXT_FRONTIER_SOURCE_COUNT",
    "CellContextFrontierDataAudit",
    "CellContextFrontierDataCheck",
    "CellContextFrontierExpectedState",
    "CellContextFrontierFixture",
    "CellContextFrontierOperation",
    "CellContextFrontierRecord",
    "CellContextFrontierRole",
    "CellContextFrontierSourceReceipt",
    "audit_cell_context_frontier_data",
    "default_cell_context_frontier_fixture",
]
