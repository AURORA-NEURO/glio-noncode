"""Deterministic resource budgets for fixture replay and review exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBudget:
    budget_id: str
    operation: str
    max_records: int
    max_work_units: int
    max_payload_fields: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBudgetObservation:
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
class LinkGraphFoundationFrontierPerformanceReport:
    fixture_id: str
    budgets: tuple[LinkGraphFoundationFrontierBudget, ...]
    observations: tuple[LinkGraphFoundationFrontierBudgetObservation, ...]
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


def default_link_graph_foundation_frontier_budgets() -> tuple[LinkGraphFoundationFrontierBudget, ...]:
    return tuple(LinkGraphFoundationFrontierBudget(f"budget-{operation.value}", operation.value, 4, 64, 32) for operation in LinkGraphFoundationFrontierOperation)


def evaluate_link_graph_foundation_frontier_performance(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierPerformanceReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    budgets = default_link_graph_foundation_frontier_budgets()
    observations = []
    for budget in budgets:
        rows = replay.by_operation(budget.operation)
        record_count = len(rows)
        work_units = sum(3 + len(row.adapter.evidence_ids) + len(row.adapter.issue_codes) + int(row.adapter.measurements.get("link_count", row.adapter.measurements.get("element_count", 0))) for row in rows)
        payload_fields = sum(len(record.payload) for record in value.operation_records(budget.operation))
        observations.append(LinkGraphFoundationFrontierBudgetObservation(budget.budget_id, record_count, work_units, payload_fields, record_count <= budget.max_records, work_units <= budget.max_work_units, payload_fields <= budget.max_payload_fields))
    values = tuple(observations)
    return LinkGraphFoundationFrontierPerformanceReport(value.fixture_id, budgets, values, bool(values) and all(item.accepted for item in values))


def performance_summary(report: LinkGraphFoundationFrontierPerformanceReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "budget_count": len(report.budgets), "observation_count": len(report.observations), "work_units": sum(item.work_units for item in report.observations), "payload_fields": sum(item.payload_fields for item in report.observations), "accepted": report.accepted}


__all__ = ["LinkGraphFoundationFrontierBudget", "LinkGraphFoundationFrontierBudgetObservation", "LinkGraphFoundationFrontierPerformanceReport", "default_link_graph_foundation_frontier_budgets", "evaluate_link_graph_foundation_frontier_performance", "performance_summary"]
