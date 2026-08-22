"""Closed public aggregate fixture for Domain 09 C05-C08."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .topology_context import TopologyState

TOPOLOGY_BETA_FRONTIER_FIXTURE_VERSION = "2026.08.d09-c05-c08.v1"
TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|unknown"
TOPOLOGY_BETA_FRONTIER_FOREIGN_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|unknown"
TOPOLOGY_BETA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
TOPOLOGY_BETA_FRONTIER_POSITIVE_COUNT = 4
TOPOLOGY_BETA_FRONTIER_CONTROL_COUNT = 12
TOPOLOGY_BETA_FRONTIER_SOURCE_COUNT = 4


class TopologyBetaFrontierOperation(StrEnum):
    LOOP_STRIPE = "loop_stripe"
    PROMOTER_CAPTURE = "promoter_capture"
    ENHANCER_PROMOTER_CONTACT = "enhancer_promoter_contact"
    ACTIVITY_BY_CONTACT = "activity_by_contact"


class TopologyBetaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierSource:
    source_id: str
    source_kind: str
    source_version: str
    uri: str
    checksum: str
    context_key: str
    public_aggregate: bool = True
    receipt_fields: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("source_id", "source_kind", "source_version", "uri", "checksum", "context_key"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.public_aggregate:
            raise ValidationError("topology beta frontier sources must be public aggregates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierRecord:
    record_id: str
    operation: TopologyBetaFrontierOperation
    role: TopologyBetaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...] = ()
    expected_measurements: Mapping[str, Any] = field(default_factory=dict)
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("topology beta frontier records need source receipts")
        if self.expected_state not in {item.value for item in TopologyState}:
            raise ValidationError(f"unknown expected topology state: {self.expected_state}")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "record_id": self.record_id,
            "operation": self.operation,
            "role": self.role,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "payload": dict(self.payload),
            "expected_state": self.expected_state,
            "expected_issue_codes": self.expected_issue_codes,
            "expected_measurements": dict(self.expected_measurements),
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierFixture:
    fixture_id: str
    version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[TopologyBetaFrontierSource, ...]
    records: tuple[TopologyBetaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.version, "fixture version")
        require_non_empty(self.context_key, "fixture context key")
        require_non_empty(self.foreign_context_key, "fixture foreign context key")
        require_non_empty(self.boundary, "fixture boundary")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"fixture_id": self.fixture_id, "version": self.version, "sources": self.sources, "records": self.records}),
            )

    @property
    def positive_records(self) -> tuple[TopologyBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is TopologyBetaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[TopologyBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is TopologyBetaFrontierRole.CONTROL)

    def operation_records(self, operation: TopologyBetaFrontierOperation | str) -> tuple[TopologyBetaFrontierRecord, ...]:
        value = TopologyBetaFrontierOperation(str(operation))
        return tuple(item for item in self.records if item.operation is value)

    def source(self, source_id: str) -> TopologyBetaFrontierSource:
        for item in self.sources:
            if item.source_id == source_id:
                return item
        raise KeyError(source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "context_key": self.context_key,
            "foreign_context_key": self.foreign_context_key,
            "boundary": self.boundary,
            "sources": [item.to_dict() for item in self.sources],
            "records": [item.to_dict() for item in self.records],
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierDataAudit:
    fixture_id: str
    accepted: bool
    checks: tuple[str, ...]
    record_count: int
    source_count: int
    positive_count: int
    control_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "accepted": self.accepted,
            "checks": self.checks,
            "record_count": self.record_count,
            "source_count": self.source_count,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def _source(source_id: str, kind: str, version: str, uri: str) -> TopologyBetaFrontierSource:
    return TopologyBetaFrontierSource(
        source_id,
        kind,
        version,
        uri,
        content_hash({"source_id": source_id, "version": version, "uri": uri}),
        TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY,
        receipt_fields={"scope": "aggregate", "access": "public", "schema": "locked"},
    )


def _loop_payload(context_key: str, *, count: int = 1, signal: float = 7.0, metadata: bool = True) -> dict[str, Any]:
    rows = []
    for index in range(count):
        row = {
            "feature_id": f"loop-{index + 1}",
            "feature_kind": "stripe" if index else "loop",
            "chromosome_a": "7",
            "start_a": 100 + index * 100,
            "end_a": 120 + index * 100,
            "chromosome_b": "7",
            "start_b": 300 + index * 100,
            "end_b": 320 + index * 100,
            "signal": signal + index * 7.0,
            "context_key": context_key,
            "source_version": "loop-v4",
        }
        if metadata:
            row.update({"resolution": 5000, "replicate_id": f"r{index + 1}", "caller": "loop-caller"})
        rows.append(row)
    return {"features": rows, "target_context_key": TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY, "public_aggregate": True}


def _promoter_payload(context_key: str, *, count: int = 1, signal: float = 6.0, bait: bool = True) -> dict[str, Any]:
    rows = []
    for index in range(count):
        row = {
            "contact_id": f"pc-{index + 1}",
            "promoter_id": "GENE1",
            "target_element_id": "enh-1",
            "promoter_chromosome": "7",
            "promoter_start": 100,
            "promoter_end": 120,
            "target_chromosome": "7",
            "target_start": 300 + index * 100,
            "target_end": 320 + index * 100,
            "signal": signal + index * 7.0,
            "context_key": context_key,
            "source_version": "pc-v3",
            "resolution": 5000,
            "replicate_id": f"r{index + 1}",
        }
        if bait:
            row["bait_id"] = f"bait-{index + 1}"
        rows.append(row)
    return {"contacts": rows, "target_context_key": TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY, "public_aggregate": True}


def _contact_observation(context_key: str, signal: float, index: int) -> dict[str, Any]:
    return {
        "contact_id": f"contact-{index}",
        "enhancer_id": "enh-1",
        "promoter_id": "GENE1",
        "signal": signal,
        "context_key": context_key,
        "source_id": "enhancer-contact-aggregate",
        "source_version": "epc-v2",
        "raw_hash": content_hash({"index": index, "context": context_key, "signal": signal}),
        "replicate_id": f"r{index}",
    }


def _activity_observation(context_key: str, signal: float, index: int) -> dict[str, Any]:
    return {
        "enhancer_id": "enh-1",
        "activity_signal": signal,
        "context_key": context_key,
        "source_id": "enhancer-activity-aggregate",
        "source_version": "activity-v5",
        "raw_hash": content_hash({"index": index, "context": context_key, "signal": signal}),
        "replicate_id": f"r{index}",
        "assay": "accessibility_activity",
    }


def _records() -> tuple[TopologyBetaFrontierRecord, ...]:
    c = TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY
    f = TOPOLOGY_BETA_FRONTIER_FOREIGN_CONTEXT_KEY
    return (
        TopologyBetaFrontierRecord("D09-C05-P", TopologyBetaFrontierOperation.LOOP_STRIPE, TopologyBetaFrontierRole.POSITIVE, c, ("loop-stripe-aggregate",), _loop_payload(c), "supported", expected_measurements={"observation_count": 1}),
        TopologyBetaFrontierRecord("D09-C05-C1", TopologyBetaFrontierOperation.LOOP_STRIPE, TopologyBetaFrontierRole.CONTROL, c, ("loop-stripe-aggregate",), _loop_payload(c, metadata=False), "partial", ("missing_loop_metadata",), {"observation_count": 1}),
        TopologyBetaFrontierRecord("D09-C05-C2", TopologyBetaFrontierOperation.LOOP_STRIPE, TopologyBetaFrontierRole.CONTROL, c, ("loop-stripe-aggregate",), _loop_payload(c, count=2, signal=2.0), "ambiguous", ("replicate_disagreement",), {"observation_count": 2}),
        TopologyBetaFrontierRecord("D09-C05-C3", TopologyBetaFrontierOperation.LOOP_STRIPE, TopologyBetaFrontierRole.CONTROL, f, ("loop-stripe-aggregate",), _loop_payload(f), "out_of_domain", ("context_mismatch",), {"observation_count": 1}),
        TopologyBetaFrontierRecord("D09-C06-P", TopologyBetaFrontierOperation.PROMOTER_CAPTURE, TopologyBetaFrontierRole.POSITIVE, c, ("promoter-capture-aggregate",), _promoter_payload(c), "supported", expected_measurements={"contact_count": 1}),
        TopologyBetaFrontierRecord("D09-C06-C1", TopologyBetaFrontierOperation.PROMOTER_CAPTURE, TopologyBetaFrontierRole.CONTROL, c, ("promoter-capture-aggregate",), _promoter_payload(c, bait=False), "partial", ("missing_bait_id",), {"contact_count": 1}),
        TopologyBetaFrontierRecord("D09-C06-C2", TopologyBetaFrontierOperation.PROMOTER_CAPTURE, TopologyBetaFrontierRole.CONTROL, c, ("promoter-capture-aggregate",), _promoter_payload(c, count=2, signal=2.0), "ambiguous", ("replicate_disagreement",), {"contact_count": 2}),
        TopologyBetaFrontierRecord("D09-C06-C3", TopologyBetaFrontierOperation.PROMOTER_CAPTURE, TopologyBetaFrontierRole.CONTROL, f, ("promoter-capture-aggregate",), _promoter_payload(f), "out_of_domain", ("context_mismatch",), {"contact_count": 1}),
        TopologyBetaFrontierRecord("D09-C07-P", TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, TopologyBetaFrontierRole.POSITIVE, c, ("enhancer-contact-aggregate",), {"observations": [_contact_observation(c, 6.0, 1)], "enhancer_id": "enh-1", "promoter_id": "GENE1", "target_context_key": c, "public_aggregate": True}, "supported", expected_measurements={"observation_count": 1}),
        TopologyBetaFrontierRecord("D09-C07-C1", TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, TopologyBetaFrontierRole.CONTROL, c, ("enhancer-contact-aggregate",), {"observations": [_contact_observation(c, 1.0, 1), _contact_observation(c, 9.0, 2)], "enhancer_id": "enh-1", "promoter_id": "GENE1", "target_context_key": c, "public_aggregate": True}, "ambiguous", ("replicate_disagreement",), {"observation_count": 2}),
        TopologyBetaFrontierRecord("D09-C07-C2", TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, TopologyBetaFrontierRole.CONTROL, f, ("enhancer-contact-aggregate",), {"observations": [_contact_observation(f, 6.0, 1)], "enhancer_id": "enh-1", "promoter_id": "GENE1", "target_context_key": f, "public_aggregate": True}, "out_of_domain", ("context_mismatch",), {"observation_count": 1}),
        TopologyBetaFrontierRecord("D09-C07-C3", TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, TopologyBetaFrontierRole.CONTROL, c, ("enhancer-contact-aggregate",), {"observations": [], "enhancer_id": "enh-1", "promoter_id": "GENE1", "target_context_key": c, "public_aggregate": True}, "absent", ("no_contact_observations",), {"observation_count": 0}),
        TopologyBetaFrontierRecord("D09-C08-P", TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, TopologyBetaFrontierRole.POSITIVE, c, ("enhancer-contact-aggregate", "enhancer-activity-aggregate"), {"contacts": [_contact_observation(c, 6.0, 1)], "activities": [_activity_observation(c, 0.8, 1)], "enhancer_id": "enh-1", "promoter_id": "GENE1", "model_id": "abc-aggregate", "model_version": "2026.08", "target_context_key": c, "public_aggregate": True}, "supported"),
        TopologyBetaFrontierRecord("D09-C08-C1", TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, TopologyBetaFrontierRole.CONTROL, c, ("enhancer-contact-aggregate", "enhancer-activity-aggregate"), {"contacts": [_contact_observation(c, 6.0, 1)], "activities": [], "enhancer_id": "enh-1", "promoter_id": "GENE1", "model_id": "abc-aggregate", "model_version": "2026.08", "target_context_key": c, "public_aggregate": True}, "abstained", ("missing_activity",), {"activity_count": 0}),
        TopologyBetaFrontierRecord("D09-C08-C2", TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, TopologyBetaFrontierRole.CONTROL, c, ("enhancer-contact-aggregate", "enhancer-activity-aggregate"), {"contacts": [_contact_observation(c, 1.0, 1), _contact_observation(c, 9.0, 2)], "activities": [_activity_observation(c, 0.1, 1), _activity_observation(c, 0.9, 2)], "enhancer_id": "enh-1", "promoter_id": "GENE1", "model_id": "abc-aggregate", "model_version": "2026.08", "target_context_key": c, "public_aggregate": True}, "ambiguous", ("component_disagreement",), {"contact_count": 2, "activity_count": 2}),
        TopologyBetaFrontierRecord("D09-C08-C3", TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, TopologyBetaFrontierRole.CONTROL, f, ("enhancer-contact-aggregate", "enhancer-activity-aggregate"), {"contacts": [_contact_observation(f, 6.0, 1)], "activities": [_activity_observation(f, 0.8, 1)], "enhancer_id": "enh-1", "promoter_id": "GENE1", "model_id": "abc-aggregate", "model_version": "2026.08", "target_context_key": f, "public_aggregate": True}, "out_of_domain", ("context_mismatch",), {"contact_count": 1, "activity_count": 1}),
    )


def default_topology_beta_frontier_fixture() -> TopologyBetaFrontierFixture:
    return TopologyBetaFrontierFixture(
        "topology-beta-frontier-fixture",
        TOPOLOGY_BETA_FRONTIER_FIXTURE_VERSION,
        TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY,
        TOPOLOGY_BETA_FRONTIER_FOREIGN_CONTEXT_KEY,
        TOPOLOGY_BETA_FRONTIER_BOUNDARY,
        (
            _source("loop-stripe-aggregate", "loop_stripe_aggregate", "loop-v4", "https://data.example.org/topology/loop-stripe-v4"),
            _source("promoter-capture-aggregate", "promoter_capture_aggregate", "pc-v3", "https://data.example.org/topology/promoter-capture-v3"),
            _source("enhancer-contact-aggregate", "enhancer_contact_aggregate", "epc-v2", "https://data.example.org/topology/enhancer-contact-v2"),
            _source("enhancer-activity-aggregate", "enhancer_activity_aggregate", "activity-v5", "https://data.example.org/topology/enhancer-activity-v5"),
        ),
        _records(),
    )


def audit_topology_beta_frontier_data(fixture: TopologyBetaFrontierFixture) -> TopologyBetaFrontierDataAudit:
    checks: list[str] = []
    checks.append("record_count" if len(fixture.records) == 16 else "record_count_failed")
    checks.append("source_count" if len(fixture.sources) == 4 else "source_count_failed")
    checks.append("operation_balance" if all(len(fixture.operation_records(item)) == 4 for item in TopologyBetaFrontierOperation) else "operation_balance_failed")
    checks.append("positive_balance" if len(fixture.positive_records) == 4 else "positive_balance_failed")
    checks.append("control_balance" if len(fixture.control_records) == 12 else "control_balance_failed")
    checks.append("aggregate_boundary" if fixture.boundary == TOPOLOGY_BETA_FRONTIER_BOUNDARY else "aggregate_boundary_failed")
    checks.append("source_receipts" if all(item.public_aggregate for item in fixture.sources) else "source_receipts_failed")
    checks.append("record_sources" if all(set(item.source_ids) <= {source.source_id for source in fixture.sources} for item in fixture.records) else "record_sources_failed")
    checks.append("context_closure" if all(item.context_key in {fixture.context_key, fixture.foreign_context_key} for item in fixture.records) else "context_closure_failed")
    accepted = all(not item.endswith("_failed") for item in checks)
    return TopologyBetaFrontierDataAudit(fixture.fixture_id, accepted, tuple(checks), len(fixture.records), len(fixture.sources), len(fixture.positive_records), len(fixture.control_records))


def fixture_json(fixture: TopologyBetaFrontierFixture | None = None) -> str:
    return json.dumps((fixture or default_topology_beta_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = [
    "TOPOLOGY_BETA_FRONTIER_BOUNDARY",
    "TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY",
    "TOPOLOGY_BETA_FRONTIER_CONTROL_COUNT",
    "TOPOLOGY_BETA_FRONTIER_FIXTURE_VERSION",
    "TOPOLOGY_BETA_FRONTIER_FOREIGN_CONTEXT_KEY",
    "TOPOLOGY_BETA_FRONTIER_POSITIVE_COUNT",
    "TOPOLOGY_BETA_FRONTIER_SOURCE_COUNT",
    "TopologyBetaFrontierDataAudit",
    "TopologyBetaFrontierFixture",
    "TopologyBetaFrontierOperation",
    "TopologyBetaFrontierRecord",
    "TopologyBetaFrontierRole",
    "TopologyBetaFrontierSource",
    "audit_topology_beta_frontier_data",
    "default_topology_beta_frontier_fixture",
    "fixture_json",
]
