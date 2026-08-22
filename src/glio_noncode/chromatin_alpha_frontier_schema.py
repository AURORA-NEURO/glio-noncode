"""Schema, source, and public-boundary checks for chromatin-alpha rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_contracts import build_chromatin_alpha_frontier_contracts
from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import (
    CHROMATIN_ALPHA_FRONTIER_BOUNDARY,
    CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
    ChromatinAlphaFrontierFixture,
    ChromatinAlphaFrontierOperation,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("schema check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierSchemaReport:
    checks: tuple[ChromatinAlphaFrontierSchemaCheck, ...]
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
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def validate_chromatin_alpha_frontier_schema(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierSchemaReport:
    contracts = build_chromatin_alpha_frontier_contracts(fixture.evidence_boundary)
    operations = {contract.operation for contract in contracts.contracts}
    forbidden = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    checks = (
        ChromatinAlphaFrontierSchemaCheck(
            "contracts", contracts.accepted, "four operation contracts resolve"
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "fixture_context",
            fixture.context_key == CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
            "fixture context is exact",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "fixture_boundary",
            fixture.evidence_boundary == CHROMATIN_ALPHA_FRONTIER_BOUNDARY,
            "public aggregate boundary is retained",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "fixture_identity", bool(fixture.fixture_id), "fixture identity is present"
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "fixture_sources", len(fixture.sources) == 5, "five source receipts are declared"
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "record_count", len(fixture.records) == 16, "sixteen records are present"
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "record_roles",
            len(fixture.positive_records) == 4 and len(fixture.control_records) == 12,
            "positive and control roles are balanced",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "operation_contracts",
            all(record.operation in operations for record in fixture.records),
            "every record operation has a contract",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "payload_objects",
            all(bool(record.payload) for record in fixture.records),
            "record payloads are non-empty objects",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "boundary_keys",
            all(
                not (set(str(key).lower() for key in record.payload) & forbidden)
                for record in fixture.records
            ),
            "subject-level keys are absent",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "record_receipts",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "record receipts are addressed",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "result_receipts",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "result receipts are addressed",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "context_receipts",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "record context is locked",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "input_text",
            all(isinstance(record.payload.get("input_text"), str) for record in fixture.records),
            "primitive input is serialized text",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "expected_paths",
            all(record.expected_state for record in fixture.records),
            "expected state paths are declared",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "evaluation_count",
            len(evaluation.records) == len(fixture.records),
            "all records have evaluations",
        ),
        ChromatinAlphaFrontierSchemaCheck(
            "positive_states",
            all(
                item.observed_state == "supported"
                for item in evaluation.records
                if item.role == "positive"
            ),
            "positive rows are supported",
        ),
    )
    return ChromatinAlphaFrontierSchemaReport(
        checks=checks,
        accepted=all(check.passed for check in checks),
        field_count=sum(len(contract.required_fields) for contract in contracts.contracts),
    )


def chromatin_alpha_frontier_schema_manifest() -> dict[str, Any]:
    contracts = build_chromatin_alpha_frontier_contracts()
    body = {
        "context_key": CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
        "boundary": CHROMATIN_ALPHA_FRONTIER_BOUNDARY,
        "operations": [operation.value for operation in ChromatinAlphaFrontierOperation],
        "contracts": [contract.to_dict() for contract in contracts.contracts],
    }
    return body | {"content_address": content_hash(body)}


__all__ = [
    "ChromatinAlphaFrontierSchemaCheck",
    "ChromatinAlphaFrontierSchemaReport",
    "chromatin_alpha_frontier_schema_manifest",
    "validate_chromatin_alpha_frontier_schema",
]
