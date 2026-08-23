"""Export profiles preserving state, limitations, and content addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_report import CohortAlphaFrontierReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierExportProfile:
    format: str
    extension: str
    media_type: str
    includes_claim_ceiling: bool
    includes_content_addresses: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierExportReport:
    profiles: tuple[CohortAlphaFrontierExportProfile, ...]
    report_id: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_export_profiles(report: CohortAlphaFrontierReport) -> CohortAlphaFrontierExportReport:
    raw = (("json", ".json", "application/json"), ("markdown", ".md", "text/markdown"), ("plain", ".txt", "text/plain"), ("jsonl", ".jsonl", "application/jsonl"), ("csv", ".csv", "text/csv"))
    profiles = tuple(CohortAlphaFrontierExportProfile(format_name, extension, media_type, True, True, content_hash({"format": format_name, "extension": extension, "media_type": media_type, "claim_ceiling": True, "addresses": True}, prefix="alpha-export")) for format_name, extension, media_type in raw)
    return CohortAlphaFrontierExportReport(profiles, report.report_id, report.accepted and len(profiles) == 5 and all(item.includes_claim_ceiling and item.includes_content_addresses for item in profiles), content_hash({"profiles": profiles, "report": report.content_address}, prefix="alpha-export-report"))


__all__ = ["CohortAlphaFrontierExportProfile", "CohortAlphaFrontierExportReport", "build_cohort_alpha_frontier_export_profiles"]
