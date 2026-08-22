"""Closed public aggregate fixture for Domain 08 C09-C12."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CELL_CONTEXT_ALPHA_FRONTIER_FIXTURE_VERSION = "2026.08.d08-c09-c12.v1"
CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CELL_CONTEXT_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|pediatric|stem_like|tumor|unknown"
CELL_CONTEXT_ALPHA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
CELL_CONTEXT_ALPHA_FRONTIER_POSITIVE_COUNT = 4
CELL_CONTEXT_ALPHA_FRONTIER_CONTROL_COUNT = 12
CELL_CONTEXT_ALPHA_FRONTIER_SOURCE_COUNT = 4


class CellContextAlphaFrontierOperation(StrEnum):
    SPATIAL_NICHE = "spatial_niche_prior"
    CORE_MARGIN = "core_margin_territory_prior"
    RECURRENCE_STATE = "recurrence_state_prior"
    TREATMENT_INDUCED = "treatment_induced_state_prior"


class CellContextAlphaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class CellContextAlphaFrontierExpectedState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    CONTRADICTORY = "contradictory"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierSourceReceipt:
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
        for name in ("source_id", "title", "uri", "source_kind", "release", "scope", "context_key"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("alpha source receipt must use HTTPS")
        if self.context_key != CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("alpha source receipt must use the tranche anchor")
        if not self.public_aggregate:
            raise ValidationError("alpha source receipt must be aggregate")
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
class CellContextAlphaFrontierRecord:
    record_id: str
    operation: CellContextAlphaFrontierOperation
    role: CellContextAlphaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CellContextAlphaFrontierExpectedState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if self.context_key != CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("alpha record context must use the tranche anchor")
        if not self.source_ids or not self.payload:
            raise ValidationError("alpha record needs source IDs and payload")
        if not isinstance(self.operation, CellContextAlphaFrontierOperation) or not isinstance(
            self.role, CellContextAlphaFrontierRole
        ):
            raise ValidationError("alpha record enum fields are invalid")
        restricted = {
            "patient",
            "subject",
            "sample_id",
            "donor_id",
            "participant_id",
            "individual_id",
        }
        if any(str(key).lower() in restricted for key in self.payload):
            raise ValidationError("alpha payload cannot contain subject-level keys")
        if str(self.payload.get("target_context_key", "")) not in {
            CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY,
            CELL_CONTEXT_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY,
        }:
            raise ValidationError("alpha target context is not declared")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(True, False)))

    def to_dict(self, include_payload: bool = True, include_address: bool = True) -> dict[str, Any]:
        value = {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "role": self.role.value,
            "context_key": self.context_key,
            "source_ids": list(self.source_ids),
            "expected_state": self.expected_state.value,
            "expected_issue_codes": list(self.expected_issue_codes),
            "description": self.description,
        }
        if include_payload:
            value["payload"] = jsonable(self.payload)
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[CellContextAlphaFrontierSourceReceipt, ...]
    records: tuple[CellContextAlphaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            self.fixture_version != CELL_CONTEXT_ALPHA_FRONTIER_FIXTURE_VERSION
            or self.context_key != CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY
        ):
            raise ValidationError("unsupported alpha fixture identity")
        if self.evidence_boundary != CELL_CONTEXT_ALPHA_FRONTIER_BOUNDARY:
            raise ValidationError("alpha fixture must be aggregate")
        if len(self.sources) != 4 or len(self.records) != 16:
            raise ValidationError("alpha fixture requires four sources and sixteen records")
        if len(self.positive_records) != 4 or len(self.control_records) != 12:
            raise ValidationError("alpha fixture positive and control counts are invalid")
        source_ids = {item.source_id for item in self.sources}
        if any(set(item.source_ids) - source_ids for item in self.records):
            raise ValidationError("alpha record references undeclared source")
        if len({item.record_id for item in self.records}) != len(self.records):
            raise ValidationError("alpha record IDs must be unique")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(True, False)))

    @property
    def positive_records(self) -> tuple[CellContextAlphaFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is CellContextAlphaFrontierRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[CellContextAlphaFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is CellContextAlphaFrontierRole.CONTROL
        )

    def operation_records(
        self, operation: CellContextAlphaFrontierOperation
    ) -> tuple[CellContextAlphaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.operation is operation)

    def source_map(self) -> dict[str, CellContextAlphaFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CellContextAlphaFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(
        self, include_payload: bool = False, include_address: bool = True
    ) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "evidence_boundary": self.evidence_boundary,
            "sources": [item.to_dict() for item in self.sources],
            "records": [item.to_dict(include_payload) for item in self.records],
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("alpha data check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierDataAudit:
    fixture_id: str
    checks: tuple[CellContextAlphaFrontierDataCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("alpha data audit is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _row(
    observation_id: str,
    context_key: str,
    values: Mapping[str, Any],
    *,
    subject_id: str = "aggregate-cohort",
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "subject_id": subject_id,
        "context_key": context_key,
        "source_id": "alpha-aggregate",
        "source_version": "aggregate-alpha-2026-01",
        "sample_id": "aggregate-a",
        **dict(values),
    }


def _payload(target: str, rows: list[dict[str, Any]], **params: Any) -> dict[str, Any]:
    return {
        "target_context_key": target,
        "observation_text": json.dumps(
            {"observations": rows}, sort_keys=True, separators=(",", ":")
        ),
        "source_version": "aggregate-alpha-2026-01",
        **params,
    }


def _record(
    record_id: str,
    operation: CellContextAlphaFrontierOperation,
    role: CellContextAlphaFrontierRole,
    payload: Mapping[str, Any],
    state: CellContextAlphaFrontierExpectedState,
    issues: tuple[str, ...],
    description: str,
    source_id: str,
) -> CellContextAlphaFrontierRecord:
    return CellContextAlphaFrontierRecord(
        record_id,
        operation,
        role,
        CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY,
        (source_id,),
        payload,
        state,
        issues,
        description,
    )


def _sources() -> tuple[CellContextAlphaFrontierSourceReceipt, ...]:
    context = CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY
    return (
        CellContextAlphaFrontierSourceReceipt(
            "alpha-spatial",
            "Human Cell Atlas spatial index",
            "https://data.humancellatlas.org/",
            "spatial_context",
            "2026-01",
            "public aggregate niche descriptors",
            context,
        ),
        CellContextAlphaFrontierSourceReceipt(
            "alpha-territory",
            "GTEx public tissue portal",
            "https://gtexportal.org/home/",
            "territory_summary",
            "2025-10",
            "public aggregate core and margin summaries",
            context,
        ),
        CellContextAlphaFrontierSourceReceipt(
            "alpha-recurrence",
            "Cancer Genome Atlas public portal",
            "https://portal.gdc.cancer.gov/",
            "cohort_phase_summary",
            "2025-12",
            "public aggregate recurrence phase descriptors",
            context,
        ),
        CellContextAlphaFrontierSourceReceipt(
            "alpha-treatment",
            "Open Targets public platform",
            "https://platform.opentargets.org/",
            "treatment_context_index",
            "2025-11",
            "public aggregate pre and post support descriptors",
            context,
        ),
    )


def default_cell_context_alpha_frontier_fixture() -> CellContextAlphaFrontierFixture:
    context = CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY
    foreign = CELL_CONTEXT_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY
    source_spatial, source_territory, source_recurrence, source_treatment = (
        "alpha-spatial",
        "alpha-territory",
        "alpha-recurrence",
        "alpha-treatment",
    )
    rows: list[CellContextAlphaFrontierRecord] = []
    rows.extend(
        (
            _record(
                "d08-c09-positive",
                CellContextAlphaFrontierOperation.SPATIAL_NICHE,
                CellContextAlphaFrontierRole.POSITIVE,
                _payload(
                    context,
                    [
                        _row(
                            "niche-1",
                            context,
                            {
                                "niche_id": "perivascular",
                                "support": 0.84,
                                "sample_id": "aggregate-a",
                            },
                        ),
                        _row(
                            "niche-2",
                            context,
                            {
                                "niche_id": "perivascular",
                                "support": 0.78,
                                "sample_id": "aggregate-b",
                            },
                        ),
                    ],
                ),
                CellContextAlphaFrontierExpectedState.SUPPORTED,
                (),
                "spatial niche support replicated across aggregate rows",
                source_spatial,
            ),
            _record(
                "d08-c09-partial",
                CellContextAlphaFrontierOperation.SPATIAL_NICHE,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row(
                            "niche-partial", context, {"niche_id": "hypoxic", "support": "invalid"}
                        ),
                        _row("niche-valid", context, {"niche_id": "hypoxic", "support": 0.4}),
                    ],
                ),
                CellContextAlphaFrontierExpectedState.PARTIAL,
                ("invalid_spatial_niche_row",),
                "spatial parser quarantine retains aggregate controls",
                source_spatial,
            ),
            _record(
                "d08-c09-ambiguous",
                CellContextAlphaFrontierOperation.SPATIAL_NICHE,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row("niche-a", context, {"niche_id": "perivascular", "support": 0.8}),
                        _row("niche-b", context, {"niche_id": "hypoxic", "support": 0.77}),
                    ],
                ),
                CellContextAlphaFrontierExpectedState.AMBIGUOUS,
                (),
                "spatial close-candidate margin control",
                source_spatial,
            ),
            _record(
                "d08-c09-domain",
                CellContextAlphaFrontierOperation.SPATIAL_NICHE,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [_row("niche-foreign", foreign, {"niche_id": "perivascular", "support": 0.9})],
                ),
                CellContextAlphaFrontierExpectedState.OUT_OF_DOMAIN,
                ("context_mismatch",),
                "spatial foreign-context refusal",
                source_spatial,
            ),
            _record(
                "d08-c10-positive",
                CellContextAlphaFrontierOperation.CORE_MARGIN,
                CellContextAlphaFrontierRole.POSITIVE,
                _payload(
                    context,
                    [
                        _row(
                            "territory-positive",
                            context,
                            {"core_score": 0.86, "margin_score": 0.22},
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.SUPPORTED,
                (),
                "core territory support exceeds margin support",
                source_territory,
            ),
            _record(
                "d08-c10-partial",
                CellContextAlphaFrontierOperation.CORE_MARGIN,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row(
                            "territory-partial", context, {"core_score": None, "margin_score": None}
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.PARTIAL,
                ("invalid_core_margin_row",),
                "missing one-sided territory evidence is partial",
                source_territory,
            ),
            _record(
                "d08-c10-ambiguous",
                CellContextAlphaFrontierOperation.CORE_MARGIN,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row(
                            "territory-ambiguous",
                            context,
                            {"core_score": 0.54, "margin_score": 0.5},
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.AMBIGUOUS,
                (),
                "core and margin near-tie control",
                source_territory,
            ),
            _record(
                "d08-c10-domain",
                CellContextAlphaFrontierOperation.CORE_MARGIN,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [_row("territory-foreign", foreign, {"core_score": 0.8, "margin_score": 0.2})],
                ),
                CellContextAlphaFrontierExpectedState.OUT_OF_DOMAIN,
                ("context_mismatch",),
                "territory foreign-context refusal",
                source_territory,
            ),
            _record(
                "d08-c11-positive",
                CellContextAlphaFrontierOperation.RECURRENCE_STATE,
                CellContextAlphaFrontierRole.POSITIVE,
                _payload(
                    context,
                    [
                        _row("phase-primary-a", context, {"phase": "primary", "support": 0.86}),
                        _row("phase-primary-b", context, {"phase": "primary", "support": 0.82}),
                        _row(
                            "phase-recurrence-a", context, {"phase": "recurrence", "support": 0.38}
                        ),
                        _row(
                            "phase-recurrence-b", context, {"phase": "recurrence", "support": 0.4}
                        ),
                    ],
                ),
                CellContextAlphaFrontierExpectedState.SUPPORTED,
                (),
                "primary phase ranks above recurrence",
                source_recurrence,
            ),
            _record(
                "d08-c11-partial",
                CellContextAlphaFrontierOperation.RECURRENCE_STATE,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [_row("phase-partial", context, {"phase": "primary", "support": "invalid"})],
                ),
                CellContextAlphaFrontierExpectedState.PARTIAL,
                ("invalid_recurrence_row",),
                "recurrence parser quarantine control",
                source_recurrence,
            ),
            _record(
                "d08-c11-ambiguous",
                CellContextAlphaFrontierOperation.RECURRENCE_STATE,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row("phase-a", context, {"phase": "primary", "support": 0.62}),
                        _row("phase-b", context, {"phase": "recurrence", "support": 0.59}),
                    ],
                ),
                CellContextAlphaFrontierExpectedState.AMBIGUOUS,
                (),
                "recurrence close-phase control",
                source_recurrence,
            ),
            _record(
                "d08-c11-domain",
                CellContextAlphaFrontierOperation.RECURRENCE_STATE,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [_row("phase-foreign", foreign, {"phase": "recurrence", "support": 0.9})],
                ),
                CellContextAlphaFrontierExpectedState.OUT_OF_DOMAIN,
                ("context_mismatch",),
                "recurrence foreign-context refusal",
                source_recurrence,
            ),
            _record(
                "d08-c12-positive",
                CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
                CellContextAlphaFrontierRole.POSITIVE,
                _payload(
                    context,
                    [
                        _row(
                            "treatment-positive",
                            context,
                            {
                                "treatment_id": "aggregate-exposure",
                                "state_id": "mesenchymal",
                                "baseline_support": 0.22,
                                "post_treatment_support": 0.76,
                                "treatment_phase": "post_treatment",
                            },
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.SUPPORTED,
                (),
                "post-treatment support increase is descriptive",
                source_treatment,
            ),
            _record(
                "d08-c12-partial",
                CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row(
                            "treatment-partial",
                            context,
                            {
                                "treatment_id": "aggregate-exposure",
                                "state_id": "cycling",
                                "post_treatment_support": 0.6,
                                "treatment_phase": "post_treatment",
                            },
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.PARTIAL,
                ("invalid_treatment_induced_row",),
                "missing baseline is retained as partial",
                source_treatment,
            ),
            _record(
                "d08-c12-stable",
                CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row(
                            "treatment-stable",
                            context,
                            {
                                "treatment_id": "aggregate-exposure",
                                "state_id": "stem_like",
                                "baseline_support": 0.55,
                                "post_treatment_support": 0.58,
                                "treatment_phase": "post_treatment",
                            },
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.SUPPORTED,
                (),
                "stable support delta control",
                source_treatment,
            ),
            _record(
                "d08-c12-domain",
                CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
                CellContextAlphaFrontierRole.CONTROL,
                _payload(
                    context,
                    [
                        _row(
                            "treatment-foreign",
                            foreign,
                            {
                                "treatment_id": "aggregate-exposure",
                                "state_id": "cycling",
                                "baseline_support": 0.2,
                                "post_treatment_support": 0.8,
                                "treatment_phase": "post_treatment",
                            },
                        )
                    ],
                ),
                CellContextAlphaFrontierExpectedState.OUT_OF_DOMAIN,
                ("context_mismatch",),
                "treatment foreign-context refusal",
                source_treatment,
            ),
        )
    )
    return CellContextAlphaFrontierFixture(
        "cell-context-alpha-frontier",
        CELL_CONTEXT_ALPHA_FRONTIER_FIXTURE_VERSION,
        context,
        CELL_CONTEXT_ALPHA_FRONTIER_BOUNDARY,
        _sources(),
        tuple(rows),
    )


def audit_cell_context_alpha_frontier_data(
    fixture: CellContextAlphaFrontierFixture,
) -> CellContextAlphaFrontierDataAudit:
    checks = (
        CellContextAlphaFrontierDataCheck(
            "fixture-version",
            fixture.fixture_version == CELL_CONTEXT_ALPHA_FRONTIER_FIXTURE_VERSION,
            "fixture version is supported",
            fixture.fixture_version,
            CELL_CONTEXT_ALPHA_FRONTIER_FIXTURE_VERSION,
        ),
        CellContextAlphaFrontierDataCheck(
            "aggregate-boundary",
            fixture.evidence_boundary == CELL_CONTEXT_ALPHA_FRONTIER_BOUNDARY,
            "aggregate boundary is declared",
            fixture.evidence_boundary,
            CELL_CONTEXT_ALPHA_FRONTIER_BOUNDARY,
        ),
        CellContextAlphaFrontierDataCheck(
            "source-count",
            len(fixture.sources) == 4,
            "four source receipts are present",
            len(fixture.sources),
            4,
        ),
        CellContextAlphaFrontierDataCheck(
            "record-count",
            len(fixture.records) == 16,
            "sixteen records are present",
            len(fixture.records),
            16,
        ),
        CellContextAlphaFrontierDataCheck(
            "operation-balance",
            all(
                len(fixture.operation_records(item)) == 4
                for item in CellContextAlphaFrontierOperation
            ),
            "each operation has four paths",
            True,
            True,
        ),
        CellContextAlphaFrontierDataCheck(
            "source-closure",
            all(set(item.source_ids).issubset(fixture.source_map()) for item in fixture.records),
            "records reference declared receipts",
            True,
            True,
        ),
        CellContextAlphaFrontierDataCheck(
            "target-contexts",
            all(
                item.payload.get("target_context_key")
                in {
                    CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY,
                    CELL_CONTEXT_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY,
                }
                for item in fixture.records
            ),
            "target contexts are closed",
            True,
            True,
        ),
    )
    return CellContextAlphaFrontierDataAudit(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CELL_CONTEXT_ALPHA_FRONTIER_BOUNDARY",
    "CELL_CONTEXT_ALPHA_FRONTIER_CONTEXT_KEY",
    "CELL_CONTEXT_ALPHA_FRONTIER_FIXTURE_VERSION",
    "CELL_CONTEXT_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY",
    "CellContextAlphaFrontierDataAudit",
    "CellContextAlphaFrontierDataCheck",
    "CellContextAlphaFrontierExpectedState",
    "CellContextAlphaFrontierFixture",
    "CellContextAlphaFrontierOperation",
    "CellContextAlphaFrontierRecord",
    "CellContextAlphaFrontierRole",
    "CellContextAlphaFrontierSourceReceipt",
    "audit_cell_context_alpha_frontier_data",
    "default_cell_context_alpha_frontier_fixture",
]
