"""Independent release checks assembled from the final runtime report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseCheck:
    check_id: str
    category: str
    observed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseCheckReport:
    checks: tuple[CohortAlphaFrontierReleaseCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_release_checks(stages: tuple[CohortAlphaFrontierRuntimeStage, ...]) -> CohortAlphaFrontierReleaseCheckReport:
    raw = (("ordered", "runtime", tuple(stage.ordinal for stage in stages) == tuple(range(1, len(stages) + 1)), "stage ordinals are contiguous"), ("unique", "runtime", len({stage.stage_id for stage in stages}) == len(stages), "stage identifiers are unique"), ("receipted", "integrity", all(stage.output_address for stage in stages), "every stage has a content address"), ("accepted", "quality", all(stage.accepted for stage in stages), "every runtime stage accepted"), ("depth", "scope", len(stages) >= 48, "depth runtime includes broad release surface"))
    checks = tuple(CohortAlphaFrontierReleaseCheck(check_id, category, observed, detail, content_hash({"id": check_id, "category": category, "observed": observed, "detail": detail}, prefix="alpha-release-check")) for check_id, category, observed, detail in raw)
    return CohortAlphaFrontierReleaseCheckReport(checks, all(item.observed for item in checks), content_hash(checks, prefix="alpha-release-check-report"))


__all__ = ["CohortAlphaFrontierReleaseCheck", "CohortAlphaFrontierReleaseCheckReport", "evaluate_cohort_alpha_frontier_release_checks"]
