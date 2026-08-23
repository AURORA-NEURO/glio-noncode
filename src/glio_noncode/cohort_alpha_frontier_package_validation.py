"""Package validation that checks required files and claim-safe exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_package import CohortAlphaFrontierPackageManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPackageValidationCheck:
    check_id: str
    observed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPackageValidationReport:
    checks: tuple[CohortAlphaFrontierPackageValidationCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def validate_cohort_alpha_frontier_package(package: CohortAlphaFrontierPackageManifest) -> CohortAlphaFrontierPackageValidationReport:
    paths = {entry.path for entry in package.entries}
    raw = (
        ("fixture", "fixture.json" in paths, "fixture is present"),
        ("evaluation", "evaluation.json" in paths, "evaluation is present"),
        ("quality", "quality.json" in paths, "quality gate is present"),
        ("claim_ceiling", "README.md" in paths, "scope and claim ceiling are present"),
        ("addresses", all(entry.content_address for entry in package.entries), "every entry is receipted"),
    )
    checks = tuple(CohortAlphaFrontierPackageValidationCheck(check_id, observed, detail, content_hash({"id": check_id, "observed": observed, "detail": detail}, prefix="alpha-package-check")) for check_id, observed, detail in raw)
    return CohortAlphaFrontierPackageValidationReport(checks, package.accepted and all(item.observed for item in checks), content_hash(checks, prefix="alpha-package-validation"))


__all__ = ["CohortAlphaFrontierPackageValidationCheck", "CohortAlphaFrontierPackageValidationReport", "validate_cohort_alpha_frontier_package"]
