"""Deterministic budgets for beta frontier parsing, replay, and export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierBudget:
    budget_id: str
    operation: str
    max_records: int
    max_work_units: int
    max_payload_fields: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierBudgetObservation:
    budget_id: str
    record_count: int
    work_units: int
    payload_fields: int
    record_ok: bool
    work_ok: bool
    payload_ok: bool

    @property
    def accepted(self) -> bool:
        return self.record_ok and self.work_ok and self.payload_ok

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierPerformanceReport:
    fixture_id: str
    budgets: tuple[LinkGraphBetaFrontierBudget, ...]
    observations: tuple[LinkGraphBetaFrontierBudgetObservation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_budgets(self) -> tuple[str, ...]:
        return tuple(item.budget_id for item in self.observations if not item.accepted)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "budgets": [item.to_dict() for item in self.budgets], "observations": [item.to_dict() for item in self.observations], "failed_budgets": self.failed_budgets, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_performance(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierPerformanceReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    budgets = tuple(LinkGraphBetaFrontierBudget(f"budget-{operation.value}", operation.value, 4, 64, 16) for operation in LinkGraphBetaFrontierOperation)
    observations = []
    for budget in budgets:
        rows = replay.by_operation(budget.operation)
        work = sum(3 + len(row.adapter.evidence_ids) + len(row.adapter.issue_codes) + int(row.adapter.measurements.get("observation_count", 0)) for row in rows)
        fields = sum(len(record.payload) for record in value.operation_records(budget.operation))
        observations.append(LinkGraphBetaFrontierBudgetObservation(budget.budget_id, len(rows), work, fields, len(rows) <= budget.max_records, work <= budget.max_work_units, fields <= budget.max_payload_fields))
    values = tuple(observations)
    return LinkGraphBetaFrontierPerformanceReport(value.fixture_id, budgets, values, bool(values) and all(item.accepted for item in values))


def performance_summary(report: LinkGraphBetaFrontierPerformanceReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "budget_count": len(report.budgets), "observation_count": len(report.observations), "work_units": sum(item.work_units for item in report.observations), "payload_fields": sum(item.payload_fields for item in report.observations), "accepted": report.accepted}


__all__ = ["LinkGraphBetaFrontierBudget", "LinkGraphBetaFrontierBudgetObservation", "LinkGraphBetaFrontierPerformanceReport", "evaluate_link_graph_beta_frontier_performance", "performance_summary"]
