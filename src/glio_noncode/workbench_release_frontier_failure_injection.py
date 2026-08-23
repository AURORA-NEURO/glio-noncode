"""Malformed and boundary failure rehearsals."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .workbench_release_frontier_operations import evaluate_accessibility, evaluate_report_export, evaluate_review_form, evaluate_search_palette

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseFailureReport:
    cases: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def run_workbench_release_failure_injections() -> WorkbenchReleaseFailureReport:
    cases = ({"case": "invalid-review", "state": evaluate_review_form({}).state.value, "required": "rejected"}, {"case": "empty-report", "state": evaluate_report_export({"report_id": "x", "context_key": "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment", "format": "json", "sections": []}).state.value, "required": "review"}, {"case": "empty-search", "state": evaluate_search_palette({"query": "x", "context_key": "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment", "records": [], "commands": []}).state.value, "required": "review"}, {"case": "empty-accessibility", "state": evaluate_accessibility({"surface_id": "x", "context_key": "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment", "surface": {}, "required_criteria": ["keyboard"]}).state.value, "required": "review"})
    body = {"cases": cases, "accepted": all(item["state"] == item["required"] for item in cases)}
    return WorkbenchReleaseFailureReport(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseFailureReport", "run_workbench_release_failure_injections"]
