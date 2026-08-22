"""Control-coverage inventory for the C09-C12 aggregate fixture.

The inventory makes the fixture's negative space inspectable. Positive,
single-source, fragile, missing, unresolved, contradictory, measured-negative,
and foreign-context rows are classified explicitly. It proves that controls
were exercised and not silently discarded; it is not an inference engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture, CausalAlphaFrontierOperation, CausalAlphaFrontierRole
from .causal_reasoning import CausalState
from .serialization import content_hash


class CausalAlphaFrontierControlClass(StrEnum):
    POSITIVE = "positive"
    SINGLE_SOURCE = "single_source"
    FRAGILE = "fragile"
    MISSING = "missing"
    UNRESOLVED = "unresolved"
    CONTRADICTORY = "contradictory"
    MEASURED_NEGATIVE = "measured_negative"
    FOREIGN_CONTEXT = "foreign_context"


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierControlCoverageRow:
    record_id: str
    operation: CausalAlphaFrontierOperation
    role: CausalAlphaFrontierRole
    control_class: CausalAlphaFrontierControlClass
    expected_state: CausalState
    observed_state: CausalState
    source_count: int
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    retained_in_review: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "record_id": self.record_id,
            "operation": self.operation,
            "role": self.role,
            "control_class": self.control_class,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "source_count": self.source_count,
            "expected_issue_codes": self.expected_issue_codes,
            "observed_issue_codes": self.observed_issue_codes,
            "retained_in_review": self.retained_in_review,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierControlCoverage:
    fixture_id: str
    rows: tuple[CausalAlphaFrontierControlCoverageRow, ...]
    class_counts: dict[str, int]
    operation_counts: dict[str, dict[str, int]]
    required_classes: tuple[CausalAlphaFrontierControlClass, ...]
    present_classes: tuple[CausalAlphaFrontierControlClass, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def missing_classes(self) -> tuple[CausalAlphaFrontierControlClass, ...]:
        return tuple(item for item in self.required_classes if item not in self.present_classes)

    def for_class(self, control_class: CausalAlphaFrontierControlClass | str) -> tuple[CausalAlphaFrontierControlCoverageRow, ...]:
        value = CausalAlphaFrontierControlClass(str(control_class))
        return tuple(item for item in self.rows if item.control_class is value)

    def for_operation(self, operation: CausalAlphaFrontierOperation | str) -> tuple[CausalAlphaFrontierControlCoverageRow, ...]:
        value = CausalAlphaFrontierOperation(str(operation))
        return tuple(item for item in self.rows if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "rows": [item.to_dict() for item in self.rows],
            "class_counts": dict(self.class_counts),
            "operation_counts": {key: dict(value) for key, value in self.operation_counts.items()},
            "required_classes": self.required_classes,
            "present_classes": self.present_classes,
            "missing_classes": self.missing_classes,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


_REQUIRED_CLASSES = (
    CausalAlphaFrontierControlClass.POSITIVE,
    CausalAlphaFrontierControlClass.SINGLE_SOURCE,
    CausalAlphaFrontierControlClass.FRAGILE,
    CausalAlphaFrontierControlClass.MISSING,
    CausalAlphaFrontierControlClass.UNRESOLVED,
    CausalAlphaFrontierControlClass.CONTRADICTORY,
    CausalAlphaFrontierControlClass.MEASURED_NEGATIVE,
    CausalAlphaFrontierControlClass.FOREIGN_CONTEXT,
)


def _classify(record: Any, result: Any, fixture: CausalAlphaFrontierFixture) -> CausalAlphaFrontierControlClass:
    if record.context_key == fixture.foreign_context_key:
        return CausalAlphaFrontierControlClass.FOREIGN_CONTEXT
    if record.role is CausalAlphaFrontierRole.POSITIVE:
        return CausalAlphaFrontierControlClass.POSITIVE
    if result.observed_state is CausalState.CONTRADICTORY:
        return CausalAlphaFrontierControlClass.CONTRADICTORY
    if result.observed_state is CausalState.MEASURED_NEGATIVE:
        return CausalAlphaFrontierControlClass.MEASURED_NEGATIVE
    if record.operation is CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY:
        if len(record.payload.get("evidence", ())) == 1:
            return CausalAlphaFrontierControlClass.SINGLE_SOURCE
        return CausalAlphaFrontierControlClass.FRAGILE
    if record.operation is CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST:
        observations = {str(item.get("confounder_id", "")) for item in record.payload.get("observations", ())}
        required = {str(item) for item in record.payload.get("required_confounder_ids", ())}
        if required - observations:
            return CausalAlphaFrontierControlClass.MISSING
        return CausalAlphaFrontierControlClass.UNRESOLVED
    return CausalAlphaFrontierControlClass.SINGLE_SOURCE


def build_causal_alpha_frontier_control_coverage(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, review_record_ids: tuple[str, ...] = ()) -> CausalAlphaFrontierControlCoverage:
    records = fixture.record_map()
    review_ids = set(review_record_ids)
    rows: list[CausalAlphaFrontierControlCoverageRow] = []
    for result in evaluation.evaluation.results:
        record = records[result.record_id]
        control_class = _classify(record, result, fixture)
        rows.append(CausalAlphaFrontierControlCoverageRow(record.record_id, record.operation, record.role, control_class, result.expected_state, result.observed_state, len(record.source_ids), result.expected_issue_codes, result.observed_issue_codes, result.record_id in review_ids, result.accepted))
    class_counts: dict[str, int] = {}
    operation_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        class_counts[row.control_class.value] = class_counts.get(row.control_class.value, 0) + 1
        operation = operation_counts.setdefault(row.operation.value, {})
        operation[row.control_class.value] = operation.get(row.control_class.value, 0) + 1
    present = tuple(item for item in _REQUIRED_CLASSES if item.value in class_counts)
    accepted = bool(len(rows) == 16 and not tuple(item for item in _REQUIRED_CLASSES if item not in present) and all(item.accepted for item in rows) and all(item.retained_in_review or item.control_class is CausalAlphaFrontierControlClass.POSITIVE for item in rows))
    return CausalAlphaFrontierControlCoverage(fixture.fixture_id, tuple(rows), dict(sorted(class_counts.items())), {key: dict(sorted(value.items())) for key, value in sorted(operation_counts.items())}, _REQUIRED_CLASSES, present, accepted)


__all__ = ["CausalAlphaFrontierControlClass", "CausalAlphaFrontierControlCoverage", "CausalAlphaFrontierControlCoverageRow", "build_causal_alpha_frontier_control_coverage"]
