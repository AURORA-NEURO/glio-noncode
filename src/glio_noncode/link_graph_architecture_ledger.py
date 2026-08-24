"""Deterministic D10 receipt ledger."""

from __future__ import annotations

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureFixture,
    LinkGraphArchitectureLedger,
    addressed,
)


def build_link_graph_architecture_ledger(
    fixture: LinkGraphArchitectureFixture, evaluation: LinkGraphArchitectureEvaluation
) -> LinkGraphArchitectureLedger:
    events = tuple(
        {
            "event_id": f"D10-LEDGER-{index:03d}",
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "state": receipt.observed_state.value,
            "result_state": receipt.observed_result_state,
            "issue_codes": receipt.observed_issue_codes,
            "output_address": receipt.output_address,
        }
        for index, receipt in enumerate(evaluation.receipts, start=1)
    )
    return LinkGraphArchitectureLedger(fixture.fixture_id, events, addressed(events, "link-ledger"))


def link_graph_architecture_ledger_is_closed(ledger: LinkGraphArchitectureLedger) -> bool:
    return (
        len(ledger.events) == 64
        and len({item["case_id"] for item in ledger.events}) == 64
        and all(str(item["output_address"]).startswith("sha256:") for item in ledger.events)
    )


__all__ = ["build_link_graph_architecture_ledger", "link_graph_architecture_ledger_is_closed"]
