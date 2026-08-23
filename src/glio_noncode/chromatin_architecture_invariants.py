"""Cross-surface invariants for the D07 aggregate."""

from __future__ import annotations

from .chromatin_architecture_contracts import (
    ChromatinArchitectureCheck,
    ChromatinArchitectureCheckKind,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    addressed,
)


def check_chromatin_architecture_invariants(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> tuple[ChromatinArchitectureCheck, ...]:
    source_ids = {item.source_id for item in fixture.sources}
    cases_by_operation = {item.operation_id: 0 for item in fixture.operations}
    for case in fixture.cases:
        cases_by_operation[case.operation_id] += 1
    checks_data = (
        (
            "operation-case-cardinality",
            set(cases_by_operation.values()) == {4},
            cases_by_operation,
            4,
            "each operation has four cases",
        ),
        (
            "operation-receipt-cardinality",
            len(evaluation.receipts) == len(fixture.cases),
            len(evaluation.receipts),
            len(fixture.cases),
            "each case has one receipt",
        ),
        (
            "source-join-closure",
            all(set(case.source_ids) <= source_ids for case in fixture.cases),
            all(set(case.source_ids) <= source_ids for case in fixture.cases),
            True,
            "all case sources exist",
        ),
        (
            "positive-receipts",
            sum(item.expected_state.value == "accepted" for item in evaluation.receipts) == 16,
            sum(item.expected_state.value == "accepted" for item in evaluation.receipts),
            16,
            "one positive receipt per operation",
        ),
        (
            "control-receipts",
            sum(item.expected_state.value == "review" for item in evaluation.receipts) == 48,
            sum(item.expected_state.value == "review" for item in evaluation.receipts),
            48,
            "three control receipts per operation",
        ),
        (
            "control-not-publishable",
            all(
                item.observed_state.value == "review"
                for item in evaluation.receipts
                if item.expected_state.value == "review"
            ),
            all(
                item.observed_state.value == "review"
                for item in evaluation.receipts
                if item.expected_state.value == "review"
            ),
            True,
            "controls remain review-held",
        ),
        (
            "address-closure",
            all(item.content_address.startswith("sha256:") for item in evaluation.receipts),
            all(item.content_address.startswith("sha256:") for item in evaluation.receipts),
            True,
            "receipts are addressed",
        ),
        (
            "context-closure",
            fixture.context_key == evaluation.context_key,
            fixture.context_key,
            evaluation.context_key,
            "evaluation preserves aggregate context",
        ),
    )
    checks: list[ChromatinArchitectureCheck] = []
    for check_id, passed, observed, required, detail in checks_data:
        body = {
            "check_id": check_id,
            "passed": passed,
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        checks.append(
            ChromatinArchitectureCheck(
                check_id,
                ChromatinArchitectureCheckKind.INVARIANT,
                passed,
                observed,
                required,
                detail,
                addressed(body, "chromatin-invariant"),
            )
        )
    return tuple(checks)


__all__ = ["check_chromatin_architecture_invariants"]
