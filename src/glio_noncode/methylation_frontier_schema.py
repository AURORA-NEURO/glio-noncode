"""Schema and public-boundary checks for methylation records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_contracts import build_methylation_frontier_contracts
from .methylation_frontier_public_data import (
    MethylationFrontierFixture,
    MethylationFrontierOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierSchemaCheck:
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
class MethylationFrontierSchemaReport:
    checks: tuple[MethylationFrontierSchemaCheck, ...]
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


def validate_methylation_frontier_schema(
    fixture: MethylationFrontierFixture,
) -> MethylationFrontierSchemaReport:
    contracts = build_methylation_frontier_contracts()
    operation_set = {contract.operation for contract in contracts.contracts}
    checks = (
        MethylationFrontierSchemaCheck(
            "contracts", contracts.accepted, "four operation contracts are available"
        ),
        MethylationFrontierSchemaCheck(
            "fixture_records", bool(fixture.records), "fixture has records"
        ),
        MethylationFrontierSchemaCheck(
            "record_context",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "records carry the fixture context",
        ),
        MethylationFrontierSchemaCheck(
            "record_operations",
            all(record.operation in operation_set for record in fixture.records),
            "each operation has a contract",
        ),
        MethylationFrontierSchemaCheck(
            "record_payloads",
            all(bool(record.payload) for record in fixture.records),
            "record payloads are objects",
        ),
        MethylationFrontierSchemaCheck(
            "record_receipts",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "records are content addressed",
        ),
        MethylationFrontierSchemaCheck(
            "source_receipts",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "sources are content addressed",
        ),
        MethylationFrontierSchemaCheck(
            "no_subject_keys",
            all(
                not {str(key).lower() for key in record.payload}
                & {"patient", "subject", "sample_id"}
                for record in fixture.records
            ),
            "subject-level keys are absent",
        ),
        MethylationFrontierSchemaCheck(
            "text_contract",
            all(
                record.operation is not MethylationFrontierOperation.CONTEXT_RETRIEVAL
                or isinstance(record.payload.get("text"), str)
                for record in fixture.records
            ),
            "retrieval payloads carry text",
        ),
    )
    return MethylationFrontierSchemaReport(
        checks=checks,
        accepted=all(check.passed for check in checks),
        field_count=sum(len(contract.required_fields) for contract in contracts.contracts),
    )


__all__ = [
    "MethylationFrontierSchemaCheck",
    "MethylationFrontierSchemaReport",
    "validate_methylation_frontier_schema",
]
