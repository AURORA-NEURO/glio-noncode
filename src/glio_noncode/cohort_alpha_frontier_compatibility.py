"""Compatibility matrix for supported serialization and runtime consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_package import CohortAlphaFrontierPackageManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCompatibilityCell:
    consumer: str
    format: str
    version: str
    accepted: bool
    constraint: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCompatibilityReport:
    cells: tuple[CohortAlphaFrontierCompatibilityCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_compatibility(package: CohortAlphaFrontierPackageManifest) -> CohortAlphaFrontierCompatibilityReport:
    raw = (("python", "json", "1", "typed dataclass serialization"), ("cli", "json", "1", "stable command output"), ("markdown", "text", "1", "plain report fallback"), ("archive", "json", "1", "content-addressed package"), ("test", "json", "1", "deterministic fixture"), ("workflow", "json", "1", "CI artifact upload"))
    cells = tuple(CohortAlphaFrontierCompatibilityCell(consumer, format_name, version, True, constraint, content_hash({"consumer": consumer, "format": format_name, "version": version, "constraint": constraint}, prefix="alpha-compatibility")) for consumer, format_name, version, constraint in raw)
    return CohortAlphaFrontierCompatibilityReport(cells, package.accepted and len(cells) == 6 and all(item.accepted for item in cells), content_hash({"cells": cells, "package": package.content_address}, prefix="alpha-compatibility-report"))


__all__ = ["CohortAlphaFrontierCompatibilityCell", "CohortAlphaFrontierCompatibilityReport", "build_cohort_alpha_frontier_compatibility"]
