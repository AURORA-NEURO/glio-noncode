"""Public aggregate fixture and source receipts for D16 coordination control."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .serialization import content_hash, jsonable
from .coordination_architecture_contracts import (
    COORDINATION_BOUNDARY,
    COORDINATION_CASE_COUNT,
    COORDINATION_CONTEXT,
    COORDINATION_FOREIGN_CONTEXT,
    COORDINATION_OPERATION_COUNT,
    COORDINATION_VERSION,
    CoordinationCase,
    CoordinationFixture,
    CoordinationOperation,
    CoordinationOperationSpec,
    CoordinationRole,
    CoordinationScenario,
    CoordinationSource,
    CoordinationState,
)


COORDINATION_SOURCE_COUNT = 5


@dataclass(frozen=True, slots=True)
class CoordinationDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationDataAudit:
    fixture_id: str
    checks: tuple[CoordinationDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, version: str) -> CoordinationSource:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "scope": "public_aggregate",
        "version": version,
    }
    return CoordinationSource(**body, content_address=content_hash(body, prefix="coordination-source"))


def default_coordination_sources() -> tuple[CoordinationSource, ...]:
    return (
        _source(
            "blueprint-receipt",
            "GLIO-NONCODE capability blueprint receipt",
            "https://github.com/AURORA-NEURO/glio-noncode",
            "blueprint-2026-08-20",
        ),
        _source(
            "ensembl-reference",
            "Ensembl public reference portal",
            "https://www.ensembl.org/info/data/index.html",
            "public reference portal",
        ),
        _source(
            "ncbi-datasets",
            "NCBI public datasets portal",
            "https://www.ncbi.nlm.nih.gov/datasets/",
            "public aggregate index",
        ),
        _source(
            "encode-portal",
            "ENCODE public data portal",
            "https://www.encodeproject.org/",
            "public aggregate portal",
        ),
        _source(
            "gdc-portal",
            "NCI Genomic Data Commons public portal",
            "https://portal.gdc.cancer.gov/",
            "public aggregate portal",
        ),
    )


_OPERATION_ROWS: tuple[tuple[CoordinationOperation, CoordinationRole, str, str], ...] = (
    (CoordinationOperation.MISSION_PLAN, CoordinationRole.PLANNER, "mission.request.v1", "mission.plan.v1"),
    (CoordinationOperation.WORKFLOW_COMPILE, CoordinationRole.COMPILER, "mission.plan.v1", "workflow.graph.v1"),
    (CoordinationOperation.TYPED_TOOL_REGISTRY, CoordinationRole.TOOL_REGISTRY, "workflow.graph.v1", "tool.registry.v1"),
    (CoordinationOperation.EXECUTION_SANDBOX, CoordinationRole.SANDBOX, "tool.registry.v1", "sandbox.receipt.v1"),
    (CoordinationOperation.CLAIM_GATE, CoordinationRole.POLICY, "sandbox.receipt.v1", "policy.decision.v1"),
    (CoordinationOperation.RESOURCE_SCHEDULE, CoordinationRole.SCHEDULER, "policy.decision.v1", "schedule.plan.v1"),
    (CoordinationOperation.FALLBACK_ROUTE, CoordinationRole.FALLBACK, "schedule.plan.v1", "fallback.route.v1"),
    (CoordinationOperation.HUMAN_REVIEW, CoordinationRole.REVIEW, "fallback.route.v1", "review.queue.v1"),
    (CoordinationOperation.EVENT_LEDGER, CoordinationRole.LEDGER, "review.queue.v1", "event.ledger.v1"),
    (CoordinationOperation.COMPUTE_REGISTRY, CoordinationRole.COMPUTE_REGISTRY, "event.ledger.v1", "compute.registry.v1"),
    (CoordinationOperation.REFERENCE_REGISTRY, CoordinationRole.REFERENCE_REGISTRY, "compute.registry.v1", "reference.registry.v1"),
    (CoordinationOperation.DRIFT_MONITOR, CoordinationRole.MONITORING, "reference.registry.v1", "monitoring.observation.v1"),
    (CoordinationOperation.SECURITY_POLICY, CoordinationRole.SECURITY, "monitoring.observation.v1", "security.decision.v1"),
    (CoordinationOperation.DEPLOYMENT_BUNDLE, CoordinationRole.DEPLOYMENT, "security.decision.v1", "deployment.bundle.v1"),
    (CoordinationOperation.FEDERATED_COORDINATION, CoordinationRole.FEDERATION, "deployment.bundle.v1", "federation.assignment.v1"),
    (CoordinationOperation.RELEASE_ROLLBACK, CoordinationRole.RELEASE, "federation.assignment.v1", "release.manifest.v1"),
)


def _spec(
    ordinal: int,
    operation: CoordinationOperation,
    role: CoordinationRole,
    input_contract: str,
    output_contract: str,
    source_ids: tuple[str, ...],
) -> CoordinationOperationSpec:
    body = {
        "operation_id": f"COORD-D16-C{ordinal:02d}",
        "capability_id": f"GNC-D16-C{ordinal:02d}",
        "ordinal": ordinal,
        "operation": operation,
        "role": role,
        "input_contract": input_contract,
        "output_contract": output_contract,
        "dependencies": () if ordinal == 1 else (f"COORD-D16-C{ordinal - 1:02d}",),
        "budget_units": ordinal + 2,
        "requires_review": ordinal in {5, 7, 8, 12, 13, 15, 16},
        "source_ids": source_ids,
    }
    return CoordinationOperationSpec(**body, content_address=content_hash(body, prefix="coordination-operation"))


def default_coordination_operations() -> tuple[CoordinationOperationSpec, ...]:
    sources = tuple(item.source_id for item in default_coordination_sources())
    return tuple(
        _spec(index, operation, role, input_contract, output_contract, (sources[index % len(sources)], "blueprint-receipt"))
        for index, (operation, role, input_contract, output_contract) in enumerate(_OPERATION_ROWS, start=1)
    )


def _payload(spec: CoordinationOperationSpec, scenario: CoordinationScenario) -> dict[str, Any]:
    values: dict[str, Any] = {
        "record_role": "positive" if scenario is CoordinationScenario.POSITIVE else "control",
        "declared_operation_id": spec.operation_id,
        "declared_capability_id": spec.capability_id,
        "declared_context_key": COORDINATION_CONTEXT,
        "declared_input_contract": spec.input_contract,
        "declared_output_contract": spec.output_contract,
        "available_budget_units": 128,
        "requested_budget_units": spec.budget_units,
        "network_requested": False,
        "public_aggregate_only": True,
        "schema_version": COORDINATION_VERSION,
        "route": "local_deterministic",
        "claim_boundary": COORDINATION_BOUNDARY,
    }
    if scenario is CoordinationScenario.FOREIGN_CONTEXT:
        values["declared_context_key"] = COORDINATION_FOREIGN_CONTEXT
    elif scenario is CoordinationScenario.BUDGET_EXCEEDED:
        values["available_budget_units"] = 0
    elif scenario is CoordinationScenario.CONTRACT_MISMATCH:
        values["declared_input_contract"] = "mismatch.contract.v0"
    return values


def _case(spec: CoordinationOperationSpec, scenario: CoordinationScenario, source_ids: tuple[str, ...]) -> CoordinationCase:
    issue_codes = {
        CoordinationScenario.POSITIVE: (),
        CoordinationScenario.FOREIGN_CONTEXT: ("foreign_context",),
        CoordinationScenario.BUDGET_EXCEEDED: ("budget_exceeded",),
        CoordinationScenario.CONTRACT_MISMATCH: ("contract_mismatch",),
    }[scenario]
    body = {
        "case_id": f"{spec.operation_id}-{scenario.value}",
        "operation_id": spec.operation_id,
        "capability_id": spec.capability_id,
        "role": spec.role,
        "scenario": scenario,
        "context_key": COORDINATION_CONTEXT,
        "source_ids": source_ids,
        "payload": _payload(spec, scenario),
        "expected_state": CoordinationState.ACCEPTED if scenario is CoordinationScenario.POSITIVE else CoordinationState.REVIEW,
        "expected_issue_codes": issue_codes,
    }
    if contains_private_key(body["payload"]):
        raise ValidationError("coordination fixture payload contains a private key")
    return CoordinationCase(**body, content_address=content_hash(body, prefix="coordination-case"))


def default_coordination_fixture() -> CoordinationFixture:
    sources = default_coordination_sources()
    source_ids = tuple(item.source_id for item in sources)
    operations = default_coordination_operations()
    cases = tuple(
        case
        for spec in operations
        for case in (
            _case(spec, CoordinationScenario.POSITIVE, (source_ids[spec.ordinal % len(source_ids)], "blueprint-receipt")),
            _case(spec, CoordinationScenario.FOREIGN_CONTEXT, (source_ids[spec.ordinal % len(source_ids)], "blueprint-receipt")),
            _case(spec, CoordinationScenario.BUDGET_EXCEEDED, (source_ids[spec.ordinal % len(source_ids)], "blueprint-receipt")),
            _case(spec, CoordinationScenario.CONTRACT_MISMATCH, (source_ids[spec.ordinal % len(source_ids)], "blueprint-receipt")),
        )
    )
    body = {
        "fixture_id": "coordination-architecture-d16",
        "version": COORDINATION_VERSION,
        "boundary": COORDINATION_BOUNDARY,
        "context_key": COORDINATION_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return CoordinationFixture(**body, content_address=content_hash(body, prefix="coordination-fixture"))


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> CoordinationDataCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return CoordinationDataCheck(**body, content_address=content_hash(body, prefix="coordination-data-check"))


def audit_coordination_data(fixture: CoordinationFixture | None = None) -> CoordinationDataAudit:
    value = fixture or default_coordination_fixture()
    operation_ids = tuple(item.operation_id for item in value.operations)
    case_counts = {operation_id: sum(item.operation_id == operation_id for item in value.cases) for operation_id in operation_ids}
    source_ids = {item.source_id for item in value.sources}
    checks = (
        _check("source-count", len(value.sources) == COORDINATION_SOURCE_COUNT, len(value.sources), COORDINATION_SOURCE_COUNT, "public source denominator is closed"),
        _check("operation-count", len(value.operations) == COORDINATION_OPERATION_COUNT, len(value.operations), COORDINATION_OPERATION_COUNT, "sixteen D16 operations are represented"),
        _check("case-count", len(value.cases) == COORDINATION_CASE_COUNT, len(value.cases), COORDINATION_CASE_COUNT, "four scenarios per operation are represented"),
        _check("operation-ids-unique", len(set(operation_ids)) == len(operation_ids), len(set(operation_ids)), len(operation_ids), "operation IDs are unique"),
        _check("case-ids-unique", len({item.case_id for item in value.cases}) == len(value.cases), len({item.case_id for item in value.cases}), len(value.cases), "case IDs are unique"),
        _check("case-cardinality", all(count == 4 for count in case_counts.values()), tuple(sorted(set(case_counts.values()))), (4,), "every operation has four cases"),
        _check("source-joins", all(set(item.source_ids) <= source_ids for item in value.cases), True, True, "case source joins resolve"),
        _check("public-scope", all(item.scope == "public_aggregate" for item in value.sources), True, True, "all source receipts are public aggregate"),
        _check("payload-safety", all(not contains_private_key(item.payload) for item in value.cases), True, True, "fixture payloads contain no private subject keys"),
        _check("positive-controls", len(value.positive_cases) == 16 and len(value.control_cases) == 48, (len(value.positive_cases), len(value.control_cases)), (16, 48), "positive and control roles are balanced"),
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return CoordinationDataAudit(value.fixture_id, checks, accepted, content_hash(body, prefix="coordination-data-audit"))


def coordination_fixture_json(fixture: CoordinationFixture | None = None) -> str:
    return json.dumps((fixture or default_coordination_fixture()).to_dict(), indent=2, sort_keys=True) + "\n"


def load_coordination_fixture(path: str | Path) -> CoordinationFixture:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"unable to read coordination fixture: {path}") from exc
    if not isinstance(value, Mapping):
        raise ValidationError("coordination fixture must be a JSON object")
    expected = default_coordination_fixture()
    if value.get("content_address") != expected.content_address:
        raise ValidationError("coordination fixture content address does not match canonical fixture")
    return expected


__all__ = [
    "COORDINATION_SOURCE_COUNT",
    "CoordinationDataCheck",
    "CoordinationDataAudit",
    "default_coordination_sources",
    "default_coordination_operations",
    "default_coordination_fixture",
    "audit_coordination_data",
    "coordination_fixture_json",
    "load_coordination_fixture",
]
