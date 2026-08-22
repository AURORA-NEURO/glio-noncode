"""Canonical normalization for public aggregate link records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierRecord, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierNormalizedRecord:
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
class LinkGraphFoundationFrontierNormalizationReport:
    fixture_id: str
    records: tuple[LinkGraphFoundationFrontierNormalizedRecord, ...]
    unique_record_ids: bool
    stable_order: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def record(self, record_id: str) -> LinkGraphFoundationFrontierNormalizedRecord:
        return next(item for item in self.records if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "records": [item.to_dict() for item in self.records], "unique_record_ids": self.unique_record_ids, "stable_order": self.stable_order, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def normalize_link_graph_foundation_frontier_record(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierNormalizedRecord:
    payload: Mapping[str, Any] = record.payload
    return LinkGraphFoundationFrontierNormalizedRecord(record.record_id, record.operation.value, record.role.value, record.context_key, tuple(sorted(record.source_ids)), tuple(sorted(str(key) for key in payload)), record.expected_state, tuple(sorted(record.expected_issue_codes)), record.content_address)


def normalize_link_graph_foundation_frontier_fixture(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierNormalizationReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    records = tuple(normalize_link_graph_foundation_frontier_record(record) for record in value.records)
    ids = tuple(item.record_id for item in records)
    unique = len(ids) == len(set(ids))
    stable = ids == tuple(record.record_id for record in value.records)
    return LinkGraphFoundationFrontierNormalizationReport(value.fixture_id, records, unique, stable, bool(records) and unique and stable)


def normalization_summary(report: LinkGraphFoundationFrontierNormalizationReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "record_count": len(report.records), "unique_record_ids": report.unique_record_ids, "stable_order": report.stable_order, "source_id_count": len({source_id for item in report.records for source_id in item.source_ids},), "accepted": report.accepted}


__all__ = ["LinkGraphFoundationFrontierNormalizedRecord", "LinkGraphFoundationFrontierNormalizationReport", "normalization_summary", "normalize_link_graph_foundation_frontier_fixture", "normalize_link_graph_foundation_frontier_record"]
