"""Claim usage receipt showing which terms each operation may use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_claim_ceiling import CohortAlphaFrontierClaimCeiling
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimUsageRow:
    operation: str
    permitted_terms: tuple[str, ...]
    blocked_terms: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimUsage:
    rows: tuple[CohortAlphaFrontierClaimUsageRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_claim_usage(ceiling: CohortAlphaFrontierClaimCeiling) -> CohortAlphaFrontierClaimUsage:
    permitted = ("descriptive", "aggregate", "observed", "signal", "comparison")
    rows = tuple(CohortAlphaFrontierClaimUsageRow(operation, permitted, ceiling.blocked_scope, ceiling.attached, content_hash({"operation": operation, "permitted": permitted, "blocked": ceiling.blocked_scope, "attached": ceiling.attached}, prefix="alpha-claim-usage")) for operation in ("C09", "C10", "C11", "C12"))
    return CohortAlphaFrontierClaimUsage(rows, ceiling.attached and len(rows) == 4 and all(item.accepted for item in rows), content_hash(rows, prefix="alpha-claim-usage-report"))


__all__ = ["CohortAlphaFrontierClaimUsage", "CohortAlphaFrontierClaimUsageRow", "build_cohort_alpha_frontier_claim_usage"]
