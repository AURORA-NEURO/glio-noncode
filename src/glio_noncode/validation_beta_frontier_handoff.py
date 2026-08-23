"""Reproducible research handoff for the validation-beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_fixture_eval import (
    ValidationBetaFrontierEvaluation,
    evaluate_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierFixture,
    ValidationBetaFrontierOperation,
    default_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_thresholds import (
    ValidationBetaFrontierThresholdReport,
    build_validation_beta_frontier_threshold_report,
)
from .validation_beta_frontier_validation_matrix import (
    ValidationBetaFrontierValidationMatrix,
    build_validation_beta_frontier_validation_matrix,
)


VALIDATION_BETA_FRONTIER_HANDOFF_VERSION = "2026.08.d13-c05-c12.handoff.v1"
VALIDATION_BETA_FRONTIER_ALLOWED_USES = (
    "research planning",
    "aggregate fixture validation",
    "control-path rehearsal",
    "software integration testing",
)
VALIDATION_BETA_FRONTIER_EXCLUDED_USES = (
    "clinical decision",
    "patient-level inference",
    "efficacy conclusion",
    "diagnostic classification",
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierHandoffItem:
    """Operation-level handoff accounting without copying payload values."""

    operation: ValidationBetaFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    review_count: int
    source_ids: tuple[str, ...]
    threshold_profile_id: str
    required_checks: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.record_count != self.positive_count + self.control_count:
            raise ValueError("handoff operation counts must conserve records")
        if not self.source_ids or not self.threshold_profile_id or not self.required_checks:
            raise ValueError("handoff operation metadata is incomplete")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("handoff operation address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierHandoff:
    """Closed handoff manifest linking data, tests, boundaries, and replays."""

    handoff_id: str
    version: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    threshold_report: ValidationBetaFrontierThresholdReport
    validation_matrix: ValidationBetaFrontierValidationMatrix
    operation_items: tuple[ValidationBetaFrontierHandoffItem, ...]
    source_ids: tuple[str, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    reproducibility_steps: tuple[str, ...]
    publication_surfaces: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def operation_count(self) -> int:
        return len(self.operation_items)

    @property
    def record_count(self) -> int:
        return sum(item.record_count for item in self.operation_items)

    def item(self, operation: ValidationBetaFrontierOperation | str) -> ValidationBetaFrontierHandoffItem:
        selected = operation.value if isinstance(operation, ValidationBetaFrontierOperation) else str(operation)
        for value in self.operation_items:
            if value.operation.value == selected:
                return value
        raise KeyError(selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "operation_count": self.operation_count,
            "record_count": self.record_count,
        }


_CHECKS = {
    ValidationBetaFrontierOperation.CRISPR_DESIGN: ("target-context", "mode-coverage", "guide-blockers"),
    ValidationBetaFrontierOperation.BASE_EDITING: ("edit-window", "base-pair", "reference-context"),
    ValidationBetaFrontierOperation.PRIME_EDITING: ("pbs", "rtt", "flank"),
    ValidationBetaFrontierOperation.ALLELE_REPORTER: ("allele-pair", "reporter-context", "replicate-plan"),
    ValidationBetaFrontierOperation.MODEL_ELIGIBILITY: ("context-exactness", "model-attributes", "subject-boundary"),
    ValidationBetaFrontierOperation.GUIDE_OLIGO: ("oligo-sequence", "gc-band", "manufacturing-boundary"),
    ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION: ("control-balance", "randomization", "seed-receipt"),
    ValidationBetaFrontierOperation.POWER_REPLICATION: ("power-inputs", "replication", "shortfall-boundary"),
}


def _item(
    operation: ValidationBetaFrontierOperation,
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
) -> ValidationBetaFrontierHandoffItem:
    records = fixture.operation_map()[operation]
    rows = evaluation.by_operation(operation)
    source_ids = tuple(sorted({source for record in records for source in record.source_ids}))
    body = {
        "operation": operation,
        "record_count": len(records),
        "positive_count": sum(record.role.value == "positive" for record in records),
        "control_count": sum(record.role.value == "control" for record in records),
        "accepted_count": sum(row.accepted for row in rows),
        "review_count": sum(row.observed_state != "ready_for_review" for row in rows),
        "source_ids": source_ids,
        "threshold_profile_id": f"threshold-{operation.value}",
        "required_checks": _CHECKS[operation],
    }
    return ValidationBetaFrontierHandoffItem(**body, content_address=content_hash(body))


def build_validation_beta_frontier_handoff(
    fixture: ValidationBetaFrontierFixture | None = None,
    evaluation: ValidationBetaFrontierEvaluation | None = None,
    *,
    handoff_id: str = "validation-beta-frontier-handoff",
) -> ValidationBetaFrontierHandoff:
    """Build an addressable handoff that can be replayed from public inputs."""

    require_non_empty(handoff_id, "handoff_id")
    value = fixture or default_validation_beta_frontier_fixture()
    report = evaluation or evaluate_validation_beta_frontier_fixture(value)
    thresholds = build_validation_beta_frontier_threshold_report()
    matrix = build_validation_beta_frontier_validation_matrix(value, report)
    items = tuple(_item(operation, value, report) for operation in ValidationBetaFrontierOperation)
    source_ids = tuple(sorted(source.source_id for source in value.sources))
    steps = (
        "load the checked-in public aggregate fixture",
        "verify source and fixture content addresses",
        "run all eight operation adapters against positive and control rows",
        "compare expected states and issue-code floors",
        "replay the same fixture with the same declared context",
        "inspect threshold probes and validation-plane cells",
        "publish only the bounded research handoff manifest",
    )
    surfaces = (
        "fixture-json",
        "evaluation-json",
        "threshold-report-json",
        "validation-matrix-json",
        "review-csv",
        "release-markdown",
    )
    accepted = bool(
        report.accepted
        and thresholds.accepted
        and matrix.accepted
        and len(items) == 8
        and len(source_ids) == len(value.sources)
    )
    body = {
        "handoff_id": handoff_id,
        "version": VALIDATION_BETA_FRONTIER_HANDOFF_VERSION,
        "fixture_id": value.fixture_id,
        "fixture_address": value.content_address,
        "evaluation_address": report.content_address,
        "threshold_report": thresholds,
        "validation_matrix": matrix,
        "operation_items": items,
        "source_ids": source_ids,
        "allowed_uses": VALIDATION_BETA_FRONTIER_ALLOWED_USES,
        "excluded_uses": VALIDATION_BETA_FRONTIER_EXCLUDED_USES,
        "reproducibility_steps": steps,
        "publication_surfaces": surfaces,
        "accepted": accepted,
    }
    return ValidationBetaFrontierHandoff(**body, content_address=content_hash(body))


def validate_validation_beta_frontier_handoff(handoff: ValidationBetaFrontierHandoff) -> bool:
    """Verify all operation, source, boundary, and surface closure rules."""

    if not handoff.accepted or handoff.version != VALIDATION_BETA_FRONTIER_HANDOFF_VERSION:
        return False
    if handoff.operation_count != 8 or handoff.record_count != 32:
        return False
    if len(handoff.source_ids) != 7 or not handoff.allowed_uses or not handoff.excluded_uses:
        return False
    if len(handoff.reproducibility_steps) != 7 or len(handoff.publication_surfaces) != 6:
        return False
    if not handoff.threshold_report.accepted or not handoff.validation_matrix.accepted:
        return False
    if {item.operation for item in handoff.operation_items} != set(ValidationBetaFrontierOperation):
        return False
    return all(item.content_address.startswith("sha256:") and item.accepted_count == 4 for item in handoff.operation_items)


def render_validation_beta_frontier_handoff_markdown(handoff: ValidationBetaFrontierHandoff | None = None) -> str:
    value = handoff or build_validation_beta_frontier_handoff()
    lines = [
        "# Validation-beta frontier research handoff",
        "",
        f"- Handoff: `{value.handoff_id}`",
        f"- Fixture: `{value.fixture_id}`",
        f"- Records: `{value.record_count}` across `{value.operation_count}` operations",
        f"- Accepted: `{validate_validation_beta_frontier_handoff(value)}`",
        "",
        "## Operation closure",
        "",
        "| Operation | Records | Positive | Controls | Review rows | Sources |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in value.operation_items:
        lines.append(f"| {item.operation.value} | {item.record_count} | {item.positive_count} | {item.control_count} | {item.review_count} | {len(item.source_ids)} |")
    lines.extend(("", "## Allowed uses", "", *[f"- {item}" for item in value.allowed_uses], "", "## Excluded uses", "", *[f"- {item}" for item in value.excluded_uses], "", "## Reproducibility", "", *[f"{index}. {item}" for index, item in enumerate(value.reproducibility_steps, 1)], ""))
    return "\n".join(lines)


def validation_beta_frontier_handoff_summary(handoff: ValidationBetaFrontierHandoff | None = None) -> dict[str, Any]:
    value = handoff or build_validation_beta_frontier_handoff()
    return {
        "accepted": validate_validation_beta_frontier_handoff(value),
        "handoff_id": value.handoff_id,
        "fixture_id": value.fixture_id,
        "operation_count": value.operation_count,
        "record_count": value.record_count,
        "source_count": len(value.source_ids),
        "publication_surface_count": len(value.publication_surfaces),
        "content_address": value.content_address,
    }


__all__ = [
    "VALIDATION_BETA_FRONTIER_ALLOWED_USES",
    "VALIDATION_BETA_FRONTIER_EXCLUDED_USES",
    "VALIDATION_BETA_FRONTIER_HANDOFF_VERSION",
    "ValidationBetaFrontierHandoff",
    "ValidationBetaFrontierHandoffItem",
    "build_validation_beta_frontier_handoff",
    "render_validation_beta_frontier_handoff_markdown",
    "validate_validation_beta_frontier_handoff",
    "validation_beta_frontier_handoff_summary",
]
