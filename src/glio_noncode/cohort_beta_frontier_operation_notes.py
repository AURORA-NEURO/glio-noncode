"""Operation-specific notes that keep interpretation boundaries discoverable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierOperationNote:
    operation: str
    question: str
    input_boundary: str
    output_boundary: str
    common_failure_modes: tuple[str, ...]
    next_evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_operation_notes() -> tuple[CohortBetaFrontierOperationNote, ...]:
    raw = (("C05", "Do variants recur across distinct samples or form a local cluster?", "callable, exact-context variant observations", "descriptive recurrence and hotspot receipt", ("duplicate samples", "foreign context", "callable-space drift"), ("independent cohort calibration", "region definition review")), ("C06", "Does a region carry more distinct variants than the declared callable-space comparator?", "context-qualified region and callable bases", "burden, expected count, and excess receipt", ("wrong denominator", "outside-region rows", "missing comparator"), ("callable interval validation", "cohort transport")), ("C07", "Do observed variants converge on a functional feature?", "feature support with observed/control labels", "feature ranking and bounded contrast", ("feature ties", "missing controls", "definition drift"), ("matched controls", "functional assay")), ("C08", "Do genes converge on a pathway or regulon?", "versioned set memberships and declared direction", "set ranking with conflict retention", ("overlapping sets", "opposing directions", "set-version drift"), ("set transport", "orthogonal functional evidence")))
    return tuple(CohortBetaFrontierOperationNote(operation, question, input_boundary, output_boundary, failures, next_evidence, content_hash({"operation": operation, "question": question, "input_boundary": input_boundary}, prefix="operation-note")) for operation, question, input_boundary, output_boundary, failures, next_evidence in raw)


def operation_note_map() -> Mapping[str, CohortBetaFrontierOperationNote]:
    return {item.operation: item for item in default_cohort_beta_frontier_operation_notes()}


__all__ = ["CohortBetaFrontierOperationNote", "default_cohort_beta_frontier_operation_notes", "operation_note_map"]
