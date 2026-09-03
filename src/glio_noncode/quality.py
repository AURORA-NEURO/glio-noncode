"""Bounded, deterministic release-quality metrics for research dossiers.

Quality signals describe evidence and review burden; they do not replace dossier
contract validation or the release gate. In particular, an unavailable metric is
not evidence that a release criterion passed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import cast

from .errors import ValidationError
from .models import Dossier, EvidenceClaim, EvidenceState
from .serialization import canonical_bytes, content_hash
from .validation import ContractValidator, ReleaseGate, ValidationLimits

_HARD_MAX_QUALITY_HYPOTHESES = 10_000
_HARD_MAX_QUALITY_EVIDENCE_CLAIMS = 20_000
_HARD_MAX_QUALITY_METRICS = 32
_HARD_MAX_QUALITY_LIMITATIONS = 32
_HARD_MAX_QUALITY_GATE_ISSUE_CODES = 64
_HARD_MAX_QUALITY_TEXT_CHARACTERS = 4_096
_HARD_MAX_QUALITY_TOTAL_TEXT_CHARACTERS = 65_536
_HARD_MAX_QUALITY_REPORT_BYTES = 262_144

# Public ceilings let callers construct downward-scoped limits. Private copies
# remain authoritative if a module attribute is rebound.
MAX_QUALITY_HYPOTHESES = _HARD_MAX_QUALITY_HYPOTHESES
MAX_QUALITY_EVIDENCE_CLAIMS = _HARD_MAX_QUALITY_EVIDENCE_CLAIMS
MAX_QUALITY_METRICS = _HARD_MAX_QUALITY_METRICS
MAX_QUALITY_LIMITATIONS = _HARD_MAX_QUALITY_LIMITATIONS
MAX_QUALITY_GATE_ISSUE_CODES = _HARD_MAX_QUALITY_GATE_ISSUE_CODES
MAX_QUALITY_TEXT_CHARACTERS = _HARD_MAX_QUALITY_TEXT_CHARACTERS
MAX_QUALITY_TOTAL_TEXT_CHARACTERS = _HARD_MAX_QUALITY_TOTAL_TEXT_CHARACTERS
MAX_QUALITY_REPORT_BYTES = _HARD_MAX_QUALITY_REPORT_BYTES

_HIGHER_IS_BETTER = "higher is better"
_LOWER_IS_BETTER = "lower is better"
_TARGETS = frozenset({_HIGHER_IS_BETTER, _LOWER_IS_BETTER})

QUALITY_METRIC_IDS = (
    "evidence_coverage",
    "context_specificity",
    "uncertainty_transparency",
    "review_burden",
    "negative_evidence_visibility",
)
QUALITY_THRESHOLD_VERSION = "quality-thresholds-2026.09"
QUALITY_REPORT_VERSION = "quality-report-2026.09"
_METRIC_ORDER = {metric_id: index for index, metric_id in enumerate(QUALITY_METRIC_IDS)}
_REQUIRED_METRIC_IDS = frozenset(QUALITY_METRIC_IDS)
_METRIC_TARGETS = {
    "evidence_coverage": _HIGHER_IS_BETTER,
    "context_specificity": _HIGHER_IS_BETTER,
    "uncertainty_transparency": _HIGHER_IS_BETTER,
    "review_burden": _LOWER_IS_BETTER,
    "negative_evidence_visibility": _HIGHER_IS_BETTER,
}
_METRIC_RATIONALES = {
    "evidence_coverage": "share of typed hypothesis edges with active supported evidence",
    "context_specificity": (
        "share of evidence-bearing typed edges whose active claims exactly match hypothesis context"
    ),
    "uncertainty_transparency": (
        "share of hypotheses carrying an explicit bounded uncertainty field"
    ),
    "review_burden": "number of candidates shown to a reviewer",
    "negative_evidence_visibility": (
        "share of negative-evidence edges whose active negative claims all retain documentation"
    ),
}
_METRIC_THRESHOLD_FIELDS = {
    "evidence_coverage": "evidence_coverage",
    "context_specificity": "context_specificity",
    "uncertainty_transparency": "uncertainty_transparency",
    "review_burden": "review_burden",
    "negative_evidence_visibility": "negative_evidence_visibility",
}
_PROPORTION_METRIC_IDS = frozenset(
    {
        "evidence_coverage",
        "context_specificity",
        "uncertainty_transparency",
        "negative_evidence_visibility",
    }
)
_CANONICAL_RELEASE_POLICY_VERSION = ReleaseGate().policy.version

_BASE_LIMITATIONS = (
    "These are internal quality signals, not external scientific validation.",
    "Thresholds must be preregistered and evaluated on held-out data before claims are made.",
)


def _bounded_positive_integer(value: object, field_name: str, ceiling: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValidationError(f"{field_name} must be positive")
    if value > ceiling:
        raise ValidationError(f"{field_name} exceeds the safety ceiling of {ceiling}")
    return value


def _finite_number(value: object, field_name: str) -> float:
    if type(value) not in {int, float}:
        raise ValidationError(f"{field_name} must be a finite number")
    try:
        result = float(cast("int | float", value))
    except OverflowError as exc:
        raise ValidationError(f"{field_name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{field_name} must be a finite number")
    return 0.0 if result == 0.0 else result


def _bounded_text(value: object, field_name: str, maximum: int) -> str:
    if type(value) is not str:
        raise ValidationError(f"{field_name} must be a string")
    if len(value) > maximum:
        raise ValidationError(f"{field_name} exceeds the safety ceiling of {maximum} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{field_name} must be valid UTF-8 text") from exc
    if not value.strip():
        raise ValidationError(f"{field_name} must not be empty")
    return value


def _bounded_identifier(value: object, field_name: str, maximum: int = 128) -> str:
    identifier = _bounded_text(
        value,
        field_name,
        maximum,
    )
    if identifier[0] not in "abcdefghijklmnopqrstuvwxyz" or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in identifier
    ):
        raise ValidationError(f"{field_name} must be a lowercase ASCII identifier")
    return identifier


def _metric_identifier(value: object) -> str:
    return _bounded_identifier(value, "quality metric metric_id")


def _sha256_address(value: object, field_name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValidationError(f"{field_name} must be a canonical sha256 content address")
    return value


@dataclass(frozen=True, slots=True)
class QualityLimits:
    """Immutable, downward-configurable work and report limits."""

    max_hypotheses: int = MAX_QUALITY_HYPOTHESES
    max_evidence_claims: int = MAX_QUALITY_EVIDENCE_CLAIMS
    max_metrics: int = MAX_QUALITY_METRICS
    max_limitations: int = MAX_QUALITY_LIMITATIONS
    max_gate_issue_codes: int = MAX_QUALITY_GATE_ISSUE_CODES
    max_text_characters: int = MAX_QUALITY_TEXT_CHARACTERS
    max_total_text_characters: int = MAX_QUALITY_TOTAL_TEXT_CHARACTERS
    max_report_bytes: int = MAX_QUALITY_REPORT_BYTES

    def __post_init__(self) -> None:
        for field_name, ceiling in (
            ("max_hypotheses", _HARD_MAX_QUALITY_HYPOTHESES),
            ("max_evidence_claims", _HARD_MAX_QUALITY_EVIDENCE_CLAIMS),
            ("max_metrics", _HARD_MAX_QUALITY_METRICS),
            ("max_limitations", _HARD_MAX_QUALITY_LIMITATIONS),
            ("max_gate_issue_codes", _HARD_MAX_QUALITY_GATE_ISSUE_CODES),
            ("max_text_characters", _HARD_MAX_QUALITY_TEXT_CHARACTERS),
            ("max_total_text_characters", _HARD_MAX_QUALITY_TOTAL_TEXT_CHARACTERS),
            ("max_report_bytes", _HARD_MAX_QUALITY_REPORT_BYTES),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_positive_integer(getattr(self, field_name), field_name, ceiling),
            )


DEFAULT_QUALITY_LIMITS = QualityLimits()


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    """Preregisterable thresholds used to classify the five dimensions."""

    evidence_coverage: float = 0.75
    context_specificity: float = 0.70
    uncertainty_transparency: float = 0.90
    review_burden: float = 3.0
    negative_evidence_visibility: float = 0.50
    higher_watch_fraction: float = 0.75
    lower_watch_multiplier: float = 1.50
    content_address: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_coverage",
            "context_specificity",
            "uncertainty_transparency",
            "negative_evidence_visibility",
        ):
            value = _finite_number(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{field_name} must be between 0 and 1")
            object.__setattr__(self, field_name, value)

        review_burden = _finite_number(self.review_burden, "review_burden")
        if not 0.0 < review_burden <= _HARD_MAX_QUALITY_HYPOTHESES:
            raise ValidationError(
                "review_burden must be positive and within the hypothesis safety ceiling"
            )
        object.__setattr__(self, "review_burden", review_burden)

        higher_watch_fraction = _finite_number(
            self.higher_watch_fraction,
            "higher_watch_fraction",
        )
        if not 0.0 < higher_watch_fraction <= 1.0:
            raise ValidationError("higher_watch_fraction must be greater than 0 and at most 1")
        object.__setattr__(self, "higher_watch_fraction", higher_watch_fraction)

        lower_watch_multiplier = _finite_number(
            self.lower_watch_multiplier,
            "lower_watch_multiplier",
        )
        if not 1.0 <= lower_watch_multiplier <= 10.0:
            raise ValidationError("lower_watch_multiplier must be between 1 and 10")
        object.__setattr__(self, "lower_watch_multiplier", lower_watch_multiplier)

        object.__setattr__(self, "content_address", content_hash(_threshold_body(self)))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> QualityThresholds:
        """Parse an exact, content-addressed threshold snapshot."""

        if type(raw) is not dict:
            raise ValidationError("quality thresholds must be an object")
        expected = {
            "version",
            "evidence_coverage",
            "context_specificity",
            "uncertainty_transparency",
            "review_burden",
            "negative_evidence_visibility",
            "higher_watch_fraction",
            "lower_watch_multiplier",
            "content_address",
        }
        if (
            len(raw) != len(expected)
            or set(raw) != expected
            or any(type(key) is not str for key in raw)
        ):
            raise ValidationError("quality threshold fields must be exact")
        if type(raw["version"]) is not str or raw["version"] != QUALITY_THRESHOLD_VERSION:
            raise ValidationError("quality threshold version is unsupported")
        numeric_fields = expected - {"version", "content_address"}
        if any(type(raw[field_name]) is not float for field_name in numeric_fields):
            raise ValidationError("canonical quality threshold values must be floats")
        value = cls(
            evidence_coverage=raw["evidence_coverage"],  # type: ignore[arg-type]
            context_specificity=raw["context_specificity"],  # type: ignore[arg-type]
            uncertainty_transparency=raw["uncertainty_transparency"],  # type: ignore[arg-type]
            review_burden=raw["review_burden"],  # type: ignore[arg-type]
            negative_evidence_visibility=raw[  # type: ignore[arg-type]
                "negative_evidence_visibility"
            ],
            higher_watch_fraction=raw["higher_watch_fraction"],  # type: ignore[arg-type]
            lower_watch_multiplier=raw["lower_watch_multiplier"],  # type: ignore[arg-type]
        )
        supplied_address = _sha256_address(
            raw["content_address"],
            "quality threshold content_address",
        )
        if supplied_address != value.content_address:
            raise ValidationError("quality threshold content_address does not match its payload")
        if canonical_bytes(raw) != canonical_bytes(value.to_dict()):
            raise ValidationError("quality thresholds are not an exact canonical representation")
        return value

    def to_dict(self) -> dict[str, object]:
        checked = _validated_thresholds(self)
        return _threshold_body(checked) | {"content_address": checked.content_address}


def _threshold_body(value: QualityThresholds) -> dict[str, object]:
    return {
        "version": QUALITY_THRESHOLD_VERSION,
        "evidence_coverage": value.evidence_coverage,
        "context_specificity": value.context_specificity,
        "uncertainty_transparency": value.uncertainty_transparency,
        "review_burden": value.review_burden,
        "negative_evidence_visibility": value.negative_evidence_visibility,
        "higher_watch_fraction": value.higher_watch_fraction,
        "lower_watch_multiplier": value.lower_watch_multiplier,
    }


def _validated_limits(value: object) -> QualityLimits:
    if type(value) is not QualityLimits:
        raise ValidationError("limits must be an exact QualityLimits object")
    return QualityLimits(**{item.name: getattr(value, item.name) for item in fields(QualityLimits)})


def _validated_thresholds(value: object) -> QualityThresholds:
    if type(value) is not QualityThresholds:
        raise ValidationError("thresholds must be an exact QualityThresholds object")
    checked = QualityThresholds(
        **{item.name: getattr(value, item.name) for item in fields(QualityThresholds) if item.init}
    )
    supplied_address = _sha256_address(
        value.content_address,
        "quality threshold content_address",
    )
    if supplied_address != checked.content_address:
        raise ValidationError("quality threshold content_address does not match its payload")
    return checked


DEFAULT_QUALITY_THRESHOLDS = QualityThresholds()


class QualityBand(str, Enum):  # noqa: UP042 - preserve historical string-enum behavior
    PASS = "pass"
    WATCH = "watch"
    FAIL = "fail"
    UNKNOWN = "unknown"


def _expected_metric_band(
    metric_id: str,
    value: float | None,
    thresholds: QualityThresholds,
) -> QualityBand:
    if value is None:
        return QualityBand.UNKNOWN
    threshold = float(getattr(thresholds, _METRIC_THRESHOLD_FIELDS[metric_id]))
    if _METRIC_TARGETS[metric_id] == _HIGHER_IS_BETTER:
        if value >= threshold:
            return QualityBand.PASS
        if value >= threshold * thresholds.higher_watch_fraction:
            return QualityBand.WATCH
        return QualityBand.FAIL
    if value <= threshold:
        return QualityBand.PASS
    if value <= threshold * thresholds.lower_watch_multiplier:
        return QualityBand.WATCH
    return QualityBand.FAIL


@dataclass(frozen=True, slots=True)
class QualityMetric:
    metric_id: str
    value: float | None
    target: str
    band: QualityBand
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _metric_identifier(self.metric_id))
        if type(self.band) is not QualityBand:
            raise ValidationError("quality metric band must be an exact QualityBand")
        if self.value is None:
            if self.band is not QualityBand.UNKNOWN:
                raise ValidationError("a quality metric without a value must have band UNKNOWN")
        else:
            value = _finite_number(self.value, "quality metric value")
            if value < 0.0:
                raise ValidationError("quality metric value must not be negative")
            if self.band is QualityBand.UNKNOWN:
                raise ValidationError("an UNKNOWN quality metric must not carry a value")
            object.__setattr__(self, "value", value)
        if type(self.target) is not str or self.target not in _TARGETS:
            raise ValidationError(
                "quality metric target must be 'higher is better' or 'lower is better'"
            )
        object.__setattr__(
            self,
            "rationale",
            _bounded_text(
                self.rationale,
                "quality metric rationale",
                _HARD_MAX_QUALITY_TEXT_CHARACTERS,
            ),
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> QualityMetric:
        """Parse the exact canonical JSON representation of one metric."""

        if type(raw) is not dict:
            raise ValidationError("quality metric must be an object")
        expected = {"metric_id", "value", "target", "band", "rationale"}
        if (
            len(raw) != len(expected)
            or set(raw) != expected
            or any(type(key) is not str for key in raw)
        ):
            raise ValidationError("quality metric fields must be exact")
        band_raw = raw["band"]
        if type(band_raw) is not str:
            raise ValidationError("quality metric band must be a string")
        value_raw = raw["value"]
        if value_raw is not None and type(value_raw) is not float:
            raise ValidationError("canonical quality metric value must be a float or null")
        try:
            band = QualityBand(band_raw)
        except ValueError as exc:
            raise ValidationError(f"unsupported quality metric band {band_raw!r}") from exc
        metric = cls(
            metric_id=raw["metric_id"],  # type: ignore[arg-type]
            value=value_raw,
            target=raw["target"],  # type: ignore[arg-type]
            band=band,
            rationale=raw["rationale"],  # type: ignore[arg-type]
        )
        if canonical_bytes(raw) != canonical_bytes(metric.to_dict()):
            raise ValidationError("quality metric is not an exact canonical representation")
        return metric

    def to_dict(self) -> dict[str, object]:
        _validate_metric(self)
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "target": self.target,
            "band": self.band.value,
            "rationale": self.rationale,
        }


def _validate_metric(metric: object) -> QualityMetric:
    if type(metric) is not QualityMetric:
        raise ValidationError("report metrics must be exact QualityMetric objects")
    if metric.value is not None and type(metric.value) is not float:
        raise ValidationError("canonical quality metric value must be a float or null")
    # Reconstruction also detects mutation performed through object.__setattr__.
    return QualityMetric(
        metric_id=metric.metric_id,
        value=metric.value,
        target=metric.target,
        band=metric.band,
        rationale=metric.rationale,
    )


def _validate_metric_semantics(
    metric: QualityMetric,
    thresholds: QualityThresholds,
    limits: QualityLimits,
) -> None:
    expected_target = _METRIC_TARGETS[metric.metric_id]
    if metric.target != expected_target:
        raise ValidationError(
            f"quality metric {metric.metric_id} must use target {expected_target!r}"
        )
    expected_rationale = _METRIC_RATIONALES[metric.metric_id]
    if metric.rationale != expected_rationale:
        raise ValidationError(f"quality metric {metric.metric_id} rationale is not canonical")
    if metric.value is not None:
        if metric.metric_id in _PROPORTION_METRIC_IDS and not 0.0 <= metric.value <= 1.0:
            raise ValidationError(
                f"quality metric {metric.metric_id} must be a proportion between 0 and 1"
            )
        if metric.metric_id == "review_burden" and (
            metric.value > limits.max_hypotheses or not metric.value.is_integer()
        ):
            raise ValidationError(
                "quality metric review_burden must be an integral count within the hypothesis limit"
            )
    expected_band = _expected_metric_band(metric.metric_id, metric.value, thresholds)
    if metric.band is not expected_band:
        raise ValidationError(
            f"quality metric {metric.metric_id} band does not match its value and thresholds"
        )


def _metric_order_key(metric: QualityMetric) -> tuple[int, str]:
    return (_METRIC_ORDER.get(metric.metric_id, len(_METRIC_ORDER)), metric.metric_id)


def _report_body(
    dossier_address: str,
    thresholds: QualityThresholds,
    release_gate_valid: bool,
    release_gate_issue_codes: tuple[str, ...],
    release_policy_version: str,
    metrics: tuple[QualityMetric, ...],
    release_ready: bool,
    limitations: tuple[str, ...],
) -> dict[str, object]:
    return {
        "version": QUALITY_REPORT_VERSION,
        "dossier_address": dossier_address,
        "thresholds": thresholds.to_dict(),
        "release_gate_valid": release_gate_valid,
        "release_gate_issue_codes": list(release_gate_issue_codes),
        "release_policy_version": release_policy_version,
        "metrics": [metric.to_dict() for metric in metrics],
        "release_ready": release_ready,
        "limitations": list(limitations),
    }


def _summarize_codes(codes: tuple[str, ...]) -> str:
    displayed = codes[:8]
    suffix = "" if len(codes) <= 8 else f" (+{len(codes) - 8} more)"
    return ", ".join(displayed) + suffix


def _expected_limitations(
    metrics: tuple[QualityMetric, ...],
    release_gate_valid: bool,
    release_gate_issue_codes: tuple[str, ...],
) -> tuple[str, ...]:
    limitations = list(_BASE_LIMITATIONS)
    unknown = tuple(metric.metric_id for metric in metrics if metric.band is QualityBand.UNKNOWN)
    failed = tuple(metric.metric_id for metric in metrics if metric.band is QualityBand.FAIL)
    if unknown:
        limitations.append(
            "Unknown required metrics block release readiness: " + ", ".join(unknown) + "."
        )
    if failed:
        limitations.append(
            "Quality metrics below their failure thresholds block release readiness: "
            + ", ".join(failed)
            + "."
        )
    if not release_gate_valid:
        limitations.append(
            "The authoritative release gate did not pass: "
            + _summarize_codes(release_gate_issue_codes)
            + "."
        )
    elif release_gate_issue_codes:
        limitations.append(
            "Authoritative release gate warnings remain visible: "
            + _summarize_codes(release_gate_issue_codes)
            + "."
        )
    return tuple(limitations)


def _validate_report_components(
    dossier_address: object,
    thresholds: object,
    release_gate_valid: object,
    release_gate_issue_codes: object,
    release_policy_version: object,
    metrics: object,
    release_ready: object,
    limitations: object,
    limits: QualityLimits,
) -> tuple[
    str,
    QualityThresholds,
    bool,
    tuple[str, ...],
    str,
    tuple[QualityMetric, ...],
    bool,
    tuple[str, ...],
]:
    checked_dossier_address = _sha256_address(dossier_address, "quality dossier_address")
    checked_thresholds = _validated_thresholds(thresholds)
    if type(release_gate_valid) is not bool:
        raise ValidationError("quality report release_gate_valid must be a boolean")
    if type(release_gate_issue_codes) is not tuple:
        raise ValidationError("quality report release_gate_issue_codes must be a tuple")
    if len(release_gate_issue_codes) > limits.max_gate_issue_codes:
        raise ValidationError(
            "quality report exceeds the configured maximum of "
            f"{limits.max_gate_issue_codes} release-gate issue codes"
        )
    checked_gate_codes = tuple(
        _bounded_identifier(item, f"quality release_gate_issue_codes[{index}]")
        for index, item in enumerate(release_gate_issue_codes)
    )
    if len(checked_gate_codes) != len(set(checked_gate_codes)):
        raise ValidationError("quality report release_gate_issue_codes must be unique")
    checked_gate_codes = tuple(sorted(checked_gate_codes))
    if not release_gate_valid and not checked_gate_codes:
        raise ValidationError("a failed quality release gate must retain at least one issue code")
    checked_policy_version = _bounded_text(
        release_policy_version,
        "quality report release_policy_version",
        128,
    )
    if checked_policy_version != _CANONICAL_RELEASE_POLICY_VERSION:
        raise ValidationError("quality report release_policy_version is not canonical")
    if type(metrics) is not tuple:
        raise ValidationError("quality report metrics must be a tuple")
    if not metrics:
        raise ValidationError("quality report must contain at least one metric")
    if len(metrics) > limits.max_metrics:
        raise ValidationError(
            f"quality report exceeds the configured maximum of {limits.max_metrics} metrics"
        )
    checked_metrics = tuple(_validate_metric(metric) for metric in metrics)
    metric_ids = tuple(metric.metric_id for metric in checked_metrics)
    if len(metric_ids) != len(set(metric_ids)):
        raise ValidationError("quality report metric_id values must be unique")
    missing = _REQUIRED_METRIC_IDS - set(metric_ids)
    unexpected = set(metric_ids) - _REQUIRED_METRIC_IDS
    if missing or unexpected:
        raise ValidationError(
            "quality report metric identities must be exact "
            f"(missing={sorted(missing)}, unexpected={sorted(unexpected)})"
        )
    for metric in checked_metrics:
        _validate_metric_semantics(metric, checked_thresholds, limits)

    if type(release_ready) is not bool:
        raise ValidationError("quality report release_ready must be a boolean")
    blocked = tuple(
        metric.metric_id
        for metric in checked_metrics
        if metric.band in {QualityBand.FAIL, QualityBand.UNKNOWN}
    )
    expected_ready = release_gate_valid and not blocked
    if release_ready is not expected_ready:
        raise ValidationError(
            "quality report release_ready does not match its gate and metric decisions"
        )

    if type(limitations) is not tuple:
        raise ValidationError("quality report limitations must be a tuple")
    if len(limitations) > limits.max_limitations:
        raise ValidationError(
            f"quality report exceeds the configured maximum of {limits.max_limitations} limitations"
        )
    checked_limitations = tuple(
        _bounded_text(item, f"quality report limitations[{index}]", limits.max_text_characters)
        for index, item in enumerate(limitations)
    )
    if len(checked_limitations) != len(set(checked_limitations)):
        raise ValidationError("quality report limitations must be unique")
    expected_limitations = _expected_limitations(
        tuple(sorted(checked_metrics, key=_metric_order_key)),
        release_gate_valid,
        checked_gate_codes,
    )
    if checked_limitations != expected_limitations:
        raise ValidationError("quality report limitations are not the canonical decision summary")

    texts = (
        QUALITY_REPORT_VERSION,
        checked_dossier_address,
        checked_policy_version,
        *checked_gate_codes,
        *(metric.metric_id for metric in checked_metrics),
        *(metric.target for metric in checked_metrics),
        *(metric.rationale for metric in checked_metrics),
        *checked_limitations,
    )
    for index, text in enumerate(texts):
        _bounded_text(text, f"quality report text[{index}]", limits.max_text_characters)
    total_characters = sum(len(text) for text in texts)
    if total_characters > limits.max_total_text_characters:
        raise ValidationError(
            "quality report text exceeds the configured maximum of "
            f"{limits.max_total_text_characters} characters"
        )
    return (
        checked_dossier_address,
        checked_thresholds,
        release_gate_valid,
        checked_gate_codes,
        checked_policy_version,
        checked_metrics,
        release_ready,
        checked_limitations,
    )


@dataclass(frozen=True, slots=True)
class QualityReport:
    dossier_address: str
    thresholds: QualityThresholds
    release_gate_valid: bool
    release_gate_issue_codes: tuple[str, ...]
    release_policy_version: str
    metrics: tuple[QualityMetric, ...]
    release_ready: bool
    limitations: tuple[str, ...]
    content_address: str = field(init=False)

    def __post_init__(self) -> None:
        hard_limits = _validated_limits(DEFAULT_QUALITY_LIMITS)
        (
            dossier_address,
            thresholds,
            release_gate_valid,
            release_gate_issue_codes,
            release_policy_version,
            metrics,
            release_ready,
            limitations,
        ) = _validate_report_components(
            self.dossier_address,
            self.thresholds,
            self.release_gate_valid,
            self.release_gate_issue_codes,
            self.release_policy_version,
            self.metrics,
            self.release_ready,
            self.limitations,
            hard_limits,
        )
        ordered = tuple(sorted(metrics, key=_metric_order_key))
        object.__setattr__(self, "dossier_address", dossier_address)
        object.__setattr__(self, "thresholds", thresholds)
        object.__setattr__(self, "release_gate_valid", release_gate_valid)
        object.__setattr__(self, "release_gate_issue_codes", release_gate_issue_codes)
        object.__setattr__(self, "release_policy_version", release_policy_version)
        object.__setattr__(self, "metrics", ordered)
        object.__setattr__(self, "release_ready", release_ready)
        object.__setattr__(self, "limitations", limitations)
        body = _report_body(
            dossier_address,
            thresholds,
            release_gate_valid,
            release_gate_issue_codes,
            release_policy_version,
            ordered,
            release_ready,
            limitations,
        )
        address = content_hash(body)
        if (
            len(canonical_bytes(body | {"content_address": address}))
            > _HARD_MAX_QUALITY_REPORT_BYTES
        ):
            raise ValidationError("quality report exceeds the hard serialized-size ceiling")
        object.__setattr__(self, "content_address", address)

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> QualityReport:
        """Rehydrate an exact, content-addressed (but still untrusted) report.

        Content addressing detects payload corruption; callers that have the
        claimed dossier must additionally call :meth:`verify` to authenticate
        the recomputed quality decision against that subject.
        """

        if type(raw) is not dict:
            raise ValidationError("quality report must be an object")
        expected = {
            "version",
            "dossier_address",
            "thresholds",
            "release_gate_valid",
            "release_gate_issue_codes",
            "release_policy_version",
            "metrics",
            "release_ready",
            "limitations",
            "content_address",
        }
        if (
            len(raw) != len(expected)
            or set(raw) != expected
            or any(type(key) is not str for key in raw)
        ):
            raise ValidationError("quality report fields must be exact")
        if type(raw["version"]) is not str or raw["version"] != QUALITY_REPORT_VERSION:
            raise ValidationError("quality report version is unsupported")
        metrics_raw = raw["metrics"]
        limitations_raw = raw["limitations"]
        gate_codes_raw = raw["release_gate_issue_codes"]
        thresholds_raw = raw["thresholds"]
        if type(metrics_raw) is not list:
            raise ValidationError("quality report metrics must be a JSON array")
        if type(limitations_raw) is not list:
            raise ValidationError("quality report limitations must be a JSON array")
        if type(gate_codes_raw) is not list:
            raise ValidationError("quality report release_gate_issue_codes must be a JSON array")
        if type(thresholds_raw) is not dict:
            raise ValidationError("quality report thresholds must be an object")
        if len(metrics_raw) > _HARD_MAX_QUALITY_METRICS:
            raise ValidationError("quality report metrics exceed the hard cardinality ceiling")
        if len(limitations_raw) > _HARD_MAX_QUALITY_LIMITATIONS:
            raise ValidationError("quality report limitations exceed the hard cardinality ceiling")
        if len(gate_codes_raw) > _HARD_MAX_QUALITY_GATE_ISSUE_CODES:
            raise ValidationError(
                "quality report release_gate_issue_codes exceed the hard cardinality ceiling"
            )
        metrics = tuple(QualityMetric.from_dict(item) for item in metrics_raw)
        report = cls(
            dossier_address=raw["dossier_address"],  # type: ignore[arg-type]
            thresholds=QualityThresholds.from_dict(thresholds_raw),
            release_gate_valid=raw["release_gate_valid"],  # type: ignore[arg-type]
            release_gate_issue_codes=tuple(gate_codes_raw),  # type: ignore[arg-type]
            release_policy_version=raw["release_policy_version"],  # type: ignore[arg-type]
            metrics=metrics,
            release_ready=raw["release_ready"],  # type: ignore[arg-type]
            limitations=tuple(limitations_raw),  # type: ignore[arg-type]
        )
        supplied_address = _sha256_address(raw["content_address"], "quality content_address")
        if supplied_address != report.content_address:
            raise ValidationError("quality report content_address does not match its payload")
        if canonical_bytes(raw) != canonical_bytes(report.to_dict()):
            raise ValidationError("quality report is not an exact canonical representation")
        return report

    def verify(self, dossier: Dossier) -> bool:
        """Recompute this untrusted assertion against its claimed dossier subject."""

        try:
            if type(dossier) is not Dossier or dossier.content_address != self.dossier_address:
                return False
            claimed = canonical_bytes(self.to_dict())
            expected = QualityEvaluator(thresholds=self.thresholds).evaluate(dossier)
            return claimed == canonical_bytes(expected.to_dict())
        except Exception:  # noqa: BLE001 - verification is intentionally fail closed
            return False

    def to_dict(self) -> dict[str, object]:
        limits = _validated_limits(DEFAULT_QUALITY_LIMITS)
        (
            dossier_address,
            thresholds,
            release_gate_valid,
            release_gate_issue_codes,
            release_policy_version,
            metrics,
            release_ready,
            limitations,
        ) = _validate_report_components(
            self.dossier_address,
            self.thresholds,
            self.release_gate_valid,
            self.release_gate_issue_codes,
            self.release_policy_version,
            self.metrics,
            self.release_ready,
            self.limitations,
            limits,
        )
        if metrics != tuple(sorted(metrics, key=_metric_order_key)):
            raise ValidationError("quality report metrics are not in canonical order")
        body = _report_body(
            dossier_address,
            thresholds,
            release_gate_valid,
            release_gate_issue_codes,
            release_policy_version,
            metrics,
            release_ready,
            limitations,
        )
        expected_address = content_hash(body)
        supplied_address = _sha256_address(self.content_address, "quality content_address")
        if supplied_address != expected_address:
            raise ValidationError("quality report content_address does not match its payload")
        payload = body | {"content_address": supplied_address}
        if len(canonical_bytes(payload)) > limits.max_report_bytes:
            raise ValidationError("quality report exceeds the hard serialized-size ceiling")
        return payload


def _enforce_report_limits(report: QualityReport, limits: QualityLimits) -> None:
    (
        dossier_address,
        thresholds,
        release_gate_valid,
        release_gate_issue_codes,
        release_policy_version,
        metrics,
        release_ready,
        limitations,
    ) = _validate_report_components(
        report.dossier_address,
        report.thresholds,
        report.release_gate_valid,
        report.release_gate_issue_codes,
        report.release_policy_version,
        report.metrics,
        report.release_ready,
        report.limitations,
        limits,
    )
    payload = _report_body(
        dossier_address,
        thresholds,
        release_gate_valid,
        release_gate_issue_codes,
        release_policy_version,
        metrics,
        release_ready,
        limitations,
    ) | {"content_address": report.content_address}
    if len(canonical_bytes(payload)) > limits.max_report_bytes:
        raise ValidationError(
            "quality report exceeds the configured maximum of "
            f"{limits.max_report_bytes} serialized bytes"
        )


class QualityEvaluator:
    """Evaluate dossier health without substituting a single quality score."""

    __slots__ = ("limits", "thresholds")

    def __init__(
        self,
        *,
        limits: QualityLimits | None = None,
        thresholds: QualityThresholds | None = None,
    ) -> None:
        selected_limits = DEFAULT_QUALITY_LIMITS if limits is None else limits
        selected_thresholds = DEFAULT_QUALITY_THRESHOLDS if thresholds is None else thresholds
        self.limits = _validated_limits(selected_limits)
        self.thresholds = _validated_thresholds(selected_thresholds)

    def evaluate(self, dossier: Dossier) -> QualityReport:
        limits = _validated_limits(self.limits)
        thresholds = _validated_thresholds(self.thresholds)
        if type(dossier) is not Dossier:
            raise ValidationError("dossier must be an exact Dossier object")
        if len(QUALITY_METRIC_IDS) > limits.max_metrics:
            raise ValidationError(
                f"quality evaluation requires {len(QUALITY_METRIC_IDS)} metric slots"
            )

        validation_limits = ValidationLimits(
            max_hypotheses=limits.max_hypotheses,
            max_evidence_claims=limits.max_evidence_claims,
        )
        validation_report = ContractValidator(limits=validation_limits).validate_dossier(dossier)
        if not validation_report.valid:
            codes = sorted({issue.code for issue in validation_report.issues})[:8]
            raise ValidationError(
                "dossier failed canonical contract validation before quality evaluation: "
                + ", ".join(codes)
            )
        release_gate = ReleaseGate(limits=validation_limits)
        gate_report = release_gate.check(dossier)
        gate_valid = gate_report.valid
        release_policy_version = _bounded_text(
            release_gate.policy.version,
            "release gate policy version",
            128,
        )
        gate_codes = tuple(sorted({issue.code for issue in gate_report.issues}))
        if len(gate_codes) > limits.max_gate_issue_codes:
            raise ValidationError(
                "authoritative release gate issue codes exceed the configured maximum of "
                f"{limits.max_gate_issue_codes}"
            )
        active_evidence = self._active_evidence(dossier)

        metrics = (
            self._metric(
                "evidence_coverage",
                self._coverage(dossier, active_evidence),
                thresholds.evidence_coverage,
                _METRIC_TARGETS["evidence_coverage"],
                _METRIC_RATIONALES["evidence_coverage"],
                thresholds,
            ),
            self._metric(
                "context_specificity",
                self._context_specificity(dossier, active_evidence),
                thresholds.context_specificity,
                _METRIC_TARGETS["context_specificity"],
                _METRIC_RATIONALES["context_specificity"],
                thresholds,
            ),
            self._metric(
                "uncertainty_transparency",
                self._uncertainty_transparency(dossier),
                thresholds.uncertainty_transparency,
                _METRIC_TARGETS["uncertainty_transparency"],
                _METRIC_RATIONALES["uncertainty_transparency"],
                thresholds,
            ),
            self._metric(
                "review_burden",
                self._review_burden(dossier),
                thresholds.review_burden,
                _METRIC_TARGETS["review_burden"],
                _METRIC_RATIONALES["review_burden"],
                thresholds,
            ),
            self._metric(
                "negative_evidence_visibility",
                self._negative_visibility(active_evidence),
                thresholds.negative_evidence_visibility,
                _METRIC_TARGETS["negative_evidence_visibility"],
                _METRIC_RATIONALES["negative_evidence_visibility"],
                thresholds,
            ),
        )
        blocking = tuple(
            metric.metric_id
            for metric in metrics
            if metric.band in {QualityBand.FAIL, QualityBand.UNKNOWN}
        )
        limitations = _expected_limitations(metrics, gate_valid, gate_codes)
        report = QualityReport(
            dossier_address=dossier.content_address,
            thresholds=thresholds,
            release_gate_valid=gate_valid,
            release_gate_issue_codes=gate_codes,
            release_policy_version=release_policy_version,
            metrics=metrics,
            release_ready=not blocking and gate_valid,
            limitations=limitations,
        )
        _enforce_report_limits(report, limits)
        return report

    @staticmethod
    def _metric(
        metric_id: str,
        value: float | None,
        threshold: float,
        target: str,
        rationale: str,
        thresholds: QualityThresholds | None = None,
    ) -> QualityMetric:
        selected = DEFAULT_QUALITY_THRESHOLDS if thresholds is None else thresholds
        checked_thresholds = _validated_thresholds(selected)
        checked_threshold = _finite_number(threshold, f"{metric_id} threshold")
        if metric_id not in _REQUIRED_METRIC_IDS:
            raise ValidationError(f"unsupported quality metric identity {metric_id!r}")
        registered_threshold = float(
            getattr(checked_thresholds, _METRIC_THRESHOLD_FIELDS[metric_id])
        )
        if checked_threshold != registered_threshold:
            raise ValidationError(f"{metric_id} threshold does not match its threshold snapshot")
        checked_value = None if value is None else round(_finite_number(value, metric_id), 6)
        band = _expected_metric_band(metric_id, checked_value, checked_thresholds)
        return QualityMetric(
            metric_id,
            checked_value,
            target,
            band,
            rationale,
        )

    @staticmethod
    def _active_evidence(dossier: Dossier) -> tuple[EvidenceClaim, ...]:
        referenced_ids = {
            claim_id
            for hypothesis in dossier.hypotheses
            for edge in hypothesis.edges
            for claim_id in edge.claim_ids
        }
        superseded_ids = {
            claim.supersedes for claim in dossier.evidence if claim.supersedes is not None
        }
        return tuple(
            claim
            for claim in dossier.evidence
            if claim.evidence_id in referenced_ids and claim.evidence_id not in superseded_ids
        )

    @staticmethod
    def _coverage(
        dossier: Dossier,
        evidence: tuple[EvidenceClaim, ...],
    ) -> float | None:
        edge_ids = {edge.edge_id for hypothesis in dossier.hypotheses for edge in hypothesis.edges}
        if not edge_ids:
            return None
        supported_edges = {
            claim.edge_id for claim in evidence if claim.state is EvidenceState.SUPPORTED
        }
        return len(edge_ids & supported_edges) / len(edge_ids)

    @staticmethod
    def _context_specificity(
        dossier: Dossier,
        evidence: tuple[EvidenceClaim, ...],
    ) -> float | None:
        if not evidence:
            return None
        expected_contexts: dict[str, set[str]] = {}
        for hypothesis in dossier.hypotheses:
            for edge in hypothesis.edges:
                expected_contexts.setdefault(edge.edge_id, set()).add(hypothesis.context.key)
        evidence_by_edge: dict[str, list[EvidenceClaim]] = {}
        for claim in evidence:
            if claim.edge_id not in expected_contexts:
                return None
            evidence_by_edge.setdefault(claim.edge_id, []).append(claim)
        matching_edges = sum(
            all(
                all(claim.context.key == context_key for context_key in context_keys)
                for claim in claims
            )
            for edge_id, claims in evidence_by_edge.items()
            for context_keys in (expected_contexts[edge_id],)
        )
        return matching_edges / len(evidence_by_edge)

    @staticmethod
    def _uncertainty_transparency(dossier: Dossier) -> float | None:
        if not dossier.hypotheses:
            return None
        visible = sum(
            type(hypothesis.uncertainty) is float
            and math.isfinite(hypothesis.uncertainty)
            and 0.0 <= hypothesis.uncertainty <= 1.0
            for hypothesis in dossier.hypotheses
        )
        return visible / len(dossier.hypotheses)

    @staticmethod
    def _review_burden(dossier: Dossier) -> float:
        return float(len(dossier.hypotheses))

    @staticmethod
    def _negative_visibility(evidence: tuple[EvidenceClaim, ...]) -> float | None:
        negatives = tuple(
            claim
            for claim in evidence
            if claim.state in {EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY}
        )
        if not negatives:
            return None
        negatives_by_edge: dict[str, list[EvidenceClaim]] = {}
        for claim in negatives:
            negatives_by_edge.setdefault(claim.edge_id, []).append(claim)
        documented_edges = sum(
            all(bool(claim.summary and claim.payload) for claim in claims)
            for claims in negatives_by_edge.values()
        )
        return documented_edges / len(negatives_by_edge)
