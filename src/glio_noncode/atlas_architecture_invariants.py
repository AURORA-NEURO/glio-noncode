"""Cross-module conservation and boundary invariants for D05."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureLedger,
    AtlasArchitecturePlan,
    AtlasArchitectureReviewQueue,
    addressed,
)


def check_atlas_architecture_invariants(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    plan: AtlasArchitecturePlan,
    review_queue: AtlasArchitectureReviewQueue,
    ledger: AtlasArchitectureLedger,
) -> tuple[AtlasArchitectureCheck, ...]:
    values = (
        (
            "fixture-evaluation-join",
            fixture.fixture_id == evaluation.fixture_id,
            fixture.fixture_id,
            evaluation.fixture_id,
            "fixture and evaluation IDs join",
        ),
        (
            "fixture-plan-join",
            fixture.fixture_id == plan.fixture_id,
            fixture.fixture_id,
            plan.fixture_id,
            "fixture and plan IDs join",
        ),
        (
            "review-ledger-join",
            review_queue.fixture_id == ledger.fixture_id,
            review_queue.fixture_id,
            ledger.fixture_id,
            "review and lineage IDs join",
        ),
        (
            "operation-cardinality",
            all(
                sum(case.operation_id == node.operation_id for case in fixture.cases) == 4
                for node in plan.nodes
            ),
            len(fixture.cases),
            64,
            "four cases per operation",
        ),
        (
            "ledger-cardinality",
            len(ledger.events) == len(evaluation.receipts),
            len(ledger.events),
            len(evaluation.receipts),
            "lineage covers every receipt",
        ),
        (
            "address-coverage",
            all(case.content_address.startswith("sha256:") for case in fixture.cases),
            len(fixture.cases),
            64,
            "case declarations are addressed",
        ),
    )
    return tuple(_check(*value) for value in values)


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.INVARIANT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.INVARIANT,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-invariant"),
    )


__all__ = ["check_atlas_architecture_invariants"]
