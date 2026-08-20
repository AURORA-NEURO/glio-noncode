"""Explicit uncertainty, out-of-domain, and calibration contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .models import EvidenceClaim, EvidenceState
from .serialization import content_hash, jsonable


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
        for name in ("profile_id", "context_key", "source_version"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"{name} must not be empty")
        if not self.required_features:
            raise ValidationError("domain profile requires at least one feature")
        if not 0.0 < self.watch_threshold < 1.0:
            raise ValidationError("watch_threshold must be between 0 and 1")
        for feature in self.required_features:
            bounds = self.feature_ranges.get(feature)
            if bounds is None:
                raise ValidationError(f"required feature has no declared range: {feature}")
            minimum, maximum = bounds
            if maximum <= minimum:
                raise ValidationError(f"feature range is invalid: {feature}")

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

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class OutOfDomainDetector:
    """Compare declared numeric features with a versioned support profile."""

    def assess(self, features: Mapping[str, float], profile: DomainProfile) -> OODAssessment:
        missing = tuple(
            sorted(feature for feature in profile.required_features if feature not in features)
        )
        out_of_range: list[str] = []
        distances: list[float] = []
        warnings: list[str] = []
        for feature in profile.required_features:
            if feature not in features:
                continue
            try:
                value = float(features[feature])
            except (TypeError, ValueError):
                out_of_range.append(feature)
                warnings.append(f"feature is not numeric: {feature}")
                continue
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
        if not self.name.strip() or not self.rationale.strip():
            raise ValidationError("uncertainty component name and rationale are required")
        if not 0.0 <= self.value <= 1.0:
            raise ValidationError("uncertainty component value must be between 0 and 1")

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
        values = tuple(claims)
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
        if not 0.0 <= self.prediction <= 1.0 or not 0.0 <= self.outcome <= 1.0:
            raise ValidationError("calibration values must be between 0 and 1")


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

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CalibrationEvaluator:
    """Compute bounded calibration summaries without declaring validity."""

    def evaluate(self, data: Iterable[CalibrationDatum], *, bins: int = 10) -> CalibrationReport:
        values = tuple(data)
        if bins < 2 or bins > 100:
            raise ValidationError("calibration bins must be between 2 and 100")
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
