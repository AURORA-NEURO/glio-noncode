"""Source receipt coverage ledger for beta frontier records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierSource, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReceiptEntry:
    source_id: str
    source_kind: str
    source_version: str
    uri: str
    checksum: str
    record_count: int
    covered_record_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return self.uri.startswith("https://") and self.checksum.startswith("sha256:") and self.record_count == len(self.covered_record_ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReceiptLedger:
    fixture_id: str
    entries: tuple[LinkGraphBetaFrontierReceiptEntry, ...]
    covered_record_count: int
    uncovered_record_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def entry(self, source_id: str) -> LinkGraphBetaFrontierReceiptEntry:
        return next(item for item in self.entries if item.source_id == source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "entries": [item.to_dict() for item in self.entries], "covered_record_count": self.covered_record_count, "uncovered_record_ids": self.uncovered_record_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_receipt_ledger(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierReceiptLedger:
    value = fixture or default_link_graph_beta_frontier_fixture()
    entries = tuple(LinkGraphBetaFrontierReceiptEntry(source.source_id, source.source_kind, source.source_version, source.uri, source.checksum, sum(source.source_id in record.source_ids for record in value.records), tuple(record.record_id for record in value.records if source.source_id in record.source_ids)) for source in value.sources)
    covered = {record_id for entry in entries for record_id in entry.covered_record_ids}
    all_ids = {record.record_id for record in value.records}
    return LinkGraphBetaFrontierReceiptLedger(value.fixture_id, entries, len(covered), tuple(sorted(all_ids - covered)), bool(entries) and all(entry.complete for entry in entries) and not (all_ids - covered))


def receipt_coverage_by_operation(ledger: LinkGraphBetaFrontierReceiptLedger, fixture: LinkGraphBetaFrontierFixture) -> dict[str, int]:
    return {operation: sum(any(record.record_id in entry.covered_record_ids for entry in ledger.entries) for record in fixture.records if record.operation.value == operation) for operation in sorted({record.operation.value for record in fixture.records})}


__all__ = ["LinkGraphBetaFrontierReceiptEntry", "LinkGraphBetaFrontierReceiptLedger", "build_link_graph_beta_frontier_receipt_ledger", "receipt_coverage_by_operation"]
