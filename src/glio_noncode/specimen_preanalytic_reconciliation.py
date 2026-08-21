"""Cross-view receipt reconciliation for the C13-C16 evidence plane."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from .specimen_preanalytic_public_data import (
    SpecimenPreanalyticFixtureCatalog,
    SpecimenPreanalyticOperation,
)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReceiptIndexEntry:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    context_key: str
    source_ids: tuple[str, ...]
    record_address: str
    result_address: str
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "record_id",
            "operation",
            "role",
            "expected_state",
            "observed_state",
            "context_key",
            "record_address",
            "result_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field)), f"receipt index {field}")
        if not self.source_ids:
            raise ValueError("receipt index entry requires source IDs")
        if not all(
            value.startswith("sha256:")
            for value in (self.record_address, self.result_address, self.content_address)
        ):
            raise ValueError("receipt index addresses must be sha256-prefixed")

    def address_body(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operation": self.operation,
            "role": self.role,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "record_address": self.record_address,
            "result_address": self.result_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReceiptIndex:
    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[SpecimenPreanalyticReceiptIndexEntry, ...]
    content_address: str

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(entry.record_id for entry in self.entries)

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({entry.operation for entry in self.entries}))

    def address_body(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "entries": self.entries,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "entry_count": len(self.entries),
            "operation_ids": self.operation_ids,
        }


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReconciliationCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReconciliationReport:
    fixture_id: str
    state: str
    checks: tuple[SpecimenPreanalyticReconciliationCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed, "failed_check_ids": self.failed_check_ids}


def build_specimen_preanalytic_receipt_index(
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticReceiptIndex:
    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    receipts = {receipt.record_id: receipt for receipt in evaluation.receipts}
    entries: list[SpecimenPreanalyticReceiptIndexEntry] = []
    for record in catalog.records:
        receipt = receipts[record.record_id]
        body = {
            "record_id": record.record_id,
            "operation": record.operation.value,
            "role": record.role.value,
            "expected_state": record.expected_state.value,
            "observed_state": receipt.observed_state,
            "context_key": record.context_key,
            "source_ids": record.source_ids,
            "record_address": record.content_address,
            "result_address": receipt.output_address,
        }
        entries.append(
            SpecimenPreanalyticReceiptIndexEntry(**body, content_address=content_hash(body))
        )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "source_ids": catalog.source_ids,
        "entries": entries,
    }
    return SpecimenPreanalyticReceiptIndex(
        catalog.fixture_id,
        catalog.context_key,
        catalog.source_ids,
        tuple(entries),
        content_hash(body),
    )


def audit_specimen_preanalytic_receipt_index(
    catalog: SpecimenPreanalyticFixtureCatalog,
    index: SpecimenPreanalyticReceiptIndex,
) -> SpecimenPreanalyticReconciliationReport:
    """Compare an index with a fresh fixture evaluation and catalog."""

    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    records = {record.record_id: record for record in catalog.records}
    receipts = {receipt.record_id: receipt for receipt in evaluation.receipts}
    checks: list[SpecimenPreanalyticReconciliationCheck] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
        checks.append(
            SpecimenPreanalyticReconciliationCheck(
                check_id, bool(passed), observed, expected, message
            )
        )

    add(
        "fixture-id",
        index.fixture_id == catalog.fixture_id,
        index.fixture_id,
        catalog.fixture_id,
        "fixture identity agrees",
    )
    add(
        "context",
        index.context_key == catalog.context_key,
        index.context_key,
        catalog.context_key,
        "context agrees",
    )
    add(
        "source-set",
        set(index.source_ids) == set(catalog.source_ids),
        index.source_ids,
        catalog.source_ids,
        "source set agrees",
    )
    add(
        "entry-floor",
        len(index.entries) == len(catalog.records),
        len(index.entries),
        len(catalog.records),
        "entry count agrees",
    )
    add(
        "record-identity",
        set(index.record_ids) == set(records),
        index.record_ids,
        tuple(records),
        "record IDs agree",
    )
    add(
        "record-uniqueness",
        len(set(index.record_ids)) == len(index.entries),
        len(set(index.record_ids)),
        len(index.entries),
        "record IDs are unique",
    )
    add(
        "operation-coverage",
        set(index.operation_ids) == {item.value for item in SpecimenPreanalyticOperation},
        index.operation_ids,
        tuple(item.value for item in SpecimenPreanalyticOperation),
        "operation coverage agrees",
    )
    add(
        "context-consistency",
        all(entry.context_key == catalog.context_key for entry in index.entries),
        True,
        True,
        "entry contexts agree",
    )
    add(
        "source-consistency",
        all(set(entry.source_ids).issubset(set(catalog.source_ids)) for entry in index.entries),
        True,
        True,
        "entry sources are declared",
    )
    add(
        "record-addresses",
        all(
            entry.record_id not in records
            or entry.record_address == records[entry.record_id].content_address
            for entry in index.entries
        ),
        True,
        True,
        "record addresses agree",
    )
    add(
        "result-addresses",
        all(
            entry.record_id not in receipts
            or entry.result_address == receipts[entry.record_id].output_address
            for entry in index.entries
        ),
        True,
        True,
        "result addresses agree",
    )
    add(
        "state-alignment",
        all(
            entry.record_id not in receipts
            or entry.observed_state == receipts[entry.record_id].observed_state
            for entry in index.entries
        ),
        True,
        True,
        "result states agree",
    )
    add(
        "entry-addresses",
        all(entry.content_address == content_hash(entry.address_body()) for entry in index.entries),
        True,
        True,
        "entry addresses agree",
    )
    add(
        "index-address",
        index.content_address == content_hash(index.address_body()),
        index.content_address,
        "sha256:<recomputed>",
        "index address agrees",
    )
    add(
        "result-uniqueness",
        len({entry.result_address for entry in index.entries}) == len(index.entries),
        len({entry.result_address for entry in index.entries}),
        len(index.entries),
        "result addresses are unique",
    )
    add(
        "sanitized-index",
        not _forbidden_keys(index.to_dict()),
        True,
        True,
        "index projection is sanitized",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {"fixture_id": catalog.fixture_id, "state": state, "checks": checks}
    return SpecimenPreanalyticReconciliationReport(
        catalog.fixture_id, state, tuple(checks), content_hash(body)
    )


def _forbidden_keys(value: Any) -> tuple[str, ...]:
    forbidden = {
        "records",
        "raw_records",
        "payload",
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
    }
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in forbidden:
                found.add(normalized)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return tuple(sorted(found))


__all__ = [
    "SpecimenPreanalyticReceiptIndex",
    "SpecimenPreanalyticReceiptIndexEntry",
    "SpecimenPreanalyticReconciliationCheck",
    "SpecimenPreanalyticReconciliationReport",
    "audit_specimen_preanalytic_receipt_index",
    "build_specimen_preanalytic_receipt_index",
]
