"""Receipt-index reconciliation for the Domain 03 C09-C12 release surface.

The evaluator, graph builder, bundle builder, and runtime each expose a useful
view of one specimen-context run. This module provides the compact join between
the fixture record address and the sanitized result address. It deliberately
does not copy the fixture payload. The index makes omissions, duplicate receipt
identities, context drift, source drift, state drift, and address drift visible
as explicit reconciliation checks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_lineage_fixture_eval import evaluate_specimen_lineage_fixture
from .specimen_lineage_public_data import (
    SpecimenLineageFixtureCatalog,
    SpecimenLineageOperation,
)


@dataclass(frozen=True, slots=True)
class SpecimenLineageReceiptIndexEntry:
    """One joined fixture-record and sanitized-result receipt."""

    record_id: str
    operation: str
    fixture_state: str
    result_state: str
    context_key: str
    source_ids: tuple[str, ...]
    record_address: str
    result_address: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "operation",
            "fixture_state",
            "result_state",
            "context_key",
            "record_address",
            "result_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), f"receipt index {name}")
        if not self.source_ids:
            raise ValueError("receipt index entry requires source IDs")
        if not self.record_address.startswith("sha256:"):
            raise ValueError("receipt index record address must be sha256-prefixed")
        if not self.result_address.startswith("sha256:"):
            raise ValueError("receipt index result address must be sha256-prefixed")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("receipt index entry address must be sha256-prefixed")

    def _address_body(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operation": self.operation,
            "fixture_state": self.fixture_state,
            "result_state": self.result_state,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "record_address": self.record_address,
            "result_address": self.result_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageReceiptIndex:
    """Deterministic release index for all fixture receipts."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    entries: tuple[SpecimenLineageReceiptIndexEntry, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "receipt index fixture ID")
        require_non_empty(self.context_key, "receipt index context")
        if not self.entries:
            raise ValueError("receipt index requires entries")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("receipt index address must be sha256-prefixed")

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(entry.record_id for entry in self.entries)

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({entry.operation for entry in self.entries}))

    @property
    def result_addresses(self) -> tuple[str, ...]:
        return tuple(entry.result_address for entry in self.entries)

    def _address_body(self) -> dict[str, Any]:
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
class SpecimenLineageReconciliationCheck:
    """One cross-view receipt-index assertion."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageReconciliationReport:
    """Receipt-index audit report."""

    fixture_id: str
    state: str
    checks: tuple[SpecimenLineageReconciliationCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
        }


def build_specimen_lineage_receipt_index(
    catalog: SpecimenLineageFixtureCatalog,
) -> SpecimenLineageReceiptIndex:
    """Join evaluator receipts to fixture records without copying raw payload."""

    evaluation = evaluate_specimen_lineage_fixture(catalog)
    receipts = {receipt.record_id: receipt for receipt in evaluation.receipts}
    entries: list[SpecimenLineageReceiptIndexEntry] = []
    for record in catalog.records:
        receipt = receipts[record.record_id]
        body = {
            "record_id": record.record_id,
            "operation": record.operation.value,
            "fixture_state": record.expected_fixture_state.value,
            "result_state": receipt.observed_result_state,
            "context_key": record.context_key,
            "source_ids": record.source_ids,
            "record_address": record.content_address,
            "result_address": receipt.output_address,
        }
        entries.append(
            SpecimenLineageReceiptIndexEntry(
                record_id=record.record_id,
                operation=record.operation.value,
                fixture_state=record.expected_fixture_state.value,
                result_state=receipt.observed_result_state,
                context_key=record.context_key,
                source_ids=record.source_ids,
                record_address=record.content_address,
                result_address=receipt.output_address,
                content_address=content_hash(body),
            )
        )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "source_ids": catalog.source_ids,
        "entries": entries,
    }
    return SpecimenLineageReceiptIndex(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        source_ids=catalog.source_ids,
        entries=tuple(entries),
        content_address=content_hash(body),
    )


def audit_specimen_lineage_receipt_index(
    catalog: SpecimenLineageFixtureCatalog,
    index: SpecimenLineageReceiptIndex,
) -> SpecimenLineageReconciliationReport:
    """Reconcile the index against a fresh evaluator run and the catalog."""

    evaluation = evaluate_specimen_lineage_fixture(catalog)
    expected_records = {record.record_id: record for record in catalog.records}
    expected_receipts = {receipt.record_id: receipt for receipt in evaluation.receipts}
    checks: list[SpecimenLineageReconciliationCheck] = []
    checks.append(
        _check(
            "fixture-id",
            index.fixture_id == catalog.fixture_id,
            index.fixture_id,
            catalog.fixture_id,
        )
    )
    checks.append(
        _check(
            "context",
            index.context_key == catalog.context_key,
            index.context_key,
            catalog.context_key,
        )
    )
    checks.append(
        _check(
            "source-set",
            set(index.source_ids) == set(catalog.source_ids),
            index.source_ids,
            catalog.source_ids,
        )
    )
    checks.append(
        _check(
            "entry-floor",
            len(index.entries) == len(catalog.records),
            len(index.entries),
            len(catalog.records),
        )
    )
    checks.append(
        _check(
            "record-identity",
            set(index.record_ids) == set(expected_records),
            index.record_ids,
            tuple(expected_records),
        )
    )
    checks.append(
        _check(
            "record-uniqueness",
            len(set(index.record_ids)) == len(index.entries),
            len(set(index.record_ids)),
            len(index.entries),
        )
    )
    checks.append(
        _check(
            "operation-coverage",
            set(index.operation_ids) == {item.value for item in SpecimenLineageOperation},
            index.operation_ids,
            tuple(item.value for item in SpecimenLineageOperation),
        )
    )
    checks.append(
        _check(
            "context-consistency",
            all(entry.context_key == catalog.context_key for entry in index.entries),
            True,
            True,
        )
    )
    checks.append(
        _check(
            "source-consistency",
            all(set(entry.source_ids).issubset(set(catalog.source_ids)) for entry in index.entries),
            True,
            True,
        )
    )
    checks.append(
        _check(
            "record-addresses",
            all(
                entry.record_address == expected_records[entry.record_id].content_address
                for entry in index.entries
                if entry.record_id in expected_records
            ),
            True,
            True,
        )
    )
    checks.append(
        _check(
            "result-addresses",
            all(
                entry.result_address == expected_receipts[entry.record_id].output_address
                for entry in index.entries
                if entry.record_id in expected_receipts
            ),
            True,
            True,
        )
    )
    checks.append(
        _check(
            "state-alignment",
            all(
                entry.result_state == expected_receipts[entry.record_id].observed_result_state
                for entry in index.entries
                if entry.record_id in expected_receipts
            ),
            True,
            True,
        )
    )
    checks.append(
        _check(
            "entry-addresses",
            all(
                entry.content_address == content_hash(entry._address_body())
                for entry in index.entries
            ),
            True,
            True,
        )
    )
    checks.append(
        _check(
            "index-address",
            index.content_address == content_hash(index._address_body()),
            index.content_address,
            "sha256:<recomputed>",
        )
    )
    checks.append(
        _check(
            "address-uniqueness",
            len(set(index.result_addresses)) == len(index.entries),
            len(set(index.result_addresses)),
            len(index.entries),
        )
    )
    checks.append(_check("sanitized-index", not _forbidden_keys(index.to_dict()), True, True))
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {"fixture_id": catalog.fixture_id, "state": state, "checks": checks}
    return SpecimenLineageReconciliationReport(
        fixture_id=catalog.fixture_id,
        state=state,
        checks=tuple(checks),
        content_address=content_hash(body),
    )


def _check(
    check_id: str, passed: bool, observed: Any, expected: Any
) -> SpecimenLineageReconciliationCheck:
    return SpecimenLineageReconciliationCheck(
        check_id=check_id,
        passed=bool(passed),
        observed=observed,
        expected=expected,
        message=f"{check_id} receipt reconciliation",
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
    "SpecimenLineageReceiptIndex",
    "SpecimenLineageReceiptIndexEntry",
    "SpecimenLineageReconciliationCheck",
    "SpecimenLineageReconciliationReport",
    "audit_specimen_lineage_receipt_index",
    "build_specimen_lineage_receipt_index",
]
