"""Schema and boundary checks for aggregate sequence-regulation records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_contracts import build_sequence_regulation_contracts
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("schema check requires identity and detail")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationSchemaReport:
    checks: tuple[SequenceRegulationSchemaCheck, ...]
    accepted: bool
    field_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("schema report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def validate_sequence_regulation_schema(
    fixture: SequenceRegulationFixture,
) -> SequenceRegulationSchemaReport:
    contracts = build_sequence_regulation_contracts()
    checks = [
        SequenceRegulationSchemaCheck(
            "contracts", contracts.accepted, "four operation contracts are available"
        ),
        SequenceRegulationSchemaCheck(
            "fixture_records", bool(fixture.records), "fixture has records"
        ),
        SequenceRegulationSchemaCheck(
            "record_context",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "records carry the fixture context",
        ),
        SequenceRegulationSchemaCheck(
            "record_operations",
            all(
                record.operation in {contract.operation for contract in contracts.contracts}
                for record in fixture.records
            ),
            "each operation has a contract",
        ),
        SequenceRegulationSchemaCheck(
            "record_payloads",
            all(bool(record.payload) for record in fixture.records),
            "record payloads are objects",
        ),
        SequenceRegulationSchemaCheck(
            "record_receipts",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "records are content addressed",
        ),
        SequenceRegulationSchemaCheck(
            "source_receipts",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "sources are content addressed",
        ),
        SequenceRegulationSchemaCheck(
            "no_subject_keys",
            all(
                not {str(key).lower() for key in record.payload}
                & {"patient", "subject", "sample_id"}
                for record in fixture.records
            ),
            "subject-level keys are absent",
        ),
    ]
    fields = sum(len(contract.required_fields) for contract in contracts.contracts)
    return SequenceRegulationSchemaReport(
        tuple(checks), all(check.passed for check in checks), fields
    )


__all__ = [
    "SequenceRegulationSchemaCheck",
    "SequenceRegulationSchemaReport",
    "validate_sequence_regulation_schema",
]
