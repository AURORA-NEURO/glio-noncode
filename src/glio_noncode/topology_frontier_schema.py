"""Serialized contract shape checks for Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_contracts import (
    default_topology_frontier_contracts,
)
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_public_data import TopologyFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyFrontierSchema:
    schema_id: str
    operation: TopologyFrontierOperation
    required_fields: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_values: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierSchemaCheck:
    check_id: str
    operation: TopologyFrontierOperation
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierSchemaReport:
    schemas: tuple[TopologyFrontierSchema, ...]
    checks: tuple[TopologyFrontierSchemaCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def default_topology_frontier_schemas() -> tuple[TopologyFrontierSchema, ...]:
    rows: list[TopologyFrontierSchema] = []
    for contract in default_topology_frontier_contracts().contracts:
        body = {
            "schema_id": contract.contract_id.replace("contract", "schema"),
            "operation": contract.operation,
            "required_fields": contract.required_payload_fields,
            "state_values": tuple(dict.fromkeys(contract.positive_states + contract.control_states)),
            "issue_values": contract.issue_vocabulary,
        }
        rows.append(TopologyFrontierSchema(**body, content_address=content_hash(body)))
    return tuple(rows)


def validate_topology_frontier_schema(
    evaluation: TopologyFrontierEvaluationReport,
    *,
    schemas: tuple[TopologyFrontierSchema, ...] | None = None,
) -> TopologyFrontierSchemaReport:
    selected = schemas or default_topology_frontier_schemas()
    schema_map = {item.operation: item for item in selected}
    checks: list[TopologyFrontierSchemaCheck] = []

    def add(check_id: str, operation: TopologyFrontierOperation, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "operation": operation, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierSchemaCheck(**body, content_address=content_hash(body)))

    for operation in TopologyFrontierOperation:
        schema = schema_map.get(operation)
        rows = tuple(item for item in evaluation.receipts if item.operation is operation)
        add(f"{operation.value}:schema-present", operation, schema is not None, "schema exists")
        if schema is None:
            continue
        add(f"{operation.value}:records", operation, len(rows) == 4, "four records are covered")
        add(f"{operation.value}:state-values", operation, all(item.adapter_state in schema.state_values for item in rows), "states are in the declared vocabulary")
        add(f"{operation.value}:issue-values", operation, all(set(item.observed_issue_codes) <= set(schema.issue_values) for item in rows), "issues are in the declared vocabulary")
        add(f"{operation.value}:address", operation, schema.content_address.startswith("sha256:"), "schema is addressed")
    body = {"schemas": selected, "checks": checks}
    return TopologyFrontierSchemaReport(tuple(selected), tuple(checks), content_hash(body))


__all__ = [
    "TopologyFrontierSchema",
    "TopologyFrontierSchemaCheck",
    "TopologyFrontierSchemaReport",
    "default_topology_frontier_schemas",
    "validate_topology_frontier_schema",
]
