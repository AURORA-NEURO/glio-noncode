"""Field-level validation receipts for beta frontier inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierFieldCheck:
    field: str
    present_count: int
    expected_count: int
    valid: bool
    rule: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierFieldValidationReport:
    fixture_id: str
    checks: tuple[LinkGraphBetaFrontierFieldCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_fields(self) -> tuple[str, ...]:
        return tuple(item.field for item in self.checks if not item.valid)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": [item.to_dict() for item in self.checks], "failed_fields": self.failed_fields, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def validate_link_graph_beta_frontier_fields(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierFieldValidationReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    expected = len(value.records)
    checks = (LinkGraphBetaFrontierFieldCheck("record_id", sum(bool(record.record_id) for record in value.records), expected, all(bool(record.record_id) for record in value.records), "non-empty record identity"), LinkGraphBetaFrontierFieldCheck("context_key", sum(bool(record.context_key) for record in value.records), expected, all(bool(record.context_key) for record in value.records), "declared aggregate context"), LinkGraphBetaFrontierFieldCheck("source_ids", sum(bool(record.source_ids) for record in value.records), expected, all(bool(record.source_ids) for record in value.records), "receipt required"), LinkGraphBetaFrontierFieldCheck("payload", sum(bool(record.payload) for record in value.records), expected, all(bool(record.payload) for record in value.records), "primitive input required"), LinkGraphBetaFrontierFieldCheck("content_address", sum(bool(record.content_address) for record in value.records), expected, all(bool(record.content_address) for record in value.records), "address required"))
    return LinkGraphBetaFrontierFieldValidationReport(value.fixture_id, checks, all(item.valid for item in checks))


__all__ = ["LinkGraphBetaFrontierFieldCheck", "LinkGraphBetaFrontierFieldValidationReport", "validate_link_graph_beta_frontier_fields"]
