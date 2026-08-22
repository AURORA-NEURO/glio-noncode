"""Canonical normalization for beta frontier record fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierRecord, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierNormalizedRecord:
    record_id: str
    operation: str
    role: str
    context_key: str
    source_ids: tuple[str, ...]
    payload_keys: tuple[str, ...]
    expected_state: str
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierNormalizationReport:
    fixture_id: str
    records: tuple[LinkGraphBetaFrontierNormalizedRecord, ...]
    unique_record_ids: bool
    stable_order: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def record(self, record_id: str) -> LinkGraphBetaFrontierNormalizedRecord:
        return next(item for item in self.records if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "records": [item.to_dict() for item in self.records], "unique_record_ids": self.unique_record_ids, "stable_order": self.stable_order, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def normalize_link_graph_beta_frontier_record(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierNormalizedRecord:
    payload: Mapping[str, Any] = record.payload
    return LinkGraphBetaFrontierNormalizedRecord(record.record_id, record.operation.value, record.role.value, record.context_key, tuple(sorted(record.source_ids)), tuple(sorted(str(key) for key in payload)), record.expected_state, tuple(sorted(record.expected_issue_codes)), record.content_address)


def normalize_link_graph_beta_frontier_fixture(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierNormalizationReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    records = tuple(normalize_link_graph_beta_frontier_record(record) for record in value.records)
    ids = tuple(record.record_id for record in records)
    return LinkGraphBetaFrontierNormalizationReport(value.fixture_id, records, len(ids) == len(set(ids)), ids == tuple(record.record_id for record in value.records), bool(records) and len(ids) == len(set(ids)))


def normalization_summary(report: LinkGraphBetaFrontierNormalizationReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "record_count": len(report.records), "unique_record_ids": report.unique_record_ids, "stable_order": report.stable_order, "accepted": report.accepted}


__all__ = ["LinkGraphBetaFrontierNormalizedRecord", "LinkGraphBetaFrontierNormalizationReport", "normalization_summary", "normalize_link_graph_beta_frontier_fixture", "normalize_link_graph_beta_frontier_record"]
