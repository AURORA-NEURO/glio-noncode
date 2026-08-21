"""Assay quality checks with explicit pass, watch, fail, and abstain states."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


class QCStatus(StrEnum):
    PASS = "pass"
    WATCH = "watch"
    FAIL = "fail"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class AssayQCObservation:
    """Declared QC metrics for one assay and sample."""

    assay_id: str
    sample_id: str
    assay_type: str
    usable_reads: int | None
    mapping_rate: float | None
    replicate_correlation: float | None
    contamination_rate: float | None
    controls_passed: bool | None
    source_id: str

    def __post_init__(self) -> None:
        for name in ("assay_id", "sample_id", "assay_type", "source_id"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"assay QC {name} is required")
        if self.usable_reads is not None and self.usable_reads < 0:
            raise ValidationError("usable_reads must not be negative")
        for name in ("mapping_rate", "replicate_correlation", "contamination_rate"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AssayQCResult:
    """Quality decision with every missing metric and threshold visible."""

    assay_id: str
    status: QCStatus
    metrics: dict[str, float | int | bool | None]
    issues: tuple[str, ...]
    source_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AssayQCEvaluator:
    """Apply conservative generic thresholds; assay-specific QC remains required."""

    def evaluate(self, observation: AssayQCObservation) -> AssayQCResult:
        metrics = {
            "usable_reads": observation.usable_reads,
            "mapping_rate": observation.mapping_rate,
            "replicate_correlation": observation.replicate_correlation,
            "contamination_rate": observation.contamination_rate,
            "controls_passed": observation.controls_passed,
        }
        missing = [key for key, value in metrics.items() if value is None]
        issues: list[str] = []
        if missing:
            issues.append("Missing QC metrics: " + ", ".join(missing))
        if observation.usable_reads is not None and observation.usable_reads < 100_000:
            issues.append("Usable read count is below the generic watch threshold of 100000.")
        if observation.mapping_rate is not None and observation.mapping_rate < 0.80:
            issues.append("Mapping rate is below the generic 0.80 watch threshold.")
        if (
            observation.replicate_correlation is not None
            and observation.replicate_correlation < 0.70
        ):
            issues.append("Replicate correlation is below the generic 0.70 watch threshold.")
        if observation.contamination_rate is not None and observation.contamination_rate > 0.05:
            issues.append("Contamination rate is above the generic 0.05 watch threshold.")
        if observation.controls_passed is False:
            issues.append("Declared assay controls did not pass.")
        if missing:
            status = QCStatus.ABSTAINED
        elif observation.controls_passed is False or (
            observation.mapping_rate is not None and observation.mapping_rate < 0.60
        ):
            status = QCStatus.FAIL
        elif issues:
            status = QCStatus.WATCH
        else:
            status = QCStatus.PASS
        payload = {
            "assay_id": observation.assay_id,
            "status": status,
            "metrics": metrics,
            "issues": tuple(issues),
            "source_id": observation.source_id,
        }
        return AssayQCResult(
            assay_id=observation.assay_id,
            status=status,
            metrics=metrics,
            issues=tuple(dict.fromkeys(issues)),
            source_id=observation.source_id,
            content_address=content_hash(payload),
        )

    def evaluate_many(
        self, observations: Iterable[AssayQCObservation]
    ) -> tuple[AssayQCResult, ...]:
        return tuple(self.evaluate(observation) for observation in observations)
