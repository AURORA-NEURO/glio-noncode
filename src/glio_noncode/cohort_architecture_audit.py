"""Deep D12 closure audit."""

from __future__ import annotations

from .cohort_architecture_compliance import assess_cohort_architecture_compliance
from .cohort_architecture_contract_matrix import cohort_architecture_contract_matrix_is_closed
from .cohort_architecture_controls import cohort_architecture_controls_are_closed
from .cohort_architecture_lineage import (
    build_cohort_architecture_lineage,
    cohort_architecture_lineage_gaps,
)
from .cohort_architecture_metrics import (
    cohort_architecture_metric_invariants,
    cohort_architecture_metrics,
)
from .cohort_architecture_operations import evaluate_cohort_architecture_fixture
from .cohort_architecture_public_data import audit_cohort_architecture_data
from .cohort_architecture_replay import replay_cohort_architecture_fixture
from .cohort_architecture_schema import validate_cohort_architecture_fixture


def cohort_architecture_invariants(fixture) -> dict[str, bool]:
    evaluation = evaluate_cohort_architecture_fixture(fixture)
    metrics = cohort_architecture_metrics(fixture, evaluation)
    return {
        "typed": validate_cohort_architecture_fixture(fixture),
        "audit": audit_cohort_architecture_data(fixture).accepted,
        "evaluation": evaluation.accepted,
        "replay": replay_cohort_architecture_fixture(fixture).accepted,
        "compliance": bool(assess_cohort_architecture_compliance(fixture)["accepted"]),
        "metrics": not cohort_architecture_metric_invariants(metrics),
        "lineage": not cohort_architecture_lineage_gaps(fixture),
        "matrix": cohort_architecture_contract_matrix_is_closed(fixture),
        "controls": cohort_architecture_controls_are_closed(fixture, evaluation),
    }


def deep_audit_cohort_architecture(fixture) -> dict[str, object]:
    checks = cohort_architecture_invariants(fixture)
    lineage = build_cohort_architecture_lineage(fixture)
    evaluation = evaluate_cohort_architecture_fixture(fixture)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "accepted": all(checks.values()),
        "lineage_address": lineage["content_address"],
        "evaluation_address": evaluation.content_address,
    }
    from .cohort_architecture_contracts import addressed

    return body | {"content_address": addressed(body, "cohort-deep-audit")}


__all__ = ["cohort_architecture_invariants", "deep_audit_cohort_architecture"]
