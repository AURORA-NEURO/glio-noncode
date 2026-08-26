"""Deterministic module-by-module depth scoring for project progress views."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_inventory_contracts import ModuleInventory, ModuleState
from .module_inventory_query import inventory_from_mapping
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleDepthAssessment:
    """Explainable aggregate depth score for one source module."""

    module_id: str
    family: str
    role: str
    state: str
    score: float
    tier: str
    dimensions: Mapping[str, float]
    blockers: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.module_id.strip()
            or not self.family.strip()
            or not self.role.strip()
            or not self.tier.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module depth assessment identifiers are required")
        if not 0.0 <= self.score <= 1.0:
            raise ValidationError("module depth score must be between 0 and 1")
        if self.tier not in {"blocked", "review", "established", "deep"}:
            raise ValidationError("module depth tier is unsupported")
        if any(not 0.0 <= float(value) <= 1.0 for value in self.dimensions.values()):
            raise ValidationError("module depth dimensions must be between 0 and 1")
        if tuple(sorted(set(self.blockers))) != self.blockers:
            raise ValidationError("module depth blockers must be unique and sorted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleDepthReport:
    """Whole-project module depth report with conserved counters."""

    inventory_address: str
    assessments: tuple[ModuleDepthAssessment, ...]
    overall_score: float
    overall_percent: float
    deep_count: int
    established_count: int
    review_count: int
    blocked_count: int
    covered_module_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.inventory_address.strip() or not self.content_address.strip():
            raise ValidationError("module depth report requires addresses")
        if tuple(item.module_id for item in self.assessments) != tuple(
            sorted(item.module_id for item in self.assessments)
        ):
            raise ValidationError("module depth assessments must be sorted")
        if not 0.0 <= self.overall_score <= 1.0 or not 0.0 <= self.overall_percent <= 100.0:
            raise ValidationError("module depth aggregate score is invalid")
        if self.covered_module_count < 0 or self.covered_module_count > len(self.assessments):
            raise ValidationError("module depth covered count is invalid")

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result = {
            "inventory_address": self.inventory_address,
            "module_count": len(self.assessments),
            "overall_score": self.overall_score,
            "overall_percent": self.overall_percent,
            "deep_count": self.deep_count,
            "established_count": self.established_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "covered_module_count": self.covered_module_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result["assessments"] = [item.to_dict() for item in self.assessments]
        return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _assessment(module: Any) -> ModuleDepthAssessment:
    parse_score = (
        1.0
        if module.state is ModuleState.PARSED
        else 0.7
        if module.state is ModuleState.EMPTY
        else 0.0
    )
    test_score = min(1.0, module.test_reference_count / 3.0)
    symbol_score = min(1.0, module.public_symbol_count / 8.0)
    dependency_score = (
        1.0
        if module.import_count == 0
        else min(1.0, module.local_dependency_count / module.import_count)
    )
    scale_score = min(1.0, module.nonblank_lines / 400.0) if module.nonblank_lines else 0.0
    dimensions = {
        "parse": round(parse_score, 6),
        "tests": round(test_score, 6),
        "public_surface": round(symbol_score, 6),
        "dependency_resolution": round(dependency_score, 6),
        "implementation_scale": round(scale_score, 6),
    }
    score = round(sum(dimensions.values()) / len(dimensions), 6)
    blockers: list[str] = []
    if parse_score == 0.0:
        blockers.append("parse_error")
    if module.test_reference_count == 0:
        blockers.append("no_test_reference")
    if module.import_count and module.local_dependency_count < module.import_count:
        blockers.append("unresolved_local_import")
    if score < 0.35 or parse_score == 0.0:
        tier = "blocked"
    elif score < 0.60:
        tier = "review"
    elif score < 0.82:
        tier = "established"
    else:
        tier = "deep"
    body = {
        "module_id": module.module_id,
        "family": module.family,
        "role": module.role,
        "state": module.state,
        "score": score,
        "tier": tier,
        "dimensions": dimensions,
        "blockers": tuple(sorted(set(blockers))),
    }
    return ModuleDepthAssessment(**body, content_address=_address(body, "module-inventory-depth"))


def build_module_inventory_depth(value: ModuleInventory | Mapping[str, Any]) -> ModuleDepthReport:
    """Score source modules using only static inventory dimensions."""

    inventory = value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)
    assessments = tuple(
        sorted(
            (_assessment(module) for module in inventory.modules), key=lambda item: item.module_id
        )
    )
    overall = (
        round(sum(item.score for item in assessments) / len(assessments), 6) if assessments else 0.0
    )
    body = {
        "inventory_address": inventory.content_address,
        "assessments": assessments,
        "overall_score": overall,
        "overall_percent": round(overall * 100.0, 2),
        "deep_count": sum(item.tier == "deep" for item in assessments),
        "established_count": sum(item.tier == "established" for item in assessments),
        "review_count": sum(item.tier == "review" for item in assessments),
        "blocked_count": sum(item.tier == "blocked" for item in assessments),
        "covered_module_count": sum(not item.blockers for item in assessments),
        "accepted": inventory.accepted,
    }
    return ModuleDepthReport(
        **body, content_address=_address(body, "module-inventory-depth-report")
    )


def query_module_inventory_depth(
    value: ModuleDepthReport,
    *,
    family: str | None = None,
    role: str | None = None,
    tier: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("module depth paging is invalid")
    rows = [item.to_dict() for item in value.assessments]
    if family:
        rows = [item for item in rows if item["family"] == family]
    if role:
        rows = [item for item in rows if item["role"] == role]
    if tier:
        rows = [item for item in rows if item["tier"] == tier]
    if min_score is not None:
        rows = [item for item in rows if item["score"] >= min_score]
    if max_score is not None:
        rows = [item for item in rows if item["score"] <= max_score]
    if text:
        rows = [item for item in rows if text.casefold() in str(item).casefold()]
    body = {
        "inventory_address": value.inventory_address,
        "query": {
            "family": family,
            "role": role,
            "tier": tier,
            "min_score": min_score,
            "max_score": max_score,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-inventory-depth-query")}


def module_inventory_depth_csv(value: ModuleDepthReport) -> str:
    fields = (
        "module_id",
        "family",
        "role",
        "state",
        "score",
        "tier",
        "parse",
        "tests",
        "public_surface",
        "dependency_resolution",
        "implementation_scale",
        "blockers",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.assessments:
        row = item.to_dict()
        row.update(item.dimensions)
        row["blockers"] = ";".join(item.blockers)
        writer.writerow(row)
    return output.getvalue()


def module_inventory_depth_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-depth-v1",
        "dimensions": [
            "parse",
            "tests",
            "public_surface",
            "dependency_resolution",
            "implementation_scale",
        ],
        "tiers": ["blocked", "review", "established", "deep"],
        "score_range": [0.0, 1.0],
        "percent_range": [0.0, 100.0],
        "interpretation": "static repository maturity signal, not scientific validity",
    }


def module_inventory_depth_capabilities() -> dict[str, Any]:
    operations = (
        "score_module_parse_state",
        "score_test_references",
        "score_public_surface",
        "score_dependency_resolution",
        "score_implementation_scale",
        "aggregate_project_percent",
        "query_depth_assessments",
        "export_depth_csv",
    )
    return {
        "version": "module-inventory-depth-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "ModuleDepthAssessment",
    "ModuleDepthReport",
    "build_module_inventory_depth",
    "module_inventory_depth_capabilities",
    "module_inventory_depth_csv",
    "module_inventory_depth_schema",
    "query_module_inventory_depth",
]
