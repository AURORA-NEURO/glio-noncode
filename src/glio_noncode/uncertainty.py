"""Explicit uncertainty, out-of-domain, and calibration contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any

from .errors import ValidationError
from .models import EvidenceClaim, EvidenceState
from .serialization import content_hash, jsonable


MAX_DOMAIN_FEATURES = 2048
MAX_UNCERTAINTY_COMPONENTS = 256
MAX_UNCERTAINTY_EVIDENCE_IDS = 100_000
MAX_UNCERTAINTY_TEXT = 8_192
MAX_CALIBRATION_DATUM = 100_000
MAX_CALIBRATION_GROUPS = 4_096


def _text(value: object, label: str, *, maximum: int = MAX_UNCERTAINTY_TEXT) -> str:
    """Validate a bounded, non-empty text field without coercion."""

    if type(value) is not str or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValidationError(f"{label} exceeds the maximum length of {maximum}")
    if value != value.strip():
        raise ValidationError(f"{label} must not have surrounding whitespace")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{label} must be valid UTF-8") from exc
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{label} must not contain control characters")
    return value


def _strings(
    value: object,
    label: str,
    *,
    maximum: int,
    unique: bool = False,
) -> tuple[str, ...]:
    if type(value) is not tuple or len(value) > maximum:
        raise ValidationError(f"{label} must be a tuple of at most {maximum} items")
    result = tuple(_text(item, f"{label}[{index}]", maximum=MAX_UNCERTAINTY_TEXT) for index, item in enumerate(value))
    if unique and len(result) != len(set(result)):
        raise ValidationError(f"{label} must not contain duplicates")
    return result


def _unit_float(value: object, label: str) -> float:
    if type(value) is not float or not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{label} must be a finite float between 0 and 1")
    return value


def _finite_float(value: object, label: str) -> float:
    if type(value) is not float or not isfinite(value):
        raise ValidationError(f"{label} must be a finite float")
    return value


def _bounded_tuple(value: Iterable[Any], label: str, maximum: int) -> tuple[Any, ...]:
    """Materialize an iterable while detecting over-ceiling inputs early."""

    result: list[Any] = []
    for item in value:
        if len(result) >= maximum:
            raise ValidationError(f"{label} exceeds the supported ceiling")
        result.append(item)
    return tuple(result)


class OODStatus(StrEnum):
    """Feature-domain assessment state."""

    IN_DOMAIN = "in_domain"
    WATCH = "watch"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class UncertaintyBand(StrEnum):
    """Human-readable aggregate uncertainty band."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class DomainProfile:
    """Declared feature support domain for one context and model/reference version."""

    profile_id: str
    context_key: str
    required_features: tuple[str, ...]
    feature_ranges: Mapping[str, tuple[float, float]]
    source_version: str
    model_digest: str | None = None
    watch_threshold: float = 0.15

    def __post_init__(self) -> None:
        profile_id = _text(self.profile_id, "profile_id", maximum=256)
        context_key = _text(self.context_key, "context_key")
        source_version = _text(self.source_version, "source_version")
        required_features = _strings(
            self.required_features,
            "required_features",
            maximum=MAX_DOMAIN_FEATURES,
            unique=True,
        )
        if not required_features:
            raise ValidationError("domain profile requires at least one feature")
        if type(self.feature_ranges) is not dict and not isinstance(
            self.feature_ranges, Mapping
        ):
            raise ValidationError("feature_ranges must be a mapping")
        if len(self.feature_ranges) > MAX_DOMAIN_FEATURES:
            raise ValidationError("feature_ranges exceeds the domain feature ceiling")
        ranges: dict[str, tuple[float, float]] = {}
        for feature, bounds in self.feature_ranges.items():
            feature_name = _text(feature, "feature range name", maximum=256)
            if type(bounds) is not tuple or len(bounds) != 2:
                raise ValidationError("feature ranges must be two-float tuples")
            minimum = _finite_float(bounds[0], f"feature range {feature_name} minimum")
            maximum = _finite_float(bounds[1], f"feature range {feature_name} maximum")
            if maximum <= minimum:
                raise ValidationError(f"feature range is invalid: {feature_name}")
            ranges[feature_name] = (minimum, maximum)
        if type(self.watch_threshold) is not float or not isfinite(self.watch_threshold):
            raise ValidationError("watch_threshold must be a finite float")
        if not 0.0 < self.watch_threshold < 1.0:
            raise ValidationError("watch_threshold must be between 0 and 1")
        for feature in required_features:
            if feature not in ranges:
                raise ValidationError(f"required feature has no declared range: {feature}")
        if self.model_digest is not None:
            _text(self.model_digest, "model_digest", maximum=512)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "context_key", context_key)
        object.__setattr__(self, "source_version", source_version)
        object.__setattr__(self, "required_features", required_features)
        object.__setattr__(self, "feature_ranges", MappingProxyType(dict(sorted(ranges.items()))))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OODAssessment:
    """Feature-level domain result with missing and range reasons."""

    status: OODStatus
    distance: float
    missing_features: tuple[str, ...]
    out_of_range_features: tuple[str, ...]
    warnings: tuple[str, ...]
    profile_id: str
    content_address: str

    def __post_init__(self) -> None:
        if type(self.status) is not OODStatus:
            raise ValidationError("OOD status must be an OODStatus")
        _unit_float(self.distance, "OOD distance")
        _strings(
            self.missing_features,
            "missing_features",
            maximum=MAX_UNCERTAINTY_EVIDENCE_IDS,
            unique=True,
        )
        _strings(
            self.out_of_range_features,
            "out_of_range_features",
            maximum=MAX_UNCERTAINTY_EVIDENCE_IDS,
            unique=True,
        )
        _strings(
            self.warnings,
            "warnings",
            maximum=MAX_UNCERTAINTY_COMPONENTS,
            unique=True,
        )
        _text(self.profile_id, "profile_id", maximum=256)
        _text(self.content_address, "content_address", maximum=256)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class OutOfDomainDetector:
    """Compare declared numeric features with a versioned support profile."""

    def assess(self, features: Mapping[str, float], profile: DomainProfile) -> OODAssessment:
        if type(profile) is not DomainProfile:
            raise ValidationError("profile must be a DomainProfile")
        if not isinstance(features, Mapping):
            raise ValidationError("features must be a mapping")
        if len(features) > MAX_DOMAIN_FEATURES:
            raise ValidationError("features exceeds the domain feature ceiling")
        validated_features: dict[str, float] = {}
        for key, value in features.items():
            name = _text(key, "feature name", maximum=256)
            if type(value) is not float or not isfinite(value):
                raise ValidationError(f"feature {name} must be a finite float")
            validated_features[name] = value
        features = validated_features
        missing = tuple(
            sorted(feature for feature in profile.required_features if feature not in features)
        )
        out_of_range: list[str] = []
        distances: list[float] = []
        warnings: list[str] = []
        for feature in profile.required_features:
            if feature not in features:
                continue
            value = features[feature]
            minimum, maximum = profile.feature_ranges[feature]
            span = maximum - minimum
            if value < minimum:
                distance = (minimum - value) / span
                out_of_range.append(feature)
                distances.append(distance)
            elif value > maximum:
                distance = (value - maximum) / span
                out_of_range.append(feature)
                distances.append(distance)
            else:
                distances.append(0.0)
        distance = round(min(1.0, sum(distances) / max(1, len(distances))), 6)
        if missing:
            status = OODStatus.ABSTAINED
            warnings.append("required features are missing; domain status is not interpretable")
        elif out_of_range and distance >= profile.watch_threshold:
            status = OODStatus.OUT_OF_DOMAIN
        elif out_of_range:
            status = OODStatus.WATCH
        else:
            status = OODStatus.IN_DOMAIN
        payload = {
            "profile_id": profile.profile_id,
            "features": dict(features),
            "status": status,
            "distance": distance,
            "missing": missing,
            "out_of_range": tuple(out_of_range),
        }
        return OODAssessment(
            status=status,
            distance=distance,
            missing_features=missing,
            out_of_range_features=tuple(sorted(set(out_of_range))),
            warnings=tuple(dict.fromkeys(warnings)),
            profile_id=profile.profile_id,
            content_address=content_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class UncertaintyComponent:
    """One named contribution to aggregate uncertainty."""

    name: str
    value: float
    rationale: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.name, "uncertainty component name", maximum=256)
        _unit_float(self.value, "uncertainty component value")
        _text(self.rationale, "uncertainty component rationale")
        _strings(
            self.evidence_ids,
            "uncertainty component evidence_ids",
            maximum=MAX_UNCERTAINTY_EVIDENCE_IDS,
            unique=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UncertaintyReport:
    """Dependence-aware uncertainty summary with every component visible."""

    overall: float
    band: UncertaintyBand
    components: tuple[UncertaintyComponent, ...]
    ood: OODAssessment | None
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        _unit_float(self.overall, "uncertainty overall")
        if type(self.band) is not UncertaintyBand:
            raise ValidationError("uncertainty band must be an UncertaintyBand")
        if type(self.components) is not tuple or len(self.components) > MAX_UNCERTAINTY_COMPONENTS:
            raise ValidationError("uncertainty components exceed the supported ceiling")
        if any(type(component) is not UncertaintyComponent for component in self.components):
            raise ValidationError("uncertainty components must be typed objects")
        if self.ood is not None and type(self.ood) is not OODAssessment:
            raise ValidationError("uncertainty OOD assessment must be typed or null")
        _strings(self.limitations, "uncertainty limitations", maximum=MAX_UNCERTAINTY_COMPONENTS, unique=True)
        _text(self.content_address, "uncertainty content_address", maximum=256)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class UncertaintyPropagator:
    """Derive a cautious uncertainty view from typed claims and optional OOD."""

    def summarize(
        self,
        claims: Iterable[EvidenceClaim],
        *,
        ood: OODAssessment | None = None,
    ) -> UncertaintyReport:
        values = _bounded_tuple(
            claims,
            "uncertainty claims",
            MAX_UNCERTAINTY_EVIDENCE_IDS,
        )
        if any(type(claim) is not EvidenceClaim for claim in values):
            raise ValidationError("uncertainty claims must be EvidenceClaim objects")
        total = max(1, len(values))
        missing = tuple(
            claim.evidence_id
            for claim in values
            if claim.state
            in {
                EvidenceState.ABSTAINED,
                EvidenceState.ABSENT,
                EvidenceState.UNSUPPORTED,
                EvidenceState.OUT_OF_DOMAIN,
            }
        )
        contradictory = tuple(
            claim.evidence_id for claim in values if claim.state == EvidenceState.CONTRADICTORY
        )
        source_ids = {claim.source_id for claim in values}
        mean_confidence = sum(claim.confidence for claim in values) / total
        components = (
            UncertaintyComponent(
                "missingness",
                round(len(missing) / total, 6),
                "Missing, unsupported, out-of-domain, or abstained claims remain uncertainty.",
                missing,
            ),
            UncertaintyComponent(
                "contradiction",
                round(len(contradictory) / total, 6),
                "Contradictory claims are retained rather than resolved by averaging.",
                contradictory,
            ),
            UncertaintyComponent(
                "context_transport",
                round(1.0 - mean_confidence, 6),
                "Lower claim confidence contributes transport or applicability uncertainty.",
                tuple(claim.evidence_id for claim in values),
            ),
            UncertaintyComponent(
                "source_dependence",
                0.15 if len(source_ids) <= 1 and values else 0.0,
                "A single source leaves less independent support for triangulation.",
                tuple(claim.evidence_id for claim in values),
            ),
        )
        if ood is not None:
            components += (
                UncertaintyComponent(
                    "out_of_domain",
                    1.0
                    if ood.status in {OODStatus.OUT_OF_DOMAIN, OODStatus.ABSTAINED}
                    else ood.distance,
                    (
                        "Feature-domain distance and missingness are carried from "
                        "the versioned OOD profile."
                    ),
                ),
            )
        overall = round(
            min(1.0, sum(component.value for component in components) / len(components)), 6
        )
        if ood is not None and ood.status == OODStatus.ABSTAINED:
            band = UncertaintyBand.ABSTAIN
        elif overall >= 0.70:
            band = UncertaintyBand.HIGH
        elif overall >= 0.35:
            band = UncertaintyBand.MODERATE
        else:
            band = UncertaintyBand.LOW
        payload = {"overall": overall, "band": band, "components": components, "ood": ood}
        return UncertaintyReport(
            overall=overall,
            band=band,
            components=components,
            ood=ood,
            limitations=(
                "This is a transparent uncertainty view, not a calibrated clinical probability.",
                (
                    "Component values depend on supplied claims, contexts, and "
                    "domain profile versions."
                ),
            ),
            content_address=content_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class CalibrationDatum:
    """One held-out prediction/outcome pair for research calibration checks."""

    prediction: float
    outcome: float
    group: str = "all"

    def __post_init__(self) -> None:
        _unit_float(self.prediction, "calibration prediction")
        _unit_float(self.outcome, "calibration outcome")
        _text(self.group, "calibration group", maximum=256)


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Descriptive calibration metrics with sample count and grouping."""

    sample_count: int
    mean_absolute_error: float
    brier_score: float
    expected_calibration_error: float
    group_metrics: Mapping[str, Mapping[str, float]]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if type(self.sample_count) is not int or not 0 <= self.sample_count <= MAX_CALIBRATION_DATUM:
            raise ValidationError("calibration sample_count is outside the supported range")
        _unit_float(self.mean_absolute_error, "calibration mean_absolute_error")
        _unit_float(self.brier_score, "calibration brier_score")
        _unit_float(self.expected_calibration_error, "calibration expected_calibration_error")
        if not isinstance(self.group_metrics, Mapping):
            raise ValidationError("calibration group_metrics must be a mapping")
        if len(self.group_metrics) > MAX_CALIBRATION_GROUPS:
            raise ValidationError("calibration group_metrics exceed the supported ceiling")
        for group, metrics in self.group_metrics.items():
            _text(group, "calibration group", maximum=256)
            if not isinstance(metrics, Mapping):
                raise ValidationError("calibration group metrics must be mappings")
            if set(metrics) != {"count", "mae", "brier"}:
                raise ValidationError("calibration group metrics have an invalid shape")
            count = metrics["count"]
            if type(count) is not float or not isfinite(count) or count < 0.0:
                raise ValidationError("calibration group count must be a finite non-negative float")
            _unit_float(metrics["mae"], "calibration group mae")
            _unit_float(metrics["brier"], "calibration group brier")
        _strings(self.warnings, "calibration warnings", maximum=MAX_UNCERTAINTY_COMPONENTS, unique=True)
        _text(self.content_address, "calibration content_address", maximum=256)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CalibrationEvaluator:
    """Compute bounded calibration summaries without declaring validity."""

    def evaluate(self, data: Iterable[CalibrationDatum], *, bins: int = 10) -> CalibrationReport:
        if type(bins) is not int or bins < 2 or bins > 100:
            raise ValidationError("calibration bins must be between 2 and 100")
        values = _bounded_tuple(data, "calibration observations", MAX_CALIBRATION_DATUM)
        if any(type(item) is not CalibrationDatum for item in values):
            raise ValidationError("calibration data must contain CalibrationDatum objects")
        if len({item.group for item in values}) > MAX_CALIBRATION_GROUPS:
            raise ValidationError("calibration groups exceed the supported ceiling")
        if not values:
            return CalibrationReport(
                0,
                0.0,
                0.0,
                0.0,
                {},
                ("No calibration observations were supplied.",),
                content_hash({"empty": True}),
            )
        mae = sum(abs(item.prediction - item.outcome) for item in values) / len(values)
        brier = sum((item.prediction - item.outcome) ** 2 for item in values) / len(values)
        groups: dict[str, list[CalibrationDatum]] = {}
        for item in values:
            groups.setdefault(item.group, []).append(item)
        group_metrics: dict[str, dict[str, float]] = {}
        for group, group_values in groups.items():
            group_metrics[group] = {
                "count": float(len(group_values)),
                "mae": round(
                    sum(abs(item.prediction - item.outcome) for item in group_values)
                    / len(group_values),
                    6,
                ),
                "brier": round(
                    sum((item.prediction - item.outcome) ** 2 for item in group_values)
                    / len(group_values),
                    6,
                ),
            }
        ece = 0.0
        for index in range(bins):
            lower = index / bins
            upper = (index + 1) / bins
            members = [
                item
                for item in values
                if lower <= item.prediction < upper
                or (index == bins - 1 and item.prediction == 1.0)
            ]
            if members:
                ece += (
                    len(members)
                    / len(values)
                    * abs(
                        sum(item.prediction for item in members) / len(members)
                        - sum(item.outcome for item in members) / len(members)
                    )
                )
        payload = {
            "sample_count": len(values),
            "mae": mae,
            "brier": brier,
            "ece": ece,
            "groups": group_metrics,
        }
        warnings = (
            (
                "Calibration metrics are descriptive and require a pre-specified "
                "held-out evaluation design."
            ),
        )
        return CalibrationReport(
            sample_count=len(values),
            mean_absolute_error=round(mae, 6),
            brier_score=round(brier, 6),
            expected_calibration_error=round(ece, 6),
            group_metrics=group_metrics,
            warnings=warnings,
            content_address=content_hash(payload),
        )
