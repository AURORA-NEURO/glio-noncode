"""Public aggregate fixture for the Domain 13 planning frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

VALIDATION_FRONTIER_FIXTURE_VERSION = "2026.08.d13-c01-c04.v1"
VALIDATION_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
VALIDATION_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
VALIDATION_FRONTIER_SOURCE_COUNT = 5
VALIDATION_FRONTIER_POSITIVE_COUNT = 4
VALIDATION_FRONTIER_CONTROL_COUNT = 12


class ValidationFrontierOperation(StrEnum):
    EVIDENCE_GAP = "evidence_gap"
    ASSAY_ELIGIBILITY = "assay_eligibility"
    MPRA_PLANNING = "mpra_planning"
    STARR_SEQ_PLANNING = "starr_seq_planning"


class ValidationFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ValidationFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("validation frontier source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierRecord:
    record_id: str
    operation: ValidationFrontierOperation
    role: ValidationFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("validation frontier record requires source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ValidationFrontierSourceReceipt, ...]
    records: tuple[ValidationFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_id", "fixture_version", "context_key", "evidence_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.sources or not self.records:
            raise ValueError("validation frontier fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[ValidationFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ValidationFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[ValidationFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ValidationFrontierRole.CONTROL)

    def record_map(self) -> dict[str, ValidationFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def source_map(self) -> dict[str, ValidationFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierCatalog:
    fixture_id: str
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    operations: tuple[ValidationFrontierOperation, ...]
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierDataAudit:
    fixture_id: str
    checks: tuple[ValidationFrontierDataCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count, "failed_check_ids": list(self.failed_check_ids)}


def _source(source_id: str, title: str, uri: str, access_note: str) -> ValidationFrontierSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "access_note": access_note}
    return ValidationFrontierSourceReceipt(**body, content_address=content_hash(body))


def _record(record_id: str, operation: ValidationFrontierOperation, role: ValidationFrontierRole, payload: dict[str, Any], expected_state: str, expected_issue_codes: tuple[str, ...], notes: str, source_ids: tuple[str, ...] | None = None) -> ValidationFrontierRecord:
    receipts = source_ids if source_ids is not None else (("geo", "pubmed") if role is ValidationFrontierRole.POSITIVE else ("geo",))
    body = {"record_id": record_id, "operation": operation, "role": role, "context_key": VALIDATION_FRONTIER_CONTEXT_KEY, "source_ids": receipts, "payload": payload, "expected_state": expected_state, "expected_issue_codes": expected_issue_codes, "notes": notes}
    return ValidationFrontierRecord(**body, content_address=content_hash(body))


def _context(context_key: str = VALIDATION_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    parts = context_key.split("|")
    return {"genome_build": parts[0], "disease_class": parts[1], "age_group": parts[2], "cell_state": parts[3], "territory": parts[4], "treatment_phase": parts[5]}


def _hypothesis(hypothesis_id: str, context_key: str = VALIDATION_FRONTIER_CONTEXT_KEY, *, supported: bool = False, missing: tuple[str, ...] = ("measurement_likelihood",), uncertainty: float = 0.8, contradictory: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"hypothesis_id": hypothesis_id, "variant_id": f"{hypothesis_id}-variant", "element_id": f"{hypothesis_id}-element", "gene_id": "GENE1", "state": "supported" if supported else "partial", "state_id": "stem_like", "mechanism": "regulatory_link", "context_key": context_key, "support_proxy": 0.7 if supported else 0.4, "uncertainty": uncertainty, "factor_graph_id": f"{hypothesis_id}-graph", "factor_ids": ["sequence", "chromatin"], "prior_profile_id": "prior-public", "measurement_edge_id": "edge-public", "missing_evidence": list(missing), "contradictory_edges": list(contradictory), "limitations": ["aggregate planning fixture"]}


def _constraints(constraint_id: str, assay: str, context_key: str = VALIDATION_FRONTIER_CONTEXT_KEY, *, model: str = "neural_model", max_constructs: int = 4, min_length: int = 4, max_length: int = 12) -> dict[str, Any]:
    return {"constraint_id": constraint_id, "assay": assay, "context_key": context_key, "model_system": model, "min_insert_length": min_length, "max_insert_length": max_length, "max_constructs": max_constructs, "required_controls": ["negative_control", "positive_control"], "required_readouts": ["barcode", "rna"], "require_both_alleles": True}


def _inventory(assay: str = "mpra", *, model: str = "neural_model", complete: bool = True) -> list[dict[str, Any]]:
    return [{"assay": assay, "model_systems": [model], "min_insert_length": 4, "max_insert_length": 12, "controls": ["negative_control", "positive_control"] if complete else ["negative_control"], "readouts": ["barcode", "rna"] if complete else ["barcode"], "source_id": "assay-inventory", "feasibility": 0.8 if complete else 0.4}]


def _target(target_id: str, context_key: str = VALIDATION_FRONTIER_CONTEXT_KEY, *, sequence: str = "ACGTACGT", reference: str = "G", alternate: str = "T", offset: int = 2) -> dict[str, Any]:
    return {"target_id": target_id, "variant_id": f"{target_id}-variant", "element_id": f"{target_id}-element", "sequence": sequence, "variant_offset": offset, "reference_allele": reference, "alternate_allele": alternate, "context": _context(context_key), "source_id": "sequence-source"}


def default_validation_frontier_fixture() -> ValidationFrontierFixture:
    sources = (
        _source("geo", "NCBI Gene Expression Omnibus", "https://www.ncbi.nlm.nih.gov/geo/", "public aggregate assay planning receipt"),
        _source("pubmed", "PubMed", "https://pubmed.ncbi.nlm.nih.gov/", "public literature index receipt"),
        _source("encode", "ENCODE Project", "https://www.encodeproject.org/", "public assay and context receipt"),
        _source("common-fund", "NIH Common Fund", "https://commonfund.nih.gov/", "public research program receipt"),
        _source("sequence", "NCBI Reference Sequence", "https://www.ncbi.nlm.nih.gov/refseq/", "public sequence identity receipt"),
    )
    records = (
        _record("C01-POS-001", ValidationFrontierOperation.EVIDENCE_GAP, ValidationFrontierRole.POSITIVE, {"hypothesis": _hypothesis("h-gap"), "available_channels": ["sequence", "chromatin"]}, "partial", (), "missing measurement and high uncertainty remain visible"),
        _record("C01-CTRL-001", ValidationFrontierOperation.EVIDENCE_GAP, ValidationFrontierRole.CONTROL, {"hypothesis": _hypothesis("h-context", "GRCh38|glioma|pediatric|stem_like|core|unknown"), "available_channels": ["sequence"]}, "invalid", ("context_mismatch",), "mismatched context must not enter planning"),
        _record("C01-CTRL-002", ValidationFrontierOperation.EVIDENCE_GAP, ValidationFrontierRole.CONTROL, {"available_channels": ["sequence"]}, "invalid", ("invalid_evidence_gap_input",), "missing typed hypothesis is invalid"),
        _record("C01-CTRL-003", ValidationFrontierOperation.EVIDENCE_GAP, ValidationFrontierRole.CONTROL, {"hypothesis": _hypothesis("h-complete", supported=True, missing=(), uncertainty=0.1), "available_channels": ["sequence"]}, "ready_for_review", ("complete_hypothesis_control",), "complete snapshot is retained as a control"),
        _record("C02-POS-001", ValidationFrontierOperation.ASSAY_ELIGIBILITY, ValidationFrontierRole.POSITIVE, {"constraints": _constraints("route-positive", "mpra"), "inventory": _inventory("mpra")}, "ready_for_review", (), "matching model, bounds, controls, and readouts"),
        _record("C02-CTRL-001", ValidationFrontierOperation.ASSAY_ELIGIBILITY, ValidationFrontierRole.CONTROL, {"constraints": _constraints("route-context", "mpra"), "inventory": _inventory("mpra", model="other_model")}, "blocked", ("model_system_not_available",), "model mismatch remains blocked"),
        _record("C02-CTRL-002", ValidationFrontierOperation.ASSAY_ELIGIBILITY, ValidationFrontierRole.CONTROL, {"constraints": _constraints("route-controls", "mpra"), "inventory": _inventory("mpra", complete=False)}, "blocked", ("missing_controls", "missing_readouts"), "missing controls and readouts remain explicit"),
        _record("C02-CTRL-003", ValidationFrontierOperation.ASSAY_ELIGIBILITY, ValidationFrontierRole.CONTROL, {"constraints": _constraints("route-empty", "starr_seq"), "inventory": []}, "abstained", ("assay_not_present_in_inventory",), "empty inventory abstains"),
        _record("C03-POS-001", ValidationFrontierOperation.MPRA_PLANNING, ValidationFrontierRole.POSITIVE, {"constraints": _constraints("mpra-positive", "mpra"), "targets": [_target("mpra-target")]}, "ready_for_review", (), "reference and alternate constructs are paired"),
        _record("C03-CTRL-001", ValidationFrontierOperation.MPRA_PLANNING, ValidationFrontierRole.CONTROL, {"constraints": _constraints("mpra-context", "mpra"), "targets": [_target("mpra-context-target", "GRCh38|glioma|pediatric|stem_like|core|unknown")]}, "blocked", ("context_mismatch",), "context mismatch blocks design"),
        _record("C03-CTRL-002", ValidationFrontierOperation.MPRA_PLANNING, ValidationFrontierRole.CONTROL, {"constraints": _constraints("mpra-budget", "mpra", max_constructs=1), "targets": [_target("mpra-budget-target")]}, "blocked", ("max_constructs_exceeded",), "construct budget blocks overflow"),
        _record("C03-CTRL-003", ValidationFrontierOperation.MPRA_PLANNING, ValidationFrontierRole.CONTROL, {"constraints": _constraints("mpra-empty", "mpra"), "targets": []}, "blocked", ("no_validation_targets",), "empty target list blocks planning"),
        _record("C04-POS-001", ValidationFrontierOperation.STARR_SEQ_PLANNING, ValidationFrontierRole.POSITIVE, {"constraints": _constraints("starr-positive", "starr_seq"), "targets": [_target("starr-target")]}, "ready_for_review", (), "STARR-seq package retains paired alleles"),
        _record("C04-CTRL-001", ValidationFrontierOperation.STARR_SEQ_PLANNING, ValidationFrontierRole.CONTROL, {"constraints": _constraints("starr-context", "starr_seq"), "targets": [_target("starr-context-target", "GRCh38|glioma|pediatric|stem_like|core|unknown")]}, "blocked", ("context_mismatch",), "context mismatch blocks design"),
        _record("C04-CTRL-002", ValidationFrontierOperation.STARR_SEQ_PLANNING, ValidationFrontierRole.CONTROL, {"constraints": _constraints("starr-length", "starr_seq", max_length=6), "targets": [_target("starr-length-target")]}, "blocked", ("insert_length",), "insert bounds block target"),
        _record("C04-CTRL-003", ValidationFrontierOperation.STARR_SEQ_PLANNING, ValidationFrontierRole.CONTROL, {"constraints": _constraints("starr-empty", "starr_seq"), "targets": []}, "blocked", ("no_validation_targets",), "empty target list blocks planning"),
    )
    body = {"fixture_id": "validation-frontier-public-aggregate", "fixture_version": VALIDATION_FRONTIER_FIXTURE_VERSION, "context_key": VALIDATION_FRONTIER_CONTEXT_KEY, "evidence_boundary": VALIDATION_FRONTIER_EVIDENCE_BOUNDARY, "sources": sources, "records": records}
    return ValidationFrontierFixture(**body, content_address=content_hash(body))


def build_validation_frontier_catalog(fixture: ValidationFrontierFixture) -> ValidationFrontierCatalog:
    body = {"fixture_id": fixture.fixture_id, "record_ids": tuple(item.record_id for item in fixture.records), "source_ids": tuple(item.source_id for item in fixture.sources), "operations": tuple(ValidationFrontierOperation), "context_key": fixture.context_key}
    return ValidationFrontierCatalog(**body, content_address=content_hash(body))


def audit_validation_frontier_data(fixture: ValidationFrontierFixture) -> ValidationFrontierDataAudit:
    catalog = build_validation_frontier_catalog(fixture)
    values = (("fixture-id", fixture.fixture_id == "validation-frontier-public-aggregate", fixture.fixture_id, "validation fixture identity"), ("fixture-version", fixture.fixture_version == VALIDATION_FRONTIER_FIXTURE_VERSION, fixture.fixture_version, "version is explicit"), ("boundary", fixture.evidence_boundary == VALIDATION_FRONTIER_EVIDENCE_BOUNDARY, fixture.evidence_boundary, "aggregate boundary is exact"), ("source-count", len(fixture.sources) == 5, len(fixture.sources), 5), ("record-count", len(fixture.records) == 16, len(fixture.records), 16), ("positive-count", len(fixture.positive_records) == 4, len(fixture.positive_records), 4), ("control-count", len(fixture.control_records) == 12, len(fixture.control_records), 12), ("unique-records", len(set(catalog.record_ids)) == len(fixture.records), len(set(catalog.record_ids)), len(fixture.records)), ("operations", set(item.operation for item in fixture.records) == set(ValidationFrontierOperation), tuple(item.value for item in ValidationFrontierOperation), tuple(item.value for item in set(record.operation for record in fixture.records))), ("contexts", all(item.context_key == fixture.context_key for item in fixture.records), True, "record context is exact"), ("sources-https", all(item.uri.startswith("https://") for item in fixture.sources), True, "source receipts use HTTPS"), ("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, "records are addressed"))
    checks = tuple(ValidationFrontierDataCheck(item[0], item[1], item[2], item[3], str(item[0]), content_hash(item)) for item in values)
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": not failed, "failed_check_ids": failed}
    return ValidationFrontierDataAudit(**body, content_address=content_hash(body))


def load_validation_frontier_fixture(path: str | Path) -> ValidationFrontierFixture:
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not raw.get("sources") or not raw.get("records"):
        raise ValueError("validation frontier fixture requires sources and records")
    sources = tuple(ValidationFrontierSourceReceipt(**item) for item in raw.get("sources", ()))
    records = tuple(ValidationFrontierRecord(operation=ValidationFrontierOperation(item["operation"]), role=ValidationFrontierRole(item["role"]), **{key: item[key] for key in ("record_id", "context_key", "source_ids", "payload", "expected_state", "expected_issue_codes", "notes", "content_address")}) for item in raw.get("records", ()))
    return ValidationFrontierFixture(fixture_id=str(raw["fixture_id"]), fixture_version=str(raw["fixture_version"]), context_key=str(raw["context_key"]), evidence_boundary=str(raw["evidence_boundary"]), sources=sources, records=records, content_address=str(raw.get("content_address", content_hash({"fixture_id": raw["fixture_id"], "fixture_version": raw["fixture_version"], "context_key": raw["context_key"], "evidence_boundary": raw["evidence_boundary"], "sources": sources, "records": records}))))


__all__ = ["VALIDATION_FRONTIER_CONTEXT_KEY", "VALIDATION_FRONTIER_CONTROL_COUNT", "VALIDATION_FRONTIER_EVIDENCE_BOUNDARY", "VALIDATION_FRONTIER_FIXTURE_VERSION", "VALIDATION_FRONTIER_POSITIVE_COUNT", "VALIDATION_FRONTIER_SOURCE_COUNT", "ValidationFrontierCatalog", "ValidationFrontierDataAudit", "ValidationFrontierDataCheck", "ValidationFrontierFixture", "ValidationFrontierOperation", "ValidationFrontierRecord", "ValidationFrontierRole", "ValidationFrontierSourceReceipt", "audit_validation_frontier_data", "build_validation_frontier_catalog", "default_validation_frontier_fixture", "load_validation_frontier_fixture"]
