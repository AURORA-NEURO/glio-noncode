"""Malformed payload and boundary failure rehearsals."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .validation_design_frontier_operations import evaluate_assay_eligibility, evaluate_gap_analysis, evaluate_mpra_package, evaluate_starrseq_package
from .validation_design_frontier_public_data import default_validation_design_frontier_fixture

@dataclass(frozen=True, slots=True)
class ValidationDesignFailureReport:
    fixture_id: str
    cases: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def run_validation_design_failure_injections() -> ValidationDesignFailureReport:
    fixture = default_validation_design_frontier_fixture(); payloads = (("gap-invalid", evaluate_gap_analysis({}), "rejected"), ("route-invalid", evaluate_assay_eligibility({}), "rejected"), ("mpra-invalid", evaluate_mpra_package({}), "rejected"), ("starr-invalid", evaluate_starrseq_package({}), "rejected"))
    cases = tuple({"case": name, "state": result.state.value, "required": required, "issue_codes": result.issue_codes} for name, result, required in payloads)
    body = {"fixture_id": fixture.fixture_id, "cases": cases, "accepted": all(item["state"] == item["required"] for item in cases)}
    return ValidationDesignFailureReport(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignFailureReport", "run_validation_design_failure_injections"]
