"""Canonical ordering for operation, source, issue, and receipt views."""

from __future__ import annotations

from typing import Any

from .serialization import jsonable
from .structural_architecture_contracts import (
    StructuralArchitectureEvaluation,
    StructuralArchitectureFixture,
)


def normalize_structural_architecture_fixture(
    fixture: StructuralArchitectureFixture,
) -> dict[str, Any]:
    """Return a deterministic view suitable for hashing and diffing."""

    value = fixture.to_dict()
    value["sources"] = sorted(value["sources"], key=lambda item: item["source_id"])
    value["operations"] = sorted(value["operations"], key=lambda item: item["ordinal"])
    value["cases"] = sorted(
        value["cases"], key=lambda item: (item["operation_id"], item["case_id"])
    )
    for case in value["cases"]:
        case["source_ids"] = sorted(case["source_ids"])
        case["expected_issue_codes"] = sorted(case["expected_issue_codes"])
    return jsonable(value)


def normalize_structural_architecture_evaluation(
    evaluation: StructuralArchitectureEvaluation,
) -> dict[str, Any]:
    """Return a stable receipt order independent of caller iteration order."""

    value = evaluation.to_dict()
    value["receipts"] = sorted(value["receipts"], key=lambda item: item["case_id"])
    value["checks"] = sorted(value["checks"], key=lambda item: item["check_id"])
    return jsonable(value)


__all__ = [
    "normalize_structural_architecture_evaluation",
    "normalize_structural_architecture_fixture",
]
