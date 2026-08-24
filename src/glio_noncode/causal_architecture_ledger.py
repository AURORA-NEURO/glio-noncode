"""D11 deterministic evidence ledger."""

from __future__ import annotations

from .causal_architecture_contracts import (
    CausalArchitectureEvaluation,
    CausalArchitectureFixture,
    CausalArchitectureLedger,
    addressed,
)


def build_causal_architecture_ledger(
    fixture: CausalArchitectureFixture, evaluation: CausalArchitectureEvaluation
) -> CausalArchitectureLedger:
    events = tuple(
        {
            "event_id": f"D11-LEDGER-{index:03d}",
            "case_id": item.case_id,
            "operation_id": item.operation_id,
            "state": item.observed_state.value,
            "result_state": item.observed_result_state,
            "issue_codes": item.observed_issue_codes,
            "output_address": item.output_address,
        }
        for index, item in enumerate(evaluation.receipts, start=1)
    )
    return CausalArchitectureLedger(fixture.fixture_id, events, addressed(events, "causal-ledger"))


def causal_architecture_ledger_is_closed(ledger: CausalArchitectureLedger) -> bool:
    return (
        len(ledger.events) == 64
        and len({item["case_id"] for item in ledger.events}) == 64
        and all(str(item["output_address"]).startswith("sha256:") for item in ledger.events)
    )


__all__ = ["build_causal_architecture_ledger", "causal_architecture_ledger_is_closed"]
