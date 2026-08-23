"""Normalization receipts for fixture metadata and operation ordering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierNormalizationRow:
    record_id: str
    operation: str
    context: str
    source_count: int
    payload_keys: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierNormalizationReport:
    rows: tuple[CohortAlphaFrontierNormalizationRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def normalize_cohort_alpha_frontier_fixture(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierNormalizationReport:
    rows = []
    for record in fixture.records:
        payload = dict(record.payload)
        context = str(payload.get("context_key", fixture.foreign_context_key if record.control_class == "foreign_context" else fixture.context_key if record.control_class != "empty_control" else ""))
        normalized = CohortAlphaFrontierNormalizationRow(record.record_id, record.operation, context, len(record.source_ids), tuple(sorted(payload)), (bool(context) or record.control_class == "empty_control") and len(record.source_ids) >= 1, content_hash({"record_id": record.record_id, "operation": record.operation, "context": context, "source_count": len(record.source_ids), "keys": sorted(payload)}, prefix="alpha-normalization"))
        rows.append(normalized)
    values = tuple(rows)
    return CohortAlphaFrontierNormalizationReport(values, len(values) == 16 and all(item.accepted for item in values), content_hash(values, prefix="alpha-normalization-report"))


__all__ = ["CohortAlphaFrontierNormalizationReport", "CohortAlphaFrontierNormalizationRow", "normalize_cohort_alpha_frontier_fixture"]
