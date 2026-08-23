"""Redaction and projection controls for aggregate result exports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable


class CohortBetaFrontierRedactionMode(StrEnum):
    RETAIN = "retain"
    MASK = "mask"
    DROP = "drop"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRedactionRule:
    field_name: str
    public_mode: CohortBetaFrontierRedactionMode
    review_mode: CohortBetaFrontierRedactionMode
    operations: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRedactionResult:
    operation: str
    audience: str
    retained: Mapping[str, Any]
    masked_fields: tuple[str, ...]
    dropped_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_redaction_rules() -> tuple[CohortBetaFrontierRedactionRule, ...]:
    raw = (
        ("record_id", CohortBetaFrontierRedactionMode.MASK, CohortBetaFrontierRedactionMode.RETAIN, ("C05", "C06", "C07", "C08"), "row keys are pseudonymous and are not needed in public aggregates"),
        ("sample_id", CohortBetaFrontierRedactionMode.DROP, CohortBetaFrontierRedactionMode.RETAIN, ("C05", "C06"), "sample counts are retained while sample keys stay in review scope"),
        ("variant_id", CohortBetaFrontierRedactionMode.MASK, CohortBetaFrontierRedactionMode.RETAIN, ("C05", "C06", "C07", "C08"), "variant identity is retained only as a bounded aggregate key"),
        ("source_id", CohortBetaFrontierRedactionMode.RETAIN, CohortBetaFrontierRedactionMode.RETAIN, ("C05", "C06", "C07", "C08"), "public source receipt is required for provenance"),
        ("context_key", CohortBetaFrontierRedactionMode.RETAIN, CohortBetaFrontierRedactionMode.RETAIN, ("C05", "C06", "C07", "C08"), "context is required to prevent projection drift"),
        ("support", CohortBetaFrontierRedactionMode.RETAIN, CohortBetaFrontierRedactionMode.RETAIN, ("C07", "C08"), "bounded support is part of the descriptive result"),
        ("direction", CohortBetaFrontierRedactionMode.RETAIN, CohortBetaFrontierRedactionMode.RETAIN, ("C07", "C08"), "direction conflict must remain visible"),
        ("content_address", CohortBetaFrontierRedactionMode.RETAIN, CohortBetaFrontierRedactionMode.RETAIN, ("C05", "C06", "C07", "C08"), "immutable receipt address is always retained"),
    )
    return tuple(CohortBetaFrontierRedactionRule(field_name, public_mode, review_mode, operations, rationale, content_hash({"field_name": field_name, "public_mode": public_mode, "review_mode": review_mode, "operations": operations}, prefix="redaction-rule")) for field_name, public_mode, review_mode, operations, rationale in raw)


def redact_cohort_beta_frontier_record(operation: str, audience: str, record: Mapping[str, Any], rules: tuple[CohortBetaFrontierRedactionRule, ...] | None = None) -> CohortBetaFrontierRedactionResult:
    selected = rules or default_cohort_beta_frontier_redaction_rules()
    retained: dict[str, Any] = {}
    masked: list[str] = []
    dropped: list[str] = []
    for field_name, value in record.items():
        rule = next((item for item in selected if item.field_name == field_name and operation in item.operations), None)
        mode = rule.review_mode if audience == "research_review" else rule.public_mode if rule else CohortBetaFrontierRedactionMode.DROP
        if mode is CohortBetaFrontierRedactionMode.RETAIN:
            retained[field_name] = value
        elif mode is CohortBetaFrontierRedactionMode.MASK:
            retained[field_name] = f"masked:{content_hash(value, prefix='value')[-12:]}"
            masked.append(field_name)
        else:
            dropped.append(field_name)
    retained["operation"] = operation
    return CohortBetaFrontierRedactionResult(operation, audience, retained, tuple(masked), tuple(dropped), "context_key" in retained or audience == "research_review", content_hash({"operation": operation, "audience": audience, "retained": retained, "masked": masked, "dropped": dropped}, prefix="redaction-result"))


__all__ = ["CohortBetaFrontierRedactionMode", "CohortBetaFrontierRedactionResult", "CohortBetaFrontierRedactionRule", "default_cohort_beta_frontier_redaction_rules", "redact_cohort_beta_frontier_record"]
