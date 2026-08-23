"""Stable error taxonomy for row, context, comparator, and release failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .serialization import content_hash, jsonable


class CohortBetaFrontierErrorClass(StrEnum):
    INPUT = "input"
    CONTEXT = "context"
    COMPARATOR = "comparator"
    POLICY = "policy"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierErrorCode:
    code: str
    error_class: CohortBetaFrontierErrorClass
    title: str
    severity: str
    recovery: str
    blocking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierErrorTaxonomy:
    codes: tuple[CohortBetaFrontierErrorCode, ...]
    accepted: bool
    content_address: str

    def by_class(self, error_class: CohortBetaFrontierErrorClass) -> tuple[CohortBetaFrontierErrorCode, ...]:
        return tuple(item for item in self.codes if item.error_class is error_class)

    def by_code(self, code: str) -> CohortBetaFrontierErrorCode:
        return next(item for item in self.codes if item.code == code)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_error_taxonomy() -> CohortBetaFrontierErrorTaxonomy:
    raw = (("GNC-C05-INPUT-001", CohortBetaFrontierErrorClass.INPUT, "malformed recurrence row", "error", "quarantine row", True), ("GNC-C05-CONTEXT-001", CohortBetaFrontierErrorClass.CONTEXT, "foreign recurrence context", "warning", "exclude from target", True), ("GNC-C06-COMPARATOR-001", CohortBetaFrontierErrorClass.COMPARATOR, "missing callable comparator", "warning", "retain partial state", True), ("GNC-C07-COMPARATOR-001", CohortBetaFrontierErrorClass.COMPARATOR, "missing matched controls", "warning", "retain partial state", True), ("GNC-C08-POLICY-001", CohortBetaFrontierErrorClass.POLICY, "opposing leading directions", "warning", "retain contradictory state", True), ("GNC-C08-POLICY-002", CohortBetaFrontierErrorClass.POLICY, "prohibited claim wording", "error", "hold publication", True), ("GNC-C05-RELEASE-001", CohortBetaFrontierErrorClass.RELEASE, "replay address mismatch", "error", "hold release", True), ("GNC-C05-RELEASE-002", CohortBetaFrontierErrorClass.RELEASE, "source registry not closed", "error", "repair provenance", True))
    codes = tuple(CohortBetaFrontierErrorCode(code, error_class, title, severity, recovery, blocking, content_hash({"code": code, "class": error_class, "title": title, "severity": severity}, prefix="error-code")) for code, error_class, title, severity, recovery, blocking in raw)
    return CohortBetaFrontierErrorTaxonomy(codes, len(codes) == 8 and all(item.blocking for item in codes), content_hash(codes, prefix="error-taxonomy"))


__all__ = ["CohortBetaFrontierErrorClass", "CohortBetaFrontierErrorCode", "CohortBetaFrontierErrorTaxonomy", "default_cohort_beta_frontier_error_taxonomy"]
