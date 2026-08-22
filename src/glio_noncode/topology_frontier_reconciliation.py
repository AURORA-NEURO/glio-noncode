"""Expected-versus-observed state reconciliation for Domain 09."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_public_data import TopologyFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyFrontierReconciliationItem:
    record_id: str
    operation: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_floor_match: bool
    source_ids: tuple[str, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state_match and self.issue_floor_match and bool(self.source_ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


@dataclass(frozen=True, slots=True)
class TopologyFrontierReconciliationReport:
    fixture_id: str
    items: tuple[TopologyFrontierReconciliationItem, ...]
    global_checks: tuple[tuple[str, bool, str], ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.items) and all(item.passed for item in self.items) and all(item[1] for item in self.global_checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        rows = [f"{item.record_id}:reconciliation" for item in self.items if not item.passed]
        rows.extend(item[0] for item in self.global_checks if not item[1])
        return tuple(rows)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def reconcile_topology_frontier(
    fixture: TopologyFrontierFixture,
    evaluation: TopologyFrontierEvaluationReport,
) -> TopologyFrontierReconciliationReport:
    records = fixture.record_map()
    items: list[TopologyFrontierReconciliationItem] = []
    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        body = {
            "record_id": receipt.record_id,
            "operation": receipt.operation.value,
            "expected_state": record.expected_state,
            "observed_state": receipt.adapter_state,
            "expected_issue_codes": record.expected_issue_codes,
            "observed_issue_codes": receipt.observed_issue_codes,
            "state_match": record.expected_state == receipt.adapter_state,
            "issue_floor_match": set(record.expected_issue_codes) <= set(receipt.observed_issue_codes),
            "source_ids": record.source_ids,
        }
        items.append(TopologyFrontierReconciliationItem(**body, content_address=content_hash(body)))
    global_checks = (
        ("record-closure", {item.record_id for item in items} == set(records), "every fixture record has a receipt"),
        ("source-closure", all(source_id in fixture.source_map() for item in items for source_id in item.source_ids), "every receipt source resolves"),
        ("operation-closure", {item.operation for item in items} == {item.operation.value for item in fixture.records}, "every operation is represented"),
    )
    body = {"fixture_id": fixture.fixture_id, "items": items, "global_checks": global_checks}
    return TopologyFrontierReconciliationReport(fixture.fixture_id, tuple(items), global_checks, content_hash(body))


__all__ = [
    "TopologyFrontierReconciliationItem",
    "TopologyFrontierReconciliationReport",
    "reconcile_topology_frontier",
]
