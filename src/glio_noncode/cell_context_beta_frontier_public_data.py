"""Closed public aggregate fixture for Domain 08 C05-C08.

The fixture binds four context-prior families to reproducible aggregate rows.
Each family has one positive row and three controls: parser quarantine,
candidate ambiguity, and an explicit domain or molecular-state refusal.  The
payloads contain cohort-shaped taxonomy observations only; they are not case
records and cannot be used as clinical conclusions.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CELL_CONTEXT_BETA_FRONTIER_FIXTURE_VERSION = "2026.08.d08-c05-c08.v1"
CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY = "GRCh38|glioblastoma|adult|stem_like|core|unknown"
CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY = "GRCh38|glioma|adult|proneural|core|unknown"
CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY = "GRCh38|glioma|pediatric|stem_like|midline|unknown"
CELL_CONTEXT_BETA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|mesenchymal_like|core|unknown"
CELL_CONTEXT_BETA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
CELL_CONTEXT_BETA_FRONTIER_POSITIVE_COUNT = 4
CELL_CONTEXT_BETA_FRONTIER_CONTROL_COUNT = 12
CELL_CONTEXT_BETA_FRONTIER_SOURCE_COUNT = 4
CELL_CONTEXT_BETA_FRONTIER_TARGET_CONTEXTS = (
    CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
    CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
    CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
    CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
)


class CellContextBetaFrontierOperation(StrEnum):
    DEVELOPMENTAL_LINEAGE = "developmental_lineage_prior"
    GBM_MALIGNANT_STATE = "glioblastoma_malignant_state_prior"
    IDH_MUTANT_LINEAGE = "idh_mutant_lineage_state_prior"
    H3K27_DEVELOPMENTAL_STATE = "h3k27_altered_developmental_state_prior"


class CellContextBetaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class CellContextBetaFrontierExpectedState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    context_key: str
    covered_contexts: tuple[str, ...]
    public_aggregate: bool = True
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "source_kind", "release", "scope", "context_key"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("beta source receipt must use HTTPS")
        if self.context_key != CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("beta source receipt must use the tranche anchor context")
        if not self.covered_contexts or not set(self.covered_contexts).issubset(
            set(CELL_CONTEXT_BETA_FRONTIER_TARGET_CONTEXTS)
        ):
            raise ValidationError("beta source receipt has unsupported covered contexts")
        if not self.public_aggregate:
            raise ValidationError("beta source receipt must be aggregate")
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
            "covered_contexts": list(self.covered_contexts),
            "public_aggregate": self.public_aggregate,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierRecord:
    record_id: str
    operation: CellContextBetaFrontierOperation
    role: CellContextBetaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CellContextBetaFrontierExpectedState
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if self.context_key != CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("beta record context must use the tranche anchor")
        if not self.source_ids or not self.payload:
            raise ValidationError("beta record requires sources and payload")
        if not isinstance(self.operation, CellContextBetaFrontierOperation):
            raise ValidationError("beta record operation is invalid")
        if not isinstance(self.role, CellContextBetaFrontierRole):
            raise ValidationError("beta record role is invalid")
        if not isinstance(self.expected_state, CellContextBetaFrontierExpectedState):
            raise ValidationError("beta record expected state is invalid")
        restricted = {
            "patient",
            "subject",
            "sample_id",
            "donor_id",
            "participant_id",
            "individual_id",
        }
        if any(str(key).lower() in restricted for key in self.payload):
            raise ValidationError("beta payload cannot contain subject-level keys")
        target = str(self.payload.get("target_context_key", ""))
        if target not in CELL_CONTEXT_BETA_FRONTIER_TARGET_CONTEXTS:
            raise ValidationError("beta payload target context is not declared")
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
class CellContextBetaFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[CellContextBetaFrontierSourceReceipt, ...]
    records: tuple[CellContextBetaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != CELL_CONTEXT_BETA_FRONTIER_FIXTURE_VERSION:
            raise ValidationError("unsupported beta fixture version")
        if self.context_key != CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("beta fixture context is not the tranche anchor")
        if self.evidence_boundary != CELL_CONTEXT_BETA_FRONTIER_BOUNDARY:
            raise ValidationError("beta fixture must be aggregate")
        if len(self.sources) != CELL_CONTEXT_BETA_FRONTIER_SOURCE_COUNT:
            raise ValidationError("beta fixture requires four source receipts")
        if len(self.records) != 16:
            raise ValidationError("beta fixture requires sixteen records")
        if len(self.positive_records) != CELL_CONTEXT_BETA_FRONTIER_POSITIVE_COUNT:
            raise ValidationError("beta fixture requires four positive records")
        if len(self.control_records) != CELL_CONTEXT_BETA_FRONTIER_CONTROL_COUNT:
            raise ValidationError("beta fixture requires twelve controls")
        source_ids = {item.source_id for item in self.sources}
        if any(set(item.source_ids) - source_ids for item in self.records):
            raise ValidationError("beta record references an undeclared source")
        if len({item.record_id for item in self.records}) != len(self.records):
            raise ValidationError("beta record IDs must be unique")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(self.to_dict(include_payload=True, include_address=False)),
            )

    @property
    def positive_records(self) -> tuple[CellContextBetaFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is CellContextBetaFrontierRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[CellContextBetaFrontierRecord, ...]:
        return tuple(
            item for item in self.records if item.role is CellContextBetaFrontierRole.CONTROL
        )

    def operation_records(
        self, operation: CellContextBetaFrontierOperation
    ) -> tuple[CellContextBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.operation is operation)

    def source_map(self) -> dict[str, CellContextBetaFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, CellContextBetaFrontierRecord]:
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
class CellContextBetaFrontierDataCheck:
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
class CellContextBetaFrontierDataAudit:
    fixture_id: str
    checks: tuple[CellContextBetaFrontierDataCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("beta data audit is incomplete")
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
    observation_id: str, candidate_id: str, label: str, support: Any, context_key: str
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "subject_id": "aggregate-cohort",
        "candidate_id": candidate_id,
        "candidate_label": label,
        "context_key": context_key,
        "support": support,
        "uncertainty": 0.1,
        "evidence_tier": "public-reference-atlas",
    }


def _payload(
    target: str,
    rows: list[dict[str, Any]],
    *,
    state: str = "",
    molecule: str = "",
    margin: float = 0.15,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "target_context_key": target,
        "source_version": "aggregate-beta-2026-01",
        "model_version": "beta-1",
        "ambiguity_margin": margin,
        "observation_text": _observation_json(rows),
    }
    if state:
        value["declared_molecular_state"] = state
    return value


def _record(
    record_id: str,
    operation: CellContextBetaFrontierOperation,
    role: CellContextBetaFrontierRole,
    payload: Mapping[str, Any],
    expected: CellContextBetaFrontierExpectedState,
    issues: tuple[str, ...],
    description: str,
    source_id: str,
) -> CellContextBetaFrontierRecord:
    return CellContextBetaFrontierRecord(
        record_id,
        operation,
        role,
        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
        (source_id,),
        payload,
        expected,
        issues,
        description,
    )


def _sources() -> tuple[CellContextBetaFrontierSourceReceipt, ...]:
    contexts = CELL_CONTEXT_BETA_FRONTIER_TARGET_CONTEXTS
    return (
        CellContextBetaFrontierSourceReceipt(
            "beta-cell-atlas",
            "Human Cell Atlas public index",
            "https://data.humancellatlas.org/",
            "cell_state_index",
            "2026-01",
            "public aggregate lineage and state descriptors",
            CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
            contexts,
        ),
        CellContextBetaFrontierSourceReceipt(
            "beta-ontologies",
            "MONDO and NCIt public terminology",
            "https://mondo.monarchinitiative.org/",
            "ontology_release",
            "2025-12",
            "public aggregate disease and state terminology",
            CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
            contexts,
        ),
        CellContextBetaFrontierSourceReceipt(
            "beta-development",
            "Developmental cell atlas public portal",
            "https://cellxgene.cziscience.com/",
            "developmental_atlas",
            "2025-11",
            "public aggregate adult and pediatric developmental context",
            CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
            contexts,
        ),
        CellContextBetaFrontierSourceReceipt(
            "beta-epigenome",
            "ENCODE public data portal",
            "https://www.encodeproject.org/",
            "epigenome_index",
            "2025-10",
            "public aggregate chromatin and state context descriptors",
            CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
            contexts,
        ),
    )


def default_cell_context_beta_frontier_fixture() -> CellContextBetaFrontierFixture:
    """Return the deterministic sixteen-record public aggregate fixture."""

    source = "beta-cell-atlas"
    records: list[CellContextBetaFrontierRecord] = []
    records.append(
        _record(
            "d08-c05-positive",
            CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
            CellContextBetaFrontierRole.POSITIVE,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                [
                    _row(
                        "dev-positive",
                        "radial_glia_like",
                        "radial glia-like",
                        0.95,
                        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                    ),
                    _row(
                        "dev-secondary",
                        "oligodendrocyte_lineage",
                        "oligodendrocyte lineage",
                        0.22,
                        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                    ),
                ],
            ),
            CellContextBetaFrontierExpectedState.SUPPORTED,
            (),
            "adult aggregate developmental lineage prior",
            source,
        )
    )
    records.append(
        _record(
            "d08-c05-partial",
            CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                [
                    _row(
                        "dev-partial",
                        "radial_glia_like",
                        "radial glia-like",
                        0.92,
                        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                    ),
                    {"candidate_id": "broken", "support": "not-a-number"},
                ],
            ),
            CellContextBetaFrontierExpectedState.PARTIAL,
            ("invalid_context_prior_row",),
            "parser quarantine retains a usable developmental row",
            source,
        )
    )
    records.append(
        _record(
            "d08-c05-ambiguous",
            CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                [
                    _row(
                        "dev-a",
                        "radial_glia_like",
                        "radial glia-like",
                        0.82,
                        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                    ),
                    _row(
                        "dev-b",
                        "oligodendrocyte_lineage",
                        "oligodendrocyte lineage",
                        0.81,
                        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                    ),
                ],
            ),
            CellContextBetaFrontierExpectedState.AMBIGUOUS,
            (),
            "developmental candidate margin control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c05-domain",
            CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                [
                    _row(
                        "dev-foreign",
                        "radial_glia_like",
                        "radial glia-like",
                        0.9,
                        CELL_CONTEXT_BETA_FRONTIER_FOREIGN_CONTEXT_KEY,
                    )
                ],
            ),
            CellContextBetaFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "foreign exact-context developmental control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c06-positive",
            CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
            CellContextBetaFrontierRole.POSITIVE,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                [
                    _row(
                        "gbm-positive",
                        "stem_like",
                        "stem-like",
                        0.94,
                        CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                    )
                ],
            ),
            CellContextBetaFrontierExpectedState.SUPPORTED,
            (),
            "explicit glioblastoma malignant-state gate",
            source,
        )
    )
    records.append(
        _record(
            "d08-c06-partial",
            CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                [
                    _row(
                        "gbm-partial",
                        "cycling",
                        "cycling",
                        0.88,
                        CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                    ),
                    {"candidate_id": "broken", "support": "invalid"},
                ],
            ),
            CellContextBetaFrontierExpectedState.PARTIAL,
            ("invalid_context_prior_row",),
            "GBM parser quarantine control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c06-ambiguous",
            CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                [
                    _row(
                        "gbm-a",
                        "cycling",
                        "cycling",
                        0.8,
                        CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                    ),
                    _row(
                        "gbm-b",
                        "hypoxic",
                        "hypoxic",
                        0.79,
                        CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY,
                    ),
                ],
            ),
            CellContextBetaFrontierExpectedState.AMBIGUOUS,
            (),
            "GBM competing-state margin control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c06-domain",
            CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                [
                    _row(
                        "gbm-gate",
                        "stem_like",
                        "stem-like",
                        0.9,
                        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
                    )
                ],
            ),
            CellContextBetaFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "generic glioma cannot enter GBM state gate",
            source,
        )
    )
    records.append(
        _record(
            "d08-c07-positive",
            CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
            CellContextBetaFrontierRole.POSITIVE,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                [
                    _row(
                        "idh-positive",
                        "proneural",
                        "proneural",
                        0.93,
                        CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                    )
                ],
                state="IDH-mutant",
            ),
            CellContextBetaFrontierExpectedState.SUPPORTED,
            (),
            "declared IDH-mutant lineage-state gate",
            source,
        )
    )
    records.append(
        _record(
            "d08-c07-partial",
            CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                [
                    _row(
                        "idh-partial",
                        "oligodendrocyte_precursor_like",
                        "oligodendrocyte precursor-like",
                        0.86,
                        CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                    ),
                    {"candidate_id": "broken", "support": "invalid"},
                ],
                state="IDH-mutant",
            ),
            CellContextBetaFrontierExpectedState.PARTIAL,
            ("invalid_context_prior_row",),
            "IDH parser quarantine control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c07-ambiguous",
            CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                [
                    _row(
                        "idh-a",
                        "proneural",
                        "proneural",
                        0.8,
                        CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                    ),
                    _row(
                        "idh-b",
                        "astrocyte_lineage",
                        "astrocyte lineage",
                        0.79,
                        CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                    ),
                ],
                state="IDH-mutant",
            ),
            CellContextBetaFrontierExpectedState.AMBIGUOUS,
            (),
            "IDH competing-lineage margin control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c07-domain",
            CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                [
                    _row(
                        "idh-gate",
                        "proneural",
                        "proneural",
                        0.9,
                        CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY,
                    )
                ],
                state="IDH-wildtype",
            ),
            CellContextBetaFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "IDH-wildtype gate refusal",
            source,
        )
    )
    records.append(
        _record(
            "d08-c08-positive",
            CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
            CellContextBetaFrontierRole.POSITIVE,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                [
                    _row(
                        "h3-positive",
                        "midline_glial_progenitor",
                        "midline glial progenitor",
                        0.94,
                        CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                    )
                ],
                state="H3K27-altered",
            ),
            CellContextBetaFrontierExpectedState.SUPPORTED,
            (),
            "declared H3K27-altered developmental-state gate",
            source,
        )
    )
    records.append(
        _record(
            "d08-c08-partial",
            CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                [
                    _row(
                        "h3-partial",
                        "radial_glia_like",
                        "radial glia-like",
                        0.86,
                        CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                    ),
                    {"candidate_id": "broken", "support": "invalid"},
                ],
                state="H3K27-altered",
            ),
            CellContextBetaFrontierExpectedState.PARTIAL,
            ("invalid_context_prior_row",),
            "H3K27 parser quarantine control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c08-ambiguous",
            CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                [
                    _row(
                        "h3-a",
                        "midline_glial_progenitor",
                        "midline glial progenitor",
                        0.8,
                        CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                    ),
                    _row(
                        "h3-b",
                        "developmental_stem_like",
                        "developmental stem-like",
                        0.79,
                        CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                    ),
                ],
                state="H3K27-altered",
            ),
            CellContextBetaFrontierExpectedState.AMBIGUOUS,
            (),
            "H3K27 competing developmental-state margin control",
            source,
        )
    )
    records.append(
        _record(
            "d08-c08-domain",
            CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
            CellContextBetaFrontierRole.CONTROL,
            _payload(
                CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                [
                    _row(
                        "h3-gate",
                        "midline_glial_progenitor",
                        "midline glial progenitor",
                        0.9,
                        CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY,
                    )
                ],
                state="IDH-mutant",
            ),
            CellContextBetaFrontierExpectedState.OUT_OF_DOMAIN,
            (),
            "wrong molecular gate for H3K27 prior",
            source,
        )
    )
    return CellContextBetaFrontierFixture(
        "cell-context-beta-frontier",
        CELL_CONTEXT_BETA_FRONTIER_FIXTURE_VERSION,
        CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
        CELL_CONTEXT_BETA_FRONTIER_BOUNDARY,
        _sources(),
        tuple(records),
    )


def audit_cell_context_beta_frontier_data(
    fixture: CellContextBetaFrontierFixture,
) -> CellContextBetaFrontierDataAudit:
    checks = (
        CellContextBetaFrontierDataCheck(
            "fixture-version",
            fixture.fixture_version == CELL_CONTEXT_BETA_FRONTIER_FIXTURE_VERSION,
            "fixture version is supported",
            fixture.fixture_version,
            CELL_CONTEXT_BETA_FRONTIER_FIXTURE_VERSION,
        ),
        CellContextBetaFrontierDataCheck(
            "aggregate-boundary",
            fixture.evidence_boundary == CELL_CONTEXT_BETA_FRONTIER_BOUNDARY,
            "aggregate boundary is declared",
            fixture.evidence_boundary,
            CELL_CONTEXT_BETA_FRONTIER_BOUNDARY,
        ),
        CellContextBetaFrontierDataCheck(
            "source-count",
            len(fixture.sources) == CELL_CONTEXT_BETA_FRONTIER_SOURCE_COUNT,
            "all public source receipts are present",
            len(fixture.sources),
            CELL_CONTEXT_BETA_FRONTIER_SOURCE_COUNT,
        ),
        CellContextBetaFrontierDataCheck(
            "record-count",
            len(fixture.records) == 16,
            "positive and control rows are complete",
            len(fixture.records),
            16,
        ),
        CellContextBetaFrontierDataCheck(
            "operation-balance",
            all(
                len(fixture.operation_records(item)) == 4
                for item in CellContextBetaFrontierOperation
            ),
            "each prior family has one positive and three controls",
            {
                item.value: len(fixture.operation_records(item))
                for item in CellContextBetaFrontierOperation
            },
            4,
        ),
        CellContextBetaFrontierDataCheck(
            "source-coverage",
            all(set(item.source_ids).issubset(fixture.source_map()) for item in fixture.records),
            "records reference declared receipts",
            True,
            True,
        ),
        CellContextBetaFrontierDataCheck(
            "payload-contexts",
            all(
                item.payload.get("target_context_key") in CELL_CONTEXT_BETA_FRONTIER_TARGET_CONTEXTS
                for item in fixture.records
            ),
            "target contexts come from the declared set",
            True,
            True,
        ),
    )
    return CellContextBetaFrontierDataAudit(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CELL_CONTEXT_BETA_FRONTIER_BOUNDARY",
    "CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY",
    "CELL_CONTEXT_BETA_FRONTIER_FIXTURE_VERSION",
    "CELL_CONTEXT_BETA_FRONTIER_GBM_CONTEXT_KEY",
    "CELL_CONTEXT_BETA_FRONTIER_H3_CONTEXT_KEY",
    "CELL_CONTEXT_BETA_FRONTIER_IDH_CONTEXT_KEY",
    "CellContextBetaFrontierDataAudit",
    "CellContextBetaFrontierDataCheck",
    "CellContextBetaFrontierExpectedState",
    "CellContextBetaFrontierFixture",
    "CellContextBetaFrontierOperation",
    "CellContextBetaFrontierRecord",
    "CellContextBetaFrontierRole",
    "CellContextBetaFrontierSourceReceipt",
    "audit_cell_context_beta_frontier_data",
    "default_cell_context_beta_frontier_fixture",
]
