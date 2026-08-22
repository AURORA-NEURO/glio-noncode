"""Schema and contract coverage checks for the Domain 10 link frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_contracts import LinkFrontierContractRegistry, default_link_frontier_contracts
from .link_frontier_public_data import (
    LinkFrontierFixture,
    LinkFrontierOperation,
    default_link_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierSchema:
    schema_id: str
    operation: LinkFrontierOperation
    version: str
    required_fields: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierSchemaCheck:
    check_id: str
    schema_id: str
    check_kind: str
    passed: bool
    expected: Any
    observed: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierSchemaReport:
    fixture_id: str
    schemas: tuple[LinkFrontierSchema, ...]
    checks: tuple[LinkFrontierSchemaCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _schema(contract: Any) -> LinkFrontierSchema:
    body = {
        "schema_id": contract.contract_id.replace("contract", "schema"),
        "operation": contract.operation,
        "version": "v1",
        "required_fields": contract.required_payload_fields,
        "state_values": tuple(sorted(set(contract.positive_states + contract.control_states))),
        "issue_codes": contract.issue_vocabulary,
    }
    return LinkFrontierSchema(**body, content_address=content_hash(body))


def default_link_frontier_schemas(
    contracts: LinkFrontierContractRegistry | None = None,
) -> tuple[LinkFrontierSchema, ...]:
    contracts = contracts or default_link_frontier_contracts()
    return tuple(_schema(contract) for contract in contracts.contracts)


def _check(schema: LinkFrontierSchema, kind: str, passed: bool, expected: Any, observed: Any) -> LinkFrontierSchemaCheck:
    body = {
        "check_id": f"{schema.schema_id}:{kind}",
        "schema_id": schema.schema_id,
        "check_kind": kind,
        "passed": passed,
        "expected": expected,
        "observed": observed,
    }
    return LinkFrontierSchemaCheck(**body, content_address=content_hash(body))


def validate_link_frontier_schema(
    fixture: LinkFrontierFixture | None = None,
    *,
    contracts: LinkFrontierContractRegistry | None = None,
) -> LinkFrontierSchemaReport:
    fixture = fixture or default_link_frontier_fixture()
    contracts = contracts or default_link_frontier_contracts()
    schemas = default_link_frontier_schemas(contracts)
    operations = {record.operation for record in fixture.records}
    checks: list[LinkFrontierSchemaCheck] = []
    for schema in schemas:
        contract = contracts.by_operation(schema.operation)
        checks.extend(
            (
                _check(schema, "required_fields", bool(schema.required_fields), True, schema.required_fields),
                _check(schema, "states", set(schema.state_values) >= {"supported", "partial", "invalid"} if schema.operation is not LinkFrontierOperation.EVIDENCE_PUBLICATION else "published" in schema.state_values, True, schema.state_values),
                _check(schema, "issues", bool(schema.issue_codes) and set(schema.issue_codes) >= set(contract.issue_vocabulary), True, schema.issue_codes),
                _check(schema, "operation", schema.operation in operations, True, schema.operation.value),
                _check(schema, "address", bool(schema.content_address), True, bool(schema.content_address)),
            )
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "schemas": schemas,
        "checks": checks,
        "accepted": bool(checks) and all(item.passed for item in checks),
    }
    return LinkFrontierSchemaReport(**body, content_address=content_hash(body))


__all__ = [
    "LinkFrontierSchema",
    "LinkFrontierSchemaCheck",
    "LinkFrontierSchemaReport",
    "default_link_frontier_schemas",
    "validate_link_frontier_schema",
]
