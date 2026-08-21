"""Scientific-beta specimen-origin and clonality contracts.

The Domain 03 MVP preserves specimen declarations, matched normals, purity,
ploidy, and sample-integrity observations. This module adds four independent
research adapters on top of those declarations:

* somatic/germline origin classification;
* mosaicism evidence scoring with an explicitly uncalibrated posterior-shaped
  estimate;
* purity/copy-number-aware cancer-cell fraction estimation; and
* relative subclone assignment from CCF clusters.

These are source-accounted measurements, not diagnoses. Missing matched-normal
evidence, contamination, contradictory callers, and out-of-range calculations
remain visible. No adapter assigns a patient identity or a clinical decision.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .models import VariantOrigin
from .serialization import content_hash, jsonable, require_non_empty


class SpecimenBetaState(StrEnum):
    """Evidence state shared by the Domain 03 beta adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class SpecimenBetaIssue:
    """A row-addressable specimen anomaly retained beside its result."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OriginClassification:
    """Origin classification with separate somatic and germline evidence scores."""

    variant_id: str
    origin: VariantOrigin
    state: SpecimenBetaState
    somatic_score: float
    germline_score: float
    tumor_alt_fraction: float | None
    normal_alt_fraction: float | None
    evidence_channels: tuple[str, ...]
    conflicting_observation_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OriginClassificationBatch:
    """Batch origin classifications with source anomalies retained."""

    input_hash: str
    state: SpecimenBetaState
    classifications: tuple[OriginClassification, ...]
    issues: tuple[SpecimenBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SomaticGermlineOriginClassifier:
    """Classify origin from declared tumor/normal evidence without hidden priors."""

    def classify(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        variant_id: str | None = None,
        minimum_tumor_alt_fraction: float = 0.05,
        normal_presence_fraction: float = 0.02,
    ) -> OriginClassificationBatch:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[SpecimenBetaIssue] = []
        if not 0 <= minimum_tumor_alt_fraction <= 1 or not 0 <= normal_presence_fraction <= 1:
            issue = SpecimenBetaIssue(
                "invalid_origin_threshold",
                "origin thresholds must be between zero and one",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, SpecimenBetaState.INVALID, (), (issue,))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SpecimenBetaIssue(
                        "row_not_object",
                        "origin observation must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            selected_variant = str(_value(row, "variant_id", "variant", "id", default=""))
            if not selected_variant:
                issues.append(
                    SpecimenBetaIssue(
                        "missing_variant_id",
                        "origin observation requires variant_id",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            if variant_id and selected_variant != variant_id:
                continue
            try:
                tumor_fraction = _fraction(
                    _value(row, "tumor_alt_fraction", "tumor_vaf", "vaf", "alternate_fraction")
                )
                normal_fraction = _fraction(_value(row, "normal_alt_fraction", "normal_vaf"))
            except ValidationError as exc:
                issues.append(
                    SpecimenBetaIssue(
                        "invalid_origin_fraction",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            grouped[selected_variant].append(
                {
                    "observation_id": str(
                        _value(row, "observation_id", "record_id", default=f"row-{row_number}")
                    ),
                    "relationship": str(
                        _value(row, "relationship", "sample_type", default="unknown")
                    ).lower(),
                    "present_in_normal": _optional_bool(row.get("present_in_normal")),
                    "tumor_fraction": tumor_fraction,
                    "normal_fraction": normal_fraction,
                    "normal_alt_reads": _optional_int(row.get("normal_alt_reads")),
                    "normal_depth": _optional_int(row.get("normal_depth")),
                    "population_frequency": _optional_fraction(
                        _value(row, "population_frequency", "pop_af")
                    ),
                    "raw_hash": raw_hash,
                }
            )
        classifications = tuple(
            self._classify_variant(
                selected_variant, rows, normal_presence_fraction, minimum_tumor_alt_fraction
            )
            for selected_variant, rows in sorted(grouped.items())
        )
        if not classifications:
            state = SpecimenBetaState.ABSTAINED
        elif any(item.state == SpecimenBetaState.AMBIGUOUS for item in classifications):
            state = SpecimenBetaState.AMBIGUOUS
        elif any(item.state == SpecimenBetaState.PARTIAL for item in classifications):
            state = SpecimenBetaState.PARTIAL
        else:
            state = SpecimenBetaState.SUPPORTED
        return self._report(
            input_hash,
            state,
            classifications,
            tuple(issues),
            (
                "Origin labels are research classifications and not clinical germline or "
                "somatic diagnoses.",
            ),
        )

    @staticmethod
    def _classify_variant(
        variant_id: str,
        rows: list[dict[str, Any]],
        normal_presence_fraction: float,
        minimum_tumor_alt_fraction: float,
    ) -> OriginClassification:
        somatic_score = 0.0
        germline_score = 0.0
        channels: list[str] = []
        conflicts: list[str] = []
        tumor_fractions = [
            row["tumor_fraction"] for row in rows if row["tumor_fraction"] is not None
        ]
        normal_fractions = [
            row["normal_fraction"] for row in rows if row["normal_fraction"] is not None
        ]
        for row in rows:
            observation_id = row["observation_id"]
            relationship = row["relationship"]
            normal_present = row["present_in_normal"]
            normal_fraction = row["normal_fraction"]
            if normal_present is True or (
                normal_fraction is not None and normal_fraction >= normal_presence_fraction
            ):
                germline_score += 2.0
                channels.append(f"normal_presence:{observation_id}")
            if normal_present is False:
                somatic_score += 2.0
                channels.append(f"normal_absence:{observation_id}")
            if (
                relationship in {"tumor", "tumour", "case", "somatic"}
                and row["tumor_fraction"] is not None
                and row["tumor_fraction"] >= minimum_tumor_alt_fraction
            ):
                somatic_score += 1.0
                channels.append(f"tumor_alt_fraction:{observation_id}")
            if (
                row["normal_alt_reads"] == 0
                and row["normal_depth"] is not None
                and row["normal_depth"] > 0
            ):
                somatic_score += 1.0
                channels.append(f"normal_zero_alt_reads:{observation_id}")
            if row["population_frequency"] is not None and row["population_frequency"] > 0:
                germline_score += 0.5
                channels.append(f"population_frequency:{observation_id}")
            if normal_present is True and relationship in {"tumor", "tumour", "case", "somatic"}:
                conflicts.append(observation_id)
        warnings: list[str] = []
        if not normal_fractions and not any(row["present_in_normal"] is not None for row in rows):
            warnings.append("No declared normal presence or normal allele fraction was supplied.")
        if somatic_score and germline_score:
            origin = VariantOrigin.UNCERTAIN
            state = SpecimenBetaState.AMBIGUOUS
            warnings.append("Somatic and germline evidence channels are both present.")
        elif germline_score >= 2:
            origin = VariantOrigin.GERMLINE
            state = SpecimenBetaState.SUPPORTED
        elif somatic_score >= 2:
            origin = VariantOrigin.SOMATIC
            state = SpecimenBetaState.SUPPORTED
        else:
            origin = VariantOrigin.UNCERTAIN
            state = SpecimenBetaState.PARTIAL
            warnings.append("Declared observations do not cross an origin evidence threshold.")
        body = {
            "variant_id": variant_id,
            "origin": origin,
            "state": state,
            "rows": tuple(row["observation_id"] for row in rows),
            "scores": (somatic_score, germline_score),
        }
        return OriginClassification(
            variant_id=variant_id,
            origin=origin,
            state=state,
            somatic_score=round(somatic_score, 6),
            germline_score=round(germline_score, 6),
            tumor_alt_fraction=(
                round(float(median(tumor_fractions)), 6) if tumor_fractions else None
            ),
            normal_alt_fraction=(
                round(float(median(normal_fractions)), 6) if normal_fractions else None
            ),
            evidence_channels=tuple(dict.fromkeys(channels)),
            conflicting_observation_ids=tuple(dict.fromkeys(conflicts)),
            observation_ids=tuple(row["observation_id"] for row in rows),
            raw_hashes=tuple(sorted(row["raw_hash"] for row in rows)),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )

    @staticmethod
    def _report(
        input_hash: str,
        state: SpecimenBetaState,
        classifications: tuple[OriginClassification, ...],
        issues: tuple[SpecimenBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> OriginClassificationBatch:
        body = {
            "input_hash": input_hash,
            "state": state,
            "classifications": classifications,
            "issues": issues,
        }
        return OriginClassificationBatch(
            input_hash=input_hash,
            state=state,
            classifications=classifications,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class MosaicismPosteriorEstimate:
    """Posterior-shaped mosaicism estimate with calibration status attached."""

    variant_id: str
    posterior_estimate: float
    calibrated: bool
    calibration_id: str | None
    supporting_tissues: tuple[str, ...]
    low_fraction_observations: tuple[str, ...]
    contamination_flags: tuple[str, ...]
    evidence_channels: tuple[str, ...]
    state: SpecimenBetaState
    uncertainty: float
    raw_hashes: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MosaicismPosteriorBatch:
    input_hash: str
    state: SpecimenBetaState
    estimates: tuple[MosaicismPosteriorEstimate, ...]
    issues: tuple[SpecimenBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MosaicismPosteriorEstimator:
    """Estimate mosaicism evidence from repeated tissue observations.

    The output is deliberately marked uncalibrated unless a caller supplies a
    calibration identifier. The logistic transform is a reproducible evidence
    score, not a population-calibrated clinical posterior.
    """

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        prior: float = 0.10,
        calibration_id: str | None = None,
        low_fraction_max: float = 0.35,
        minimum_tissues: int = 2,
        contamination_threshold: float = 0.05,
    ) -> MosaicismPosteriorBatch:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[SpecimenBetaIssue] = []
        if not 0 < prior < 1 or not 0 < low_fraction_max <= 1 or minimum_tissues < 1:
            issue = SpecimenBetaIssue(
                "invalid_mosaicism_parameter",
                "mosaicism parameters are outside their valid bounds",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, SpecimenBetaState.INVALID, (), (issue,))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SpecimenBetaIssue(
                        "row_not_object",
                        "mosaicism observation must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            variant_id = str(_value(row, "variant_id", "variant", "id", default=""))
            if not variant_id:
                issues.append(
                    SpecimenBetaIssue(
                        "missing_variant_id",
                        "mosaicism observation requires variant_id",
                        _raw_hash(row),
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                fraction = _fraction(_value(row, "alternate_fraction", "vaf", "alt_fraction"))
            except ValidationError as exc:
                issues.append(
                    SpecimenBetaIssue(
                        "invalid_mosaicism_fraction",
                        str(exc),
                        _raw_hash(row),
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            tissue = str(
                _value(row, "tissue_id", "specimen_id", "sample_id", default="unspecified")
            )
            grouped[variant_id].append(
                {
                    "observation_id": str(
                        _value(row, "observation_id", "record_id", default=f"row-{row_number}")
                    ),
                    "tissue": tissue,
                    "fraction": fraction,
                    "contamination": _optional_fraction(
                        _value(row, "contamination_fraction", "contamination")
                    ),
                    "relationship": str(
                        _value(row, "relationship", "sample_type", default="unknown")
                    ).lower(),
                    "raw_hash": _raw_hash(row),
                }
            )
        estimates = tuple(
            self._estimate_variant(
                variant_id,
                rows,
                prior,
                calibration_id,
                low_fraction_max,
                minimum_tissues,
                contamination_threshold,
            )
            for variant_id, rows in sorted(grouped.items())
        )
        state = (
            SpecimenBetaState.ABSTAINED
            if not estimates
            else SpecimenBetaState.AMBIGUOUS
            if any(item.state == SpecimenBetaState.AMBIGUOUS for item in estimates)
            else SpecimenBetaState.PARTIAL
            if any(item.state == SpecimenBetaState.PARTIAL for item in estimates)
            else SpecimenBetaState.SUPPORTED
        )
        return self._report(
            input_hash,
            state,
            estimates,
            tuple(issues),
            (
                "Posterior-shaped mosaicism estimates are uncalibrated unless a calibration_id "
                "is supplied.",
                "Mosaicism evidence does not establish constitutional status, diagnosis, or "
                "clinical risk.",
            ),
        )

    @staticmethod
    def _estimate_variant(
        variant_id: str,
        rows: list[dict[str, Any]],
        prior: float,
        calibration_id: str | None,
        low_fraction_max: float,
        minimum_tissues: int,
        contamination_threshold: float,
    ) -> MosaicismPosteriorEstimate:
        low_rows = [
            row
            for row in rows
            if row["fraction"] is not None and 0 < row["fraction"] <= low_fraction_max
        ]
        low_tissues = tuple(sorted({row["tissue"] for row in low_rows}))
        contamination_flags = tuple(
            sorted(
                row["observation_id"]
                for row in rows
                if row["contamination"] is not None
                and row["contamination"] >= contamination_threshold
            )
        )
        logit = math.log(prior / (1 - prior))
        evidence = 1.35 * max(0, len(low_tissues) - 1)
        evidence += 0.55 * len(low_rows)
        evidence -= 1.10 * len(contamination_flags)
        tumor_rows = [row for row in rows if row["relationship"] in {"tumor", "tumour", "case"}]
        if tumor_rows and not low_tissues:
            evidence -= 0.8
        posterior = _sigmoid(logit + evidence)
        warnings: list[str] = []
        channels = ["low_fraction_tissue_recurrence"] if low_tissues else []
        if contamination_flags:
            channels.append("contamination_penalty")
            warnings.append(
                "One or more observations exceed the configured contamination threshold."
            )
        if len(low_tissues) < minimum_tissues:
            state = SpecimenBetaState.PARTIAL
            warnings.append(
                "Fewer than the configured number of distinct tissues support mosaic recurrence."
            )
        else:
            state = SpecimenBetaState.SUPPORTED
        uncertainty = round(max(0.05, 1.0 - abs(posterior - 0.5) * 1.7), 6)
        body = {
            "variant_id": variant_id,
            "posterior": posterior,
            "rows": tuple(row["observation_id"] for row in rows),
            "calibration_id": calibration_id,
        }
        return MosaicismPosteriorEstimate(
            variant_id=variant_id,
            posterior_estimate=round(posterior, 6),
            calibrated=calibration_id is not None,
            calibration_id=calibration_id,
            supporting_tissues=low_tissues,
            low_fraction_observations=tuple(row["observation_id"] for row in low_rows),
            contamination_flags=contamination_flags,
            evidence_channels=tuple(channels),
            state=state,
            uncertainty=uncertainty,
            raw_hashes=tuple(sorted(row["raw_hash"] for row in rows)),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )

    @staticmethod
    def _report(
        input_hash: str,
        state: SpecimenBetaState,
        estimates: tuple[MosaicismPosteriorEstimate, ...],
        issues: tuple[SpecimenBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> MosaicismPosteriorBatch:
        body = {
            "input_hash": input_hash,
            "state": state,
            "estimates": estimates,
            "issues": issues,
        }
        return MosaicismPosteriorBatch(
            input_hash=input_hash,
            state=state,
            estimates=estimates,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class CancerCellFractionEstimate:
    """Purity/copy-number-aware CCF estimate with unclamped raw calculation."""

    variant_id: str
    sample_id: str
    estimated_ccf: float | None
    raw_ccf: float | None
    ccf_lower: float | None
    ccf_upper: float | None
    variant_allele_fraction: float | None
    purity: float | None
    total_copy_number: float | None
    alternate_copy_number: float | None
    normal_copy_number: float
    state: SpecimenBetaState
    evidence_channels: tuple[str, ...]
    warnings: tuple[str, ...]
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CancerCellFractionBatch:
    input_hash: str
    state: SpecimenBetaState
    estimates: tuple[CancerCellFractionEstimate, ...]
    issues: tuple[SpecimenBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CancerCellFractionEstimator:
    """Estimate CCF with an explicit purity and allele-copy-number model."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        normal_copy_number: float = 2.0,
        out_of_range_tolerance: float = 0.05,
    ) -> CancerCellFractionBatch:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[SpecimenBetaIssue] = []
        if normal_copy_number <= 0 or out_of_range_tolerance < 0:
            issue = SpecimenBetaIssue(
                "invalid_ccf_parameter",
                "normal copy number must be positive and tolerance non-negative",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, SpecimenBetaState.INVALID, (), (issue,))
        estimates: list[CancerCellFractionEstimate] = []
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SpecimenBetaIssue(
                        "row_not_object",
                        "CCF record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            try:
                variant_id = str(_value(row, "variant_id", "variant", "id"))
                sample_id = str(_value(row, "sample_id", "sample", default="unspecified"))
                require_non_empty(variant_id, "variant_id")
                purity = _fraction(_value(row, "purity", "tumor_purity"))
                vaf = _fraction(_value(row, "variant_allele_fraction", "vaf", "alternate_fraction"))
                total_cn = _number(
                    _value(row, "total_copy_number", "copy_number", "CN"), "total_copy_number"
                )
                alt_cn = _number(
                    _value(row, "alternate_copy_number", "alt_copy_number", "alt_cn", default=1.0),
                    "alternate_copy_number",
                )
                if alt_cn <= 0 or total_cn <= 0:
                    raise ValidationError("copy-number values must be positive")
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SpecimenBetaIssue(
                        "invalid_ccf_record",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            depth = _optional_int(_value(row, "depth", "read_depth"))
            alt_reads = _optional_int(_value(row, "alt_reads", "alternate_reads"))
            effective_cn = purity * total_cn + (1.0 - purity) * normal_copy_number
            raw_ccf = vaf * effective_cn / (purity * alt_cn) if purity > 0 else None
            lower, upper = self._interval(vaf, purity, total_cn, alt_cn, normal_copy_number, depth)
            warnings: list[str] = []
            channels = [
                "purity",
                "total_copy_number",
                "alternate_copy_number",
                "variant_allele_fraction",
            ]
            if depth is not None and alt_reads is not None:
                channels.append("read_depth_interval")
            if raw_ccf is None:
                state = SpecimenBetaState.ABSTAINED
                estimated = None
                warnings.append("Purity is zero, so CCF cannot be estimated from this model.")
            elif raw_ccf < -out_of_range_tolerance or raw_ccf > 1.0 + out_of_range_tolerance:
                state = SpecimenBetaState.PARTIAL
                estimated = None
                warnings.append(
                    "Raw CCF falls outside the model range and was not silently clamped."
                )
            else:
                state = SpecimenBetaState.SUPPORTED
                estimated = round(min(1.0, max(0.0, raw_ccf)), 6)
            if depth is not None and alt_reads is not None and alt_reads > depth:
                warnings.append("Alternate reads exceed depth; interval evidence is invalid.")
                state = SpecimenBetaState.PARTIAL
            estimates.append(
                CancerCellFractionEstimate(
                    variant_id=variant_id,
                    sample_id=sample_id,
                    estimated_ccf=estimated,
                    raw_ccf=(round(raw_ccf, 6) if raw_ccf is not None else None),
                    ccf_lower=lower,
                    ccf_upper=upper,
                    variant_allele_fraction=round(vaf, 6),
                    purity=round(purity, 6),
                    total_copy_number=round(total_cn, 6),
                    alternate_copy_number=round(alt_cn, 6),
                    normal_copy_number=normal_copy_number,
                    state=state,
                    evidence_channels=tuple(channels),
                    warnings=tuple(dict.fromkeys(warnings)),
                    raw_hash=raw_hash,
                    content_address=content_hash(
                        {
                            "variant_id": variant_id,
                            "sample_id": sample_id,
                            "raw_ccf": raw_ccf,
                            "state": state,
                        }
                    ),
                )
            )
        state = (
            SpecimenBetaState.ABSTAINED
            if not estimates
            else SpecimenBetaState.PARTIAL
            if any(item.state != SpecimenBetaState.SUPPORTED for item in estimates)
            else SpecimenBetaState.SUPPORTED
        )
        return self._report(
            input_hash,
            state,
            tuple(estimates),
            tuple(issues),
            ("CCF is model-based and depends on purity, total CN, and alternate CN assumptions.",),
        )

    @staticmethod
    def _interval(
        vaf: float,
        purity: float,
        total_cn: float,
        alt_cn: float,
        normal_cn: float,
        depth: int | None,
    ) -> tuple[float | None, float | None]:
        if depth is None or depth <= 0 or purity <= 0:
            return None, None
        standard_error = math.sqrt(max(0.0, vaf * (1.0 - vaf) / depth))
        effective_cn = purity * total_cn + (1.0 - purity) * normal_cn
        scale = effective_cn / (purity * alt_cn)
        lower = min(1.0, max(0.0, (vaf - 1.96 * standard_error) * scale))
        upper = min(1.0, max(0.0, (vaf + 1.96 * standard_error) * scale))
        return round(lower, 6), round(upper, 6)

    @staticmethod
    def _report(
        input_hash: str,
        state: SpecimenBetaState,
        estimates: tuple[CancerCellFractionEstimate, ...],
        issues: tuple[SpecimenBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> CancerCellFractionBatch:
        body = {
            "input_hash": input_hash,
            "state": state,
            "estimates": estimates,
            "issues": issues,
        }
        return CancerCellFractionBatch(
            input_hash=input_hash,
            state=state,
            estimates=estimates,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class SubcloneAssignment:
    """Relative CCF cluster assignment with boundary ambiguity retained."""

    sample_id: str
    variant_id: str
    subclone_id: str
    cluster_mean_ccf: float
    estimated_ccf: float
    distance_to_cluster_mean: float
    assignment_state: SpecimenBetaState
    assignment_basis: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SubcloneAssignmentBatch:
    input_hash: str
    state: SpecimenBetaState
    assignments: tuple[SubcloneAssignment, ...]
    cluster_means: Mapping[str, float]
    issues: tuple[SpecimenBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SubcloneAssigner:
    """Cluster CCF observations within sample scope without naming biology."""

    def assign(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        max_ccf_distance: float = 0.15,
        boundary_ambiguity: float = 0.02,
    ) -> SubcloneAssignmentBatch:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[SpecimenBetaIssue] = []
        if max_ccf_distance <= 0 or boundary_ambiguity < 0:
            issue = SpecimenBetaIssue(
                "invalid_subclone_parameter",
                "CCF clustering distance must be positive and ambiguity non-negative",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, SpecimenBetaState.INVALID, (), {}, (issue,))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SpecimenBetaIssue(
                        "row_not_object",
                        "subclone input must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            try:
                sample_id = str(_value(row, "sample_id", "sample", default="unspecified"))
                variant_id = str(_value(row, "variant_id", "variant", "id"))
                ccf = _number(
                    _value(row, "estimated_ccf", "ccf", "cancer_cell_fraction"), "estimated_ccf"
                )
                require_non_empty(variant_id, "variant_id")
                if not 0 <= ccf <= 1:
                    raise ValidationError("estimated CCF must be between zero and one")
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SpecimenBetaIssue(
                        "invalid_subclone_record",
                        str(exc),
                        _raw_hash(row),
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            grouped[sample_id].append(
                {
                    "sample_id": sample_id,
                    "variant_id": variant_id,
                    "ccf": ccf,
                    "raw_hash": _raw_hash(row),
                }
            )
        assignments: list[SubcloneAssignment] = []
        cluster_means: dict[str, float] = {}
        for sample_id, rows in sorted(grouped.items()):
            clusters: list[list[dict[str, Any]]] = []
            for row in sorted(rows, key=lambda item: (-item["ccf"], item["variant_id"])):
                if not clusters:
                    clusters.append([row])
                    continue
                mean = sum(item["ccf"] for item in clusters[-1]) / len(clusters[-1])
                if abs(row["ccf"] - mean) <= max_ccf_distance:
                    clusters[-1].append(row)
                else:
                    clusters.append([row])
            ordered_clusters = sorted(
                clusters,
                key=lambda cluster: sum(item["ccf"] for item in cluster) / len(cluster),
                reverse=True,
            )
            for index, cluster in enumerate(ordered_clusters, start=1):
                mean = round(sum(item["ccf"] for item in cluster) / len(cluster), 6)
                subclone_id = f"{sample_id}:relative-subclone:{index}"
                cluster_means[subclone_id] = mean
                for row in cluster:
                    distance = round(abs(row["ccf"] - mean), 6)
                    near_boundary = abs(distance - max_ccf_distance) <= boundary_ambiguity
                    assignment_state = (
                        SpecimenBetaState.AMBIGUOUS
                        if near_boundary
                        else SpecimenBetaState.SUPPORTED
                    )
                    assignments.append(
                        SubcloneAssignment(
                            sample_id=sample_id,
                            variant_id=row["variant_id"],
                            subclone_id=subclone_id,
                            cluster_mean_ccf=mean,
                            estimated_ccf=round(row["ccf"], 6),
                            distance_to_cluster_mean=distance,
                            assignment_state=assignment_state,
                            assignment_basis="single-linkage relative CCF cluster within sample",
                            raw_hash=row["raw_hash"],
                            content_address=content_hash(
                                {
                                    "sample_id": sample_id,
                                    "variant_id": row["variant_id"],
                                    "subclone_id": subclone_id,
                                    "ccf": row["ccf"],
                                }
                            ),
                        )
                    )
        if not assignments:
            state = SpecimenBetaState.ABSTAINED
        elif any(item.assignment_state == SpecimenBetaState.AMBIGUOUS for item in assignments):
            state = SpecimenBetaState.AMBIGUOUS
        elif issues:
            state = SpecimenBetaState.PARTIAL
        else:
            state = SpecimenBetaState.SUPPORTED
        return self._report(
            input_hash,
            state,
            tuple(
                sorted(
                    assignments,
                    key=lambda item: (item.sample_id, item.subclone_id, item.variant_id),
                )
            ),
            cluster_means,
            tuple(issues),
            (
                "Subclone IDs are relative CCF clusters within a sample and are not named "
                "biological clones.",
                "Clustering does not infer phylogeny, mutation order, or evolutionary lineage.",
            ),
        )

    @staticmethod
    def _report(
        input_hash: str,
        state: SpecimenBetaState,
        assignments: tuple[SubcloneAssignment, ...],
        cluster_means: Mapping[str, float],
        issues: tuple[SpecimenBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> SubcloneAssignmentBatch:
        body = {
            "input_hash": input_hash,
            "state": state,
            "assignments": assignments,
            "cluster_means": cluster_means,
            "issues": issues,
        }
        return SubcloneAssignmentBatch(
            input_hash=input_hash,
            state=state,
            assignments=assignments,
            cluster_means=dict(cluster_means),
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return default


def _raw_hash(row: Mapping[str, Any]) -> str:
    return str(row.get("raw_hash") or content_hash(dict(row)))


def _source_id(row: Mapping[str, Any]) -> str:
    return str(_value(row, "source_id", "source", "dataset_id", default="unspecified"))


def _fraction(value: Any) -> float | None:
    if value in {None, "", "."}:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("fraction must be numeric") from exc
    if result > 1 and result <= 100:
        result /= 100.0
    if not 0 <= result <= 1:
        raise ValidationError("fraction must be between zero and one")
    return result


def _optional_fraction(value: Any) -> float | None:
    try:
        return _fraction(value)
    except ValidationError:
        return None


def _number(value: Any, field_name: str) -> float:
    if value in {None, "", "."}:
        raise ValidationError(f"{field_name} is required")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{field_name} must be finite")
    return result


def _optional_int(value: Any) -> int | None:
    if value in {None, "", "."}:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _optional_bool(value: Any) -> bool | None:
    if value in {None, "", "."}:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "present", "supported"}


def _sigmoid(value: float) -> float:
    if value >= 40:
        return 1.0
    if value <= -40:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


__all__ = [
    "CancerCellFractionBatch",
    "CancerCellFractionEstimate",
    "CancerCellFractionEstimator",
    "MosaicismPosteriorBatch",
    "MosaicismPosteriorEstimate",
    "MosaicismPosteriorEstimator",
    "OriginClassification",
    "OriginClassificationBatch",
    "SomaticGermlineOriginClassifier",
    "SpecimenBetaIssue",
    "SpecimenBetaState",
    "SubcloneAssignment",
    "SubcloneAssignmentBatch",
    "SubcloneAssigner",
]
