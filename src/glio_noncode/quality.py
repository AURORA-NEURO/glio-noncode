"""Release-quality metrics that expose calibration and review burden."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import Dossier, EvidenceState


class QualityBand(str, Enum):
    PASS = "pass"
    WATCH = "watch"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class QualityMetric:
    metric_id: str
    value: float | None
    target: str
    band: QualityBand
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "target": self.target,
            "band": self.band.value,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class QualityReport:
    metrics: tuple[QualityMetric, ...]
    release_ready: bool
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": [metric.to_dict() for metric in self.metrics],
            "release_ready": self.release_ready,
            "limitations": list(self.limitations),
        }


class QualityEvaluator:
    """Evaluate dossier health without substituting a single quality score."""

    def evaluate(self, dossier: Dossier) -> QualityReport:
        metrics = (
            self._metric("evidence_coverage", self._coverage(dossier), 0.75, "higher is better", "coverage of supported claims"),
            self._metric("context_specificity", self._context_specificity(dossier), 0.70, "higher is better", "share of claims with strong context match"),
            self._metric("uncertainty_transparency", self._uncertainty_transparency(dossier), 0.90, "higher is better", "share of hypotheses exposing uncertainty and missing evidence"),
            self._metric("review_burden", self._review_burden(dossier), 3.0, "lower is better", "number of candidates shown to a reviewer"),
            self._metric("negative_evidence_visibility", self._negative_visibility(dossier), 0.50, "higher is better", "share of dossiers retaining negative evidence when present"),
        )
        blocking = [metric for metric in metrics if metric.band == QualityBand.FAIL]
        return QualityReport(
            metrics=metrics,
            release_ready=not blocking and dossier.research_use_only,
            limitations=(
                "These are internal quality signals, not external scientific validation.",
                "Thresholds must be preregistered and evaluated on held-out data before claims are made.",
            ),
        )

    @staticmethod
    def _metric(metric_id: str, value: float | None, threshold: float, target: str, rationale: str) -> QualityMetric:
        if value is None:
            band = QualityBand.UNKNOWN
        elif target == "higher is better":
            band = QualityBand.PASS if value >= threshold else QualityBand.WATCH if value >= threshold * 0.75 else QualityBand.FAIL
        else:
            band = QualityBand.PASS if value <= threshold else QualityBand.WATCH if value <= threshold * 1.5 else QualityBand.FAIL
        return QualityMetric(metric_id, None if value is None else round(value, 6), target, band, rationale)

    @staticmethod
    def _coverage(dossier: Dossier) -> float | None:
        if not dossier.evidence:
            return None
        return sum(claim.state == EvidenceState.SUPPORTED for claim in dossier.evidence) / len(dossier.evidence)

    @staticmethod
    def _context_specificity(dossier: Dossier) -> float | None:
        matches = [claim.payload.get("context_match", {}).get("score") for claim in dossier.evidence]
        values = [float(value) for value in matches if isinstance(value, (int, float))]
        return sum(values) / len(values) if values else None

    @staticmethod
    def _uncertainty_transparency(dossier: Dossier) -> float:
        if not dossier.hypotheses:
            return 0.0
        visible = sum(bool(hypothesis.missing_evidence or hypothesis.uncertainty > 0) for hypothesis in dossier.hypotheses)
        return visible / len(dossier.hypotheses)

    @staticmethod
    def _review_burden(dossier: Dossier) -> float:
        return float(len(dossier.hypotheses))

    @staticmethod
    def _negative_visibility(dossier: Dossier) -> float:
        negatives = [claim for claim in dossier.evidence if claim.state in (EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY)]
        if not negatives:
            return 1.0
        return sum(bool(claim.summary and claim.payload) for claim in negatives) / len(negatives)
