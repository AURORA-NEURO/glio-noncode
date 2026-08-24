"""Deep D10 closure audit."""

from __future__ import annotations

from .link_graph_architecture_compliance import assess_link_graph_architecture_compliance
from .link_graph_architecture_contract_matrix import (
    link_graph_architecture_contract_matrix_is_closed,
)
from .link_graph_architecture_controls import link_graph_architecture_controls_are_closed
from .link_graph_architecture_lineage import (
    build_link_graph_architecture_lineage,
    link_graph_architecture_lineage_gaps,
)
from .link_graph_architecture_metrics import (
    link_graph_architecture_metric_invariants,
    link_graph_architecture_metrics,
)
from .link_graph_architecture_operations import evaluate_link_graph_architecture_fixture
from .link_graph_architecture_public_data import audit_link_graph_architecture_data
from .link_graph_architecture_replay import replay_link_graph_architecture_fixture
from .link_graph_architecture_schema import validate_link_graph_architecture_fixture


def link_graph_architecture_invariants(fixture) -> dict[str, bool]:
    evaluation = evaluate_link_graph_architecture_fixture(fixture)
    metrics = link_graph_architecture_metrics(fixture, evaluation)
    return {
        "typed": validate_link_graph_architecture_fixture(fixture),
        "audit": audit_link_graph_architecture_data(fixture).accepted,
        "evaluation": evaluation.accepted,
        "replay": replay_link_graph_architecture_fixture(fixture).accepted,
        "compliance": bool(assess_link_graph_architecture_compliance(fixture)["accepted"]),
        "metrics": not link_graph_architecture_metric_invariants(metrics),
        "lineage": not link_graph_architecture_lineage_gaps(fixture),
        "matrix": link_graph_architecture_contract_matrix_is_closed(fixture),
        "controls": link_graph_architecture_controls_are_closed(fixture, evaluation),
    }


def deep_audit_link_graph_architecture(fixture) -> dict[str, object]:
    checks = link_graph_architecture_invariants(fixture)
    lineage = build_link_graph_architecture_lineage(fixture)
    evaluation = evaluate_link_graph_architecture_fixture(fixture)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "accepted": all(checks.values()),
        "lineage_address": lineage["content_address"],
        "evaluation_address": evaluation.content_address,
    }
    from .link_graph_architecture_contracts import addressed

    return body | {"content_address": addressed(body, "link-deep-audit")}


__all__ = ["deep_audit_link_graph_architecture", "link_graph_architecture_invariants"]
