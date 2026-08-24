"""Deep cross-surface audit for D09 topology."""

from __future__ import annotations

from typing import Any

from .topology_architecture_compliance import assess_topology_architecture_compliance
from .topology_architecture_contract_matrix import topology_architecture_contract_matrix_is_closed
from .topology_architecture_contracts import TopologyArchitectureFixture, addressed
from .topology_architecture_controls import topology_architecture_controls_are_closed
from .topology_architecture_lineage import (
    build_topology_architecture_lineage,
    topology_architecture_lineage_gaps,
)
from .topology_architecture_metrics import (
    topology_architecture_metric_invariants,
    topology_architecture_metrics,
)
from .topology_architecture_operations import evaluate_topology_architecture_fixture
from .topology_architecture_public_data import audit_topology_architecture_data
from .topology_architecture_replay import replay_topology_architecture_fixture
from .topology_architecture_schema import validate_topology_architecture_fixture


def topology_architecture_invariants(fixture: TopologyArchitectureFixture) -> dict[str, bool]:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    return {
        "source_count": len(source_ids) == 17,
        "operation_count": len(operation_ids) == 16,
        "case_count": len(fixture.cases) == 64,
        "public_source_visibility": all(item.public_aggregate for item in fixture.sources),
        "source_joins": all(
            set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
        ),
        "operation_joins": all(item.operation_id in operation_ids for item in fixture.cases),
        "operation_balance": all(
            sum(item.operation_id == operation.operation_id for item in fixture.cases) == 4
            for operation in fixture.operations
        ),
        "scenario_balance": (len(fixture.positive_cases), len(fixture.control_cases)) == (16, 48),
        "family_coverage": len({item.family for item in fixture.operations}) == 4,
        "delegate_contexts": all(item.delegate_context_key for item in fixture.cases),
    }


def deep_audit_topology_architecture(fixture: TopologyArchitectureFixture) -> dict[str, Any]:
    audit = audit_topology_architecture_data(fixture)
    evaluation = evaluate_topology_architecture_fixture(fixture)
    replay = replay_topology_architecture_fixture(fixture)
    metrics = topology_architecture_metrics(fixture, evaluation)
    compliance = assess_topology_architecture_compliance(fixture)
    invariants = topology_architecture_invariants(fixture)
    checks = {
        "typed": validate_topology_architecture_fixture(fixture),
        "audit": audit.accepted,
        "evaluation": evaluation.accepted,
        "replay": replay.accepted,
        "compliance": compliance["accepted"],
        "invariants": all(invariants.values()),
        "metric_invariants": not topology_architecture_metric_invariants(metrics),
        "contract_matrix": topology_architecture_contract_matrix_is_closed(fixture),
        "controls": topology_architecture_controls_are_closed(fixture, evaluation),
        "lineage": not topology_architecture_lineage_gaps(fixture),
    }
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "accepted": all(checks.values()),
        "lineage_address": build_topology_architecture_lineage(fixture)["content_address"],
        "evaluation_address": evaluation.content_address,
    }
    return body | {"content_address": addressed(body, "topology-deep-audit")}


__all__ = ["deep_audit_topology_architecture", "topology_architecture_invariants"]
