"""Origin and clonality assessment from declared multi-sample observations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .models import VariantOrigin
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class OriginObservation:
    """One sample-level observation used for origin assessment."""

    observation_id: str
    variant_id: str
    sample_id: str
    relationship: str
    alternate_fraction: float | None
    present_in_normal: bool | None
    timepoint: str
    source_id: str

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "sample_id",
            "relationship",
            "timepoint",
            "source_id",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"origin {name} is required")
        if self.alternate_fraction is not None and not 0.0 <= self.alternate_fraction <= 1.0:
            raise ValidationError("alternate_fraction must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OriginAssessment:
    """Origin and clonality view with explicit ambiguity and limitations."""

    variant_id: str
    origin: VariantOrigin
    clonality: str
    support: float
    uncertainty: float
    contributing_observation_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class OriginClonalityAssessor:
    """Classify only what the declared observations support."""

    def assess(
        self,
        observations: Iterable[OriginObservation],
        *,
        variant_id: str | None = None,
    ) -> OriginAssessment:
        values = tuple(observations)
        if not values:
            raise ValidationError("origin assessment requires observations")
        selected_variant = variant_id or values[0].variant_id
        values = tuple(item for item in values if item.variant_id == selected_variant)
        if not values:
            raise ValidationError(f"variant observations not found: {selected_variant}")
        warnings: list[str] = []
        normal_present = [item for item in values if item.present_in_normal is True]
        normal_absent = [item for item in values if item.present_in_normal is False]
        tumor_rows = [item for item in values if item.relationship.lower() in {"tumor", "somatic"}]
        if normal_present and normal_absent:
            origin = VariantOrigin.UNCERTAIN
            support = 0.35
            warnings.append("Normal-sample observations conflict across the supplied records.")
        elif normal_present:
            origin = VariantOrigin.GERMLINE
            support = 0.85
        elif normal_absent and tumor_rows:
            origin = VariantOrigin.SOMATIC
            support = 0.80
        elif tumor_rows:
            origin = VariantOrigin.UNCERTAIN
            support = 0.30
            warnings.append("Tumor evidence exists but normal presence was not declared.")
        else:
            origin = VariantOrigin.UNCERTAIN
            support = 0.20
            warnings.append("The supplied observations do not distinguish origin.")
        fractions = [
            item.alternate_fraction for item in tumor_rows if item.alternate_fraction is not None
        ]
        if not fractions:
            clonality = "unknown"
            uncertainty = 0.85
            warnings.append("No tumor alternate fractions were supplied for clonality assessment.")
        else:
            median_fraction = sorted(fractions)[len(fractions) // 2]
            if median_fraction >= 0.35:
                clonality = "clonal_candidate"
                uncertainty = 0.35
            elif median_fraction <= 0.15:
                clonality = "subclonal_candidate"
                uncertainty = 0.55
            else:
                clonality = "mixed_or_uncertain"
                uncertainty = 0.70
            if len(fractions) < 2:
                uncertainty = min(1.0, uncertainty + 0.15)
                warnings.append("Clonality is based on fewer than two tumor observations.")
        payload = {
            "variant_id": selected_variant,
            "origin": origin,
            "clonality": clonality,
            "support": support,
            "uncertainty": uncertainty,
            "observation_ids": tuple(item.observation_id for item in values),
            "warnings": tuple(warnings),
        }
        return OriginAssessment(
            variant_id=selected_variant,
            origin=origin,
            clonality=clonality,
            support=round(support, 6),
            uncertainty=round(uncertainty, 6),
            contributing_observation_ids=tuple(item.observation_id for item in values),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(payload),
        )
