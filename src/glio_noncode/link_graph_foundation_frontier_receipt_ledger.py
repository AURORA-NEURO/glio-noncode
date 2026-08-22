"""Receipt ledger and source-to-record coverage for aggregate link inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierSource, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReceiptEntry:
    source_id: str
    source_kind: str
    source_version: str
    uri: str
    checksum: str
    record_count: int
    operation_count: int
    covered_record_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return bool(self.source_id and self.checksum and self.uri.startswith("https://") and self.record_count == len(self.covered_record_ids))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReceiptLedger:
    fixture_id: str
    entries: tuple[LinkGraphFoundationFrontierReceiptEntry, ...]
    covered_record_count: int
    uncovered_record_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def source_count(self) -> int:
        return len(self.entries)

    def entry(self, source_id: str) -> LinkGraphFoundationFrontierReceiptEntry:
        return next(item for item in self.entries if item.source_id == source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "entries": [item.to_dict() for item in self.entries], "covered_record_count": self.covered_record_count, "uncovered_record_ids": self.uncovered_record_ids, "source_count": self.source_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _entry(source: LinkGraphFoundationFrontierSource, fixture: LinkGraphFoundationFrontierFixture) -> LinkGraphFoundationFrontierReceiptEntry:
    records = tuple(record for record in fixture.records if source.source_id in record.source_ids)
    return LinkGraphFoundationFrontierReceiptEntry(source.source_id, source.source_kind, source.source_version, source.uri, source.checksum, len(records), len({record.operation.value for record in records}), tuple(record.record_id for record in records))


def build_link_graph_foundation_frontier_receipt_ledger(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierReceiptLedger:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    entries = tuple(_entry(source, value) for source in value.sources)
    covered = {record_id for entry in entries for record_id in entry.covered_record_ids}
    all_ids = {record.record_id for record in value.records}
    uncovered = tuple(sorted(all_ids - covered))
    return LinkGraphFoundationFrontierReceiptLedger(value.fixture_id, entries, len(covered), uncovered, bool(entries) and all(entry.complete for entry in entries) and not uncovered)


def receipt_coverage_by_operation(ledger: LinkGraphFoundationFrontierReceiptLedger, fixture: LinkGraphFoundationFrontierFixture) -> dict[str, int]:
    return {operation: sum(1 for record in fixture.records if operation == record.operation.value and any(record.record_id in entry.covered_record_ids for entry in ledger.entries)) for operation in sorted({record.operation.value for record in fixture.records})}


__all__ = ["LinkGraphFoundationFrontierReceiptEntry", "LinkGraphFoundationFrontierReceiptLedger", "build_link_graph_foundation_frontier_receipt_ledger", "receipt_coverage_by_operation"]
