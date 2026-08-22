"""Operation-specific field conformance for the closed alpha envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierConformanceField:
    field_name: str
    field_type: str
    required: bool
    retention_rule: str
    missingness_rule: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierConformanceCheck:
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
class TopologyAlphaFrontierConformanceReport:
    fields: dict[str, tuple[TopologyAlphaFrontierConformanceField, ...]]
    checks: tuple[TopologyAlphaFrontierConformanceCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierConformanceCheck, ...]:
        return tuple(item for item in self.checks if item.operation == operation)

    def failed(self) -> tuple[TopologyAlphaFrontierConformanceCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fields": {key: [item.to_dict() for item in items] for key, items in self.fields.items()}, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _field(name: str, field_type: str, rule: str, missing: str = "retain explicit missingness") -> TopologyAlphaFrontierConformanceField:
    return TopologyAlphaFrontierConformanceField(name, field_type, True, rule, missing)


def build_topology_alpha_frontier_conformance(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierConformanceReport:
    fields = {
        "boundary_motif": (_field("boundary_id", "string", "preserve boundary identity"), _field("side", "enum", "preserve left or right side"), _field("orientation", "enum", "retain orientation"), _field("score", "number", "retain measured score"), _field("context_key", "string", "gate exact context"), _field("source_version", "string", "retain source version")),
        "ctcf_cohesin": (_field("variant_id", "string", "preserve variant identity"), _field("reference_ctcf", "number", "retain reference channel"), _field("alternate_ctcf", "number", "retain alternate channel"), _field("context_key", "string", "gate exact context"), _field("source_version", "string", "retain source version")),
        "idh_insulator": (_field("region_id", "string", "preserve region identity"), _field("molecular_state", "enum", "retain molecular state"), _field("insulator_score", "number", "retain score"), _field("methylation_fraction", "number", "retain methylation separately"), _field("context_key", "string", "gate exact context")),
        "sv_rewire": (_field("sv_id", "string", "preserve event identity"), _field("sv_kind", "enum", "retain event kind"), _field("affected_node_ids", "array", "retain affected nodes"), _field("context_key", "string", "gate exact context")),
    }
    checks = []
    for row in fixture.records:
        required = tuple(item.field_name for item in fields[row.operation.value]) + ("public_aggregate",)
        if row.operation.value == "sv_rewire":
            source = (row.payload.get("events") or [{}])[0]
        else:
            key = {"boundary_motif": "records", "ctcf_cohesin": "records", "idh_insulator": "records"}[row.operation.value]
            source = (row.payload.get(key) or [{}])[0]
        present = tuple(key for key in required if key in source or key in row.payload)
        missing = tuple(key for key in required if key not in present)
        allowed = row.expected_state in {"partial", "out_of_domain", "ambiguous"}
        checks.append(TopologyAlphaFrontierConformanceCheck(row.operation.value, row.record_id, required, present, missing, not missing or allowed, "operation fields are checked at the aggregate envelope and declared missingness remains visible"))
    return TopologyAlphaFrontierConformanceReport(fields, tuple(checks), len(checks) == len(fixture.records) and all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierConformanceCheck", "TopologyAlphaFrontierConformanceField", "TopologyAlphaFrontierConformanceReport", "build_topology_alpha_frontier_conformance"]
