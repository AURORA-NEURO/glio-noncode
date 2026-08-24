"""Deep D11 closure audit."""

from __future__ import annotations

from .causal_architecture_compliance import assess_causal_architecture_compliance
from .causal_architecture_contract_matrix import causal_architecture_contract_matrix_is_closed
from .causal_architecture_controls import causal_architecture_controls_are_closed
from .causal_architecture_lineage import (
    build_causal_architecture_lineage,
    causal_architecture_lineage_gaps,
)
from .causal_architecture_metrics import (
    causal_architecture_metric_invariants,
    causal_architecture_metrics,
)
from .causal_architecture_operations import evaluate_causal_architecture_fixture
from .causal_architecture_public_data import audit_causal_architecture_data
from .causal_architecture_replay import replay_causal_architecture_fixture
from .causal_architecture_schema import validate_causal_architecture_fixture


def causal_architecture_invariants(fixture) -> dict[str, bool]:
    evaluation = evaluate_causal_architecture_fixture(fixture)
    metrics = causal_architecture_metrics(fixture, evaluation)
    return {
        "typed": validate_causal_architecture_fixture(fixture),
        "audit": audit_causal_architecture_data(fixture).accepted,
        "evaluation": evaluation.accepted,
        "replay": replay_causal_architecture_fixture(fixture).accepted,
        "compliance": bool(assess_causal_architecture_compliance(fixture)["accepted"]),
        "metrics": not causal_architecture_metric_invariants(metrics),
        "lineage": not causal_architecture_lineage_gaps(fixture),
        "matrix": causal_architecture_contract_matrix_is_closed(fixture),
        "controls": causal_architecture_controls_are_closed(fixture, evaluation),
    }


def deep_audit_causal_architecture(fixture) -> dict[str, object]:
    checks = causal_architecture_invariants(fixture)
    lineage = build_causal_architecture_lineage(fixture)
    evaluation = evaluate_causal_architecture_fixture(fixture)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "accepted": all(checks.values()),
        "lineage_address": lineage["content_address"],
        "evaluation_address": evaluation.content_address,
    }
    from .causal_architecture_contracts import addressed

    return body | {"content_address": addressed(body, "causal-deep-audit")}


__all__ = ["causal_architecture_invariants", "deep_audit_causal_architecture"]
