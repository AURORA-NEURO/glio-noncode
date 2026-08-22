"""Safe fixture mutation helpers for testing explicit review behavior."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .serialization import content_hash
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, TopologyAlphaFrontierRecord, default_topology_alpha_frontier_fixture


def _replace_record(fixture: TopologyAlphaFrontierFixture, record: TopologyAlphaFrontierRecord) -> TopologyAlphaFrontierFixture:
    records = tuple(record if item.record_id == record.record_id else item for item in fixture.records)
    return replace(fixture, records=records, content_address=content_hash({"fixture_id": fixture.fixture_id, "version": fixture.version, "sources": fixture.sources, "records": records}))


def mutate_topology_alpha_frontier_expected_state(fixture: TopologyAlphaFrontierFixture | None = None, *, record_id: str = "D09-C09-P", expected_state: str = "partial") -> TopologyAlphaFrontierFixture:
    value = fixture or default_topology_alpha_frontier_fixture()
    record = next(item for item in value.records if item.record_id == record_id)
    return _replace_record(value, replace(record, expected_state=expected_state, content_address=content_hash({**record.to_dict(False), "expected_state": expected_state})))


def mutate_topology_alpha_frontier_issue_floor(fixture: TopologyAlphaFrontierFixture | None = None, *, record_id: str = "D09-C10-C2", issue_code: str = "synthetic_review_code") -> TopologyAlphaFrontierFixture:
    value = fixture or default_topology_alpha_frontier_fixture()
    record = next(item for item in value.records if item.record_id == record_id)
    issues = tuple(dict.fromkeys((*record.expected_issue_codes, issue_code)))
    return _replace_record(value, replace(record, expected_issue_codes=issues, content_address=content_hash({**record.to_dict(False), "expected_issue_codes": issues})))


def mutate_topology_alpha_frontier_context(fixture: TopologyAlphaFrontierFixture | None = None, *, record_id: str = "D09-C12-P", context_key: str = "GRCh38|glioma|pediatric|stem_like|tumor|unknown") -> TopologyAlphaFrontierFixture:
    value = fixture or default_topology_alpha_frontier_fixture()
    record = next(item for item in value.records if item.record_id == record_id)
    payload = dict(record.payload)
    for key in ("records", "contacts", "events"):
        if key in payload:
            payload[key] = tuple({**row, "context_key": context_key} for row in payload[key])
    payload["target_context_key"] = context_key
    return _replace_record(value, replace(record, context_key=context_key, payload=payload, content_address=content_hash({**record.to_dict(False), "context_key": context_key, "payload": payload})))


def summarize_topology_alpha_frontier_mutation(fixture: TopologyAlphaFrontierFixture) -> dict[str, Any]:
    return {"fixture_id": fixture.fixture_id, "content_address": fixture.content_address, "record_count": len(fixture.records), "source_count": len(fixture.sources), "record_addresses": {item.record_id: item.content_address for item in fixture.records}}


__all__ = ["mutate_topology_alpha_frontier_context", "mutate_topology_alpha_frontier_expected_state", "mutate_topology_alpha_frontier_issue_floor", "summarize_topology_alpha_frontier_mutation"]
