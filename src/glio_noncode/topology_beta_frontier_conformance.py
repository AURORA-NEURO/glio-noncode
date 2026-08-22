"""Operation-specific conformance checks for locked aggregate fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierConformanceField:
    field_name: str
    field_type: str
    required: bool
    retention_rule: str
    missingness_rule: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierConformanceCheck:
    operation: str
    record_id: str
    required_fields: tuple[str, ...]
    present_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierConformanceReport:
    fields: dict[str, tuple[TopologyBetaFrontierConformanceField, ...]]
    checks: tuple[TopologyBetaFrontierConformanceCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyBetaFrontierConformanceCheck, ...]:
        return tuple(item for item in self.checks if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": {key: [item.to_dict() for item in items] for key, items in self.fields.items()}, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _field(name: str, field_type: str, rule: str, missing: str = "retain explicit missingness") -> TopologyBetaFrontierConformanceField:
    return TopologyBetaFrontierConformanceField(name, field_type, True, rule, missing)


def build_topology_beta_frontier_conformance(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierConformanceReport:
    fields = {
        "loop_stripe": (_field("feature_id", "string", "preserve feature identity"), _field("feature_kind", "enum", "preserve loop or stripe kind"), _field("chromosome_a", "string", "preserve anchor A"), _field("start_a", "integer", "normalize coordinate"), _field("end_a", "integer", "normalize coordinate"), _field("chromosome_b", "string", "preserve anchor B"), _field("start_b", "integer", "normalize coordinate"), _field("end_b", "integer", "normalize coordinate"), _field("signal", "number", "preserve measured signal"), _field("context_key", "string", "gate exact context"), _field("source_version", "string", "preserve source version")),
        "promoter_capture": (_field("contact_id", "string", "preserve contact identity"), _field("promoter_id", "string", "preserve promoter identity"), _field("target_element_id", "string", "preserve target identity"), _field("bait_id", "string", "preserve bait receipt"), _field("signal", "number", "preserve measured signal"), _field("context_key", "string", "gate exact context")),
        "enhancer_promoter_contact": (_field("enhancer_id", "string", "preserve enhancer identity"), _field("promoter_id", "string", "preserve promoter identity"), _field("signal", "number", "retain observation"), _field("context_key", "string", "gate exact context"), _field("source_version", "string", "preserve source version")),
        "activity_by_contact": (_field("enhancer_id", "string", "preserve enhancer identity"), _field("promoter_id", "string", "preserve promoter identity"), _field("model_id", "string", "preserve model receipt"), _field("model_version", "string", "preserve model version"), _field("context_key", "string", "gate exact context")),
    }
    def present_keys(row: Any, required: tuple[str, ...]) -> set[str]:
        payload = row.payload
        if row.operation.value == "loop_stripe":
            source = (payload.get("features") or [{}])[0]
        elif row.operation.value == "promoter_capture":
            source = (payload.get("contacts") or [{}])[0]
        elif row.operation.value == "enhancer_promoter_contact":
            source = (payload.get("observations") or [{}])[0]
        else:
            source = dict(payload)
            if payload.get("contacts"):
                source.update({key: value for key, value in payload["contacts"][0].items() if key not in source})
        return {key for key in required if key in source or key == "public_aggregate"}
    checks = []
    for row in fixture.records:
        required = tuple(item.field_name for item in fields[row.operation.value]) + ("public_aggregate",)
        present = tuple(key for key in required if key in present_keys(row, required) or key == "context_key")
        missing = tuple(key for key in required if key not in present)
        allowed_missing = row.expected_state in {"partial", "absent", "abstained", "out_of_domain"}
        checks.append(TopologyBetaFrontierConformanceCheck(row.operation.value, row.record_id, required, present, missing, not missing or allowed_missing, "payload fields are checked at the aggregate envelope boundary and declared missingness is retained"))
    return TopologyBetaFrontierConformanceReport(fields, tuple(checks), len(checks) == len(fixture.records) and all(item.passed for item in checks))


__all__ = ["TopologyBetaFrontierConformanceCheck", "TopologyBetaFrontierConformanceField", "TopologyBetaFrontierConformanceReport", "build_topology_beta_frontier_conformance"]
