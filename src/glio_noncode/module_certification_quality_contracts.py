"""Typed contracts for certification coverage and release readiness."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_CERTIFICATION_QUALITY_VERSION = "module-certification-quality-v1"
MODULE_CERTIFICATION_QUALITY_BOUNDARY = "public_aggregate_module_certification_quality"
MODULE_CERTIFICATION_QUALITY_MAX_MEASURES = 20_000
MODULE_CERTIFICATION_QUALITY_MAX_GAPS = 512
MODULE_CERTIFICATION_QUALITY_MAX_LIMIT = 512
MODULE_CERTIFICATION_QUALITY_DEFAULT_LIMIT = 50


class CertificationReadiness(StrEnum):
    """Release-facing interpretation of the static certification evidence."""

    READY = "ready"
    WARNING = "warning"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _percent(value: Any, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 100.0:
        raise ValidationError(f"{field} must be between zero and one hundred")


def _score(value: Any, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ModuleCertificationCoverageMeasure:
    """Coverage conservation for one certification check kind."""

    kind: str
    module_count: int
    applicable_count: int
    passed_count: int
    failed_count: int
    not_applicable_count: int
    coverage_percent: float
    pass_percent: float
    content_address: str

    def __post_init__(self) -> None:
        _text(self.kind, "kind")
        for field in (
            "module_count",
            "applicable_count",
            "passed_count",
            "failed_count",
            "not_applicable_count",
        ):
            _count(getattr(self, field), field)
        _percent(self.coverage_percent, "coverage_percent")
        _percent(self.pass_percent, "pass_percent")
        _text(self.content_address, "content_address")
        if self.passed_count + self.failed_count != self.applicable_count:
            raise ValidationError("check coverage applicable count does not conserve states")
        if self.applicable_count + self.not_applicable_count != self.module_count:
            raise ValidationError("check coverage module count does not conserve states")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationFamilyMeasure:
    """Aggregate readiness counters for one module family."""

    family: str
    module_count: int
    certified_count: int
    review_count: int
    blocked_count: int
    uncovered_count: int
    overall_score: float
    gap_count: int
    coverage_percent: float
    content_address: str

    def __post_init__(self) -> None:
        _text(self.family, "family")
        for field in (
            "module_count",
            "certified_count",
            "review_count",
            "blocked_count",
            "uncovered_count",
            "gap_count",
        ):
            _count(getattr(self, field), field)
        _score(self.overall_score, "overall_score")
        _percent(self.coverage_percent, "coverage_percent")
        _text(self.content_address, "content_address")
        if (
            sum((self.certified_count, self.review_count, self.blocked_count, self.uncovered_count))
            != self.module_count
        ):
            raise ValidationError("family state counts do not conserve modules")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationQualityReport:
    """Conserved project-wide coverage and readiness report."""

    matrix_address: str
    lineage_address: str
    check_coverage: tuple[ModuleCertificationCoverageMeasure, ...]
    family_coverage: tuple[ModuleCertificationFamilyMeasure, ...]
    blocker_modules: tuple[str, ...]
    top_gaps: tuple[str, ...]
    overall_score: float
    evidence_coverage_percent: float
    readiness: CertificationReadiness
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.matrix_address, "matrix_address")
        _text(self.lineage_address, "lineage_address")
        _score(self.overall_score, "overall_score")
        _percent(self.evidence_coverage_percent, "evidence_coverage_percent")
        _text(self.content_address, "content_address")
        if not self.check_coverage:
            raise ValidationError("quality report requires check coverage")
        _sorted_unique(self.blocker_modules, "blocker_modules")
        _sorted_unique(self.top_gaps, "top_gaps")
        if len(self.top_gaps) > MODULE_CERTIFICATION_QUALITY_MAX_GAPS:
            raise ValidationError("quality report gap limit exceeded")
        if tuple(item.kind for item in self.check_coverage) != tuple(
            sorted(item.kind for item in self.check_coverage)
        ):
            raise ValidationError("quality check measures must be sorted")
        if tuple(item.family for item in self.family_coverage) != tuple(
            sorted(item.family for item in self.family_coverage)
        ):
            raise ValidationError("quality family measures must be sorted")
        if (
            len(self.check_coverage) + len(self.family_coverage)
            > MODULE_CERTIFICATION_QUALITY_MAX_MEASURES
        ):
            raise ValidationError("quality measure limit exceeded")

    def to_dict(self, *, include_measures: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_CERTIFICATION_QUALITY_VERSION,
            "boundary": MODULE_CERTIFICATION_QUALITY_BOUNDARY,
            "matrix_address": self.matrix_address,
            "lineage_address": self.lineage_address,
            "check_measure_count": len(self.check_coverage),
            "family_measure_count": len(self.family_coverage),
            "blocker_count": len(self.blocker_modules),
            "gap_count": len(self.top_gaps),
            "overall_score": self.overall_score,
            "evidence_coverage_percent": self.evidence_coverage_percent,
            "readiness": self.readiness.value,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_measures:
            result["check_coverage"] = [item.to_dict() for item in self.check_coverage]
            result["family_coverage"] = [item.to_dict() for item in self.family_coverage]
            result["blocker_modules"] = list(self.blocker_modules)
            result["top_gaps"] = list(self.top_gaps)
        return result


def address_module_certification_coverage(value: ModuleCertificationCoverageMeasure) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-coverage")


def address_module_certification_family(value: ModuleCertificationFamilyMeasure) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-family")


__all__ = [
    "CertificationReadiness",
    "MODULE_CERTIFICATION_QUALITY_BOUNDARY",
    "MODULE_CERTIFICATION_QUALITY_DEFAULT_LIMIT",
    "MODULE_CERTIFICATION_QUALITY_MAX_GAPS",
    "MODULE_CERTIFICATION_QUALITY_MAX_LIMIT",
    "MODULE_CERTIFICATION_QUALITY_MAX_MEASURES",
    "MODULE_CERTIFICATION_QUALITY_VERSION",
    "ModuleCertificationCoverageMeasure",
    "ModuleCertificationFamilyMeasure",
    "ModuleCertificationQualityReport",
    "address_module_certification_coverage",
    "address_module_certification_family",
]
