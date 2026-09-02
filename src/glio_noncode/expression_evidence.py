"""Matched-tumour RNA consequence evidence with conservative abstention.

The module deliberately separates private, long-form measurements from the
sample-free results that may be placed on hypothesis and review surfaces.  It
uses only the Python standard library and the package's canonical serializer.

Two analyses are provided:

* a robust one-sample expression outlier comparison against a context-matched
  reference cohort, using median/MAD and a documented IQR fallback; and
* an exact allelic-imbalance test against a declared or copy-number/purity
  derived alternate-allele fraction, followed by deterministic BH correction.

Missing baselines, phase, depth, or dispersion never silently become evidence.
In particular, allelic balance is not assumed to be 0.5 when the baseline is
unknown.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from statistics import median
from typing import Any, TypeVar

from .errors import ValidationError
from .serialization import canonical_json, content_hash

SCHEMA_VERSION = "1.0.0"
MAX_EXACT_BINOMIAL_TRIALS = 100_000
_EXACT_BINOMIAL_DEPTH_LIMIT_REASON = "exact_binomial_depth_limit_exceeded"


class RNAEvidenceState(StrEnum):
    """Evidence outcomes kept distinct on downstream surfaces."""

    SUPPORTED = "supported"
    CONTRADICTORY = "contradictory"
    MEASURED_NEGATIVE = "measured_negative"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class ExpressionScale(StrEnum):
    """Declared expression scales; raw counts are ingestible but not comparable."""

    TPM = "tpm"
    CPM = "cpm"
    FPKM = "fpkm"
    RPKM = "rpkm"
    LOG2_TPM = "log2_tpm"
    LOG2_CPM = "log2_cpm"
    LOG2_FPKM = "log2_fpkm"
    VST = "vst"
    RLOG = "rlog"
    VOOM = "voom"
    RAW_COUNT = "raw_count"

    @property
    def cohort_comparable(self) -> bool:
        return self is not ExpressionScale.RAW_COUNT


class RegulatoryDirection(StrEnum):
    """Direction predicted for the alternate regulatory allele."""

    GAIN = "gain"
    LOSS = "loss"
    UNKNOWN = "unknown"


class ExpressionDirection(StrEnum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class AllelicDirection(StrEnum):
    ALT_ENRICHED = "alt_enriched"
    REF_ENRICHED = "ref_enriched"
    BALANCED = "balanced"
    UNKNOWN = "unknown"


class PhaseStatus(StrEnum):
    """Whether the counted alternate allele is linked to the tested allele."""

    PHASED = "phased"
    UNPHASED = "unphased"
    UNKNOWN = "unknown"


class DispersionMethod(StrEnum):
    MAD = "mad"
    IQR = "iqr"
    NONE = "none"


class ExpectedFractionMethod(StrEnum):
    DECLARED = "declared"
    COPY_NUMBER_PURITY = "copy_number_purity"
    MISSING = "missing"


_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@|/+\-=]{0,255}\Z")
_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _text(value: object, field_name: str, *, key: bool = False) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field_name} must not be empty")
    if len(normalized) > 512 or any(ord(character) < 32 for character in normalized):
        raise ValidationError(f"{field_name} contains invalid characters")
    if key and not _KEY_RE.fullmatch(normalized):
        raise ValidationError(f"{field_name} is not a valid opaque key")
    return normalized


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{field_name} must be finite")
    return result


def _count(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer")
    if value < 0:
        raise ValidationError(f"{field_name} must not be negative")
    return value


def _enum(value: object, enum_type: type[_EnumT], field_name: str) -> _EnumT:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        choices = ", ".join(item.value for item in enum_type)
        raise ValidationError(f"{field_name} must be one of: {choices}") from error


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be a mapping")
    return value


def _json_mapping(text: str, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{label} must be valid JSON") from error
    return _mapping(value, label)


def _verify_address(raw: Mapping[str, Any], actual: str, label: str) -> None:
    declared = raw.get("content_address")
    if declared is not None and declared != actual:
        raise ValidationError(f"{label} content_address does not match its canonical content")


@dataclass(frozen=True, slots=True)
class ExpressionObservation:
    """One private long-form expression measurement."""

    feature_id: str
    sample_key: str
    value: float
    scale: ExpressionScale
    context_key: str
    source_id: str
    source_version: str = "unspecified"

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", _text(self.feature_id, "feature_id", key=True))
        object.__setattr__(self, "sample_key", _text(self.sample_key, "sample_key", key=True))
        object.__setattr__(self, "value", _finite(self.value, "expression value"))
        object.__setattr__(self, "scale", _enum(self.scale, ExpressionScale, "expression scale"))
        object.__setattr__(self, "context_key", _text(self.context_key, "context_key"))
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id", key=True))
        object.__setattr__(
            self,
            "source_version",
            _text(self.source_version, "source_version", key=True),
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "feature_id": self.feature_id,
            "sample_key": self.sample_key,
            "value": self.value,
            "scale": self.scale.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="expression-observation")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        """Project the measurement without its private sample key or value."""

        return {
            "schema_version": SCHEMA_VERSION,
            "feature_id": self.feature_id,
            "scale": self.scale.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "content_address": self.content_address,
        }

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ExpressionObservation:
        value = _mapping(raw, "expression observation")
        result = cls(
            feature_id=value.get("feature_id"),
            sample_key=value.get("sample_key"),
            value=value.get("value"),
            scale=value.get("scale"),
            context_key=value.get("context_key"),
            source_id=value.get("source_id"),
            source_version=value.get("source_version", "unspecified"),
        )
        _verify_address(value, result.content_address, "expression observation")
        return result

    @classmethod
    def from_json(cls, text: str) -> ExpressionObservation:
        return cls.from_mapping(_json_mapping(text, "expression observation"))


@dataclass(frozen=True, slots=True)
class ExpressionBatch:
    """A canonical, internally homogeneous collection of long-form rows."""

    observations: tuple[ExpressionObservation, ...]

    def __post_init__(self) -> None:
        values = tuple(self.observations)
        if not values:
            raise ValidationError("expression batch must contain observations")
        if any(not isinstance(item, ExpressionObservation) for item in values):
            raise ValidationError("expression batch rows must be ExpressionObservation objects")
        ordered = tuple(sorted(
            values,
            key=lambda item: (item.feature_id, item.sample_key, item.content_address),
        ))
        keys = [(item.feature_id, item.sample_key) for item in ordered]
        if len(keys) != len(set(keys)):
            raise ValidationError("expression batch contains duplicate feature/sample keys")
        for attribute, label in (
            ("scale", "scales"),
            ("context_key", "contexts"),
            ("source_id", "sources"),
            ("source_version", "source versions"),
        ):
            if len({getattr(item, attribute) for item in ordered}) != 1:
                raise ValidationError(f"expression batch must not mix {label}")
        object.__setattr__(self, "observations", ordered)

    @classmethod
    def from_observations(cls, observations: Iterable[ExpressionObservation]) -> ExpressionBatch:
        return cls(tuple(observations))

    @property
    def scale(self) -> ExpressionScale:
        return self.observations[0].scale

    @property
    def context_key(self) -> str:
        return self.observations[0].context_key

    @property
    def source_id(self) -> str:
        return self.observations[0].source_id

    @property
    def source_version(self) -> str:
        return self.observations[0].source_version

    @property
    def feature_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item.feature_id for item in self.observations}))

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "scale": self.scale.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "observations": [item.to_dict() for item in self.observations],
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="expression-batch")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "scale": self.scale.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "feature_ids": list(self.feature_ids),
            "observation_count": len(self.observations),
            "content_address": self.content_address,
        }

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ExpressionBatch:
        value = _mapping(raw, "expression batch")
        rows = value.get("observations")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValidationError("expression batch observations must be a sequence")
        result = cls(tuple(
            ExpressionObservation.from_mapping(_mapping(row, "row")) for row in rows
        ))
        declared = {
            "scale": result.scale.value,
            "context_key": result.context_key,
            "source_id": result.source_id,
            "source_version": result.source_version,
        }
        for field_name, actual in declared.items():
            if field_name in value and value[field_name] != actual:
                raise ValidationError(f"expression batch {field_name} disagrees with its rows")
        _verify_address(value, result.content_address, "expression batch")
        return result

    @classmethod
    def from_json(cls, text: str) -> ExpressionBatch:
        return cls.from_mapping(_json_mapping(text, "expression batch"))


@dataclass(frozen=True, slots=True)
class RobustOutlierPolicy:
    min_reference_count: int = 5
    z_threshold: float = 3.5
    mad_consistency_constant: float = 1.4826
    iqr_consistency_constant: float = 1.349

    def __post_init__(self) -> None:
        if isinstance(self.min_reference_count, bool) or self.min_reference_count < 3:
            raise ValidationError("min_reference_count must be an integer of at least 3")
        for field_name in (
            "z_threshold",
            "mad_consistency_constant",
            "iqr_consistency_constant",
        ):
            value = _finite(getattr(self, field_name), field_name)
            if value <= 0:
                raise ValidationError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True, slots=True)
class ExpressionOutlierResult:
    """Sample-free robust expression result suitable for evidence surfaces."""

    feature_id: str
    context_key: str
    scale: ExpressionScale
    state: RNAEvidenceState
    direction: ExpressionDirection
    target_value: float
    reference_count: int
    reference_median: float | None
    dispersion: float | None
    dispersion_method: DispersionMethod
    robust_z: float | None
    z_threshold: float
    expected_direction: RegulatoryDirection | None
    reason_codes: tuple[str, ...]
    target_observation_address: str
    reference_batch_address: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", _text(self.feature_id, "feature_id", key=True))
        object.__setattr__(self, "context_key", _text(self.context_key, "context_key"))
        object.__setattr__(self, "scale", _enum(self.scale, ExpressionScale, "scale"))
        object.__setattr__(self, "state", _enum(self.state, RNAEvidenceState, "state"))
        object.__setattr__(
            self, "direction", _enum(self.direction, ExpressionDirection, "direction")
        )
        object.__setattr__(self, "dispersion_method", _enum(
            self.dispersion_method, DispersionMethod, "dispersion_method"
        ))
        object.__setattr__(self, "target_value", _finite(self.target_value, "target_value"))
        _count(self.reference_count, "reference_count")
        for field_name in ("reference_median", "dispersion", "robust_z"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _finite(value, field_name))
        object.__setattr__(self, "z_threshold", _finite(self.z_threshold, "z_threshold"))
        if self.expected_direction is not None:
            object.__setattr__(self, "expected_direction", _enum(
                self.expected_direction, RegulatoryDirection, "expected_direction"
            ))
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))
        _text(self.target_observation_address, "target_observation_address")
        _text(self.reference_batch_address, "reference_batch_address")

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "feature_id": self.feature_id,
            "context_key": self.context_key,
            "scale": self.scale.value,
            "state": self.state.value,
            "direction": self.direction.value,
            "target_value": self.target_value,
            "reference_count": self.reference_count,
            "reference_median": self.reference_median,
            "dispersion": self.dispersion,
            "dispersion_method": self.dispersion_method.value,
            "robust_z": self.robust_z,
            "z_threshold": self.z_threshold,
            "expected_direction": (
                self.expected_direction.value if self.expected_direction is not None else None
            ),
            "reason_codes": list(self.reason_codes),
            "target_observation_address": self.target_observation_address,
            "reference_batch_address": self.reference_batch_address,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="expression-outlier")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        return self.to_dict()

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ExpressionOutlierResult:
        value = _mapping(raw, "expression outlier result")
        result = cls(
            feature_id=value.get("feature_id"),
            context_key=value.get("context_key"),
            scale=value.get("scale"),
            state=value.get("state"),
            direction=value.get("direction"),
            target_value=value.get("target_value"),
            reference_count=value.get("reference_count"),
            reference_median=value.get("reference_median"),
            dispersion=value.get("dispersion"),
            dispersion_method=value.get("dispersion_method"),
            robust_z=value.get("robust_z"),
            z_threshold=value.get("z_threshold"),
            expected_direction=value.get("expected_direction"),
            reason_codes=tuple(value.get("reason_codes", ())),
            target_observation_address=value.get("target_observation_address"),
            reference_batch_address=value.get("reference_batch_address"),
        )
        _verify_address(value, result.content_address, "expression outlier result")
        return result

    @classmethod
    def from_json(cls, text: str) -> ExpressionOutlierResult:
        return cls.from_mapping(_json_mapping(text, "expression outlier result"))


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


class RobustExpressionOutlierAnalyzer:
    """Compare one tumour measurement to a homogeneous reference batch."""

    def __init__(self, policy: RobustOutlierPolicy | None = None) -> None:
        self.policy = policy or RobustOutlierPolicy()

    def analyze(
        self,
        target: ExpressionObservation,
        references: ExpressionBatch,
        *,
        expected_direction: RegulatoryDirection | str | None = None,
        expected_context_key: str | None = None,
    ) -> ExpressionOutlierResult:
        if not isinstance(target, ExpressionObservation):
            raise ValidationError("target must be an ExpressionObservation")
        if not isinstance(references, ExpressionBatch):
            raise ValidationError("references must be an ExpressionBatch")
        expected = (
            None
            if expected_direction is None
            else _enum(expected_direction, RegulatoryDirection, "expected_direction")
        )
        requested_context = (
            None
            if expected_context_key is None
            else _text(expected_context_key, "expected_context_key")
        )
        base = {
            "feature_id": target.feature_id,
            "context_key": target.context_key,
            "scale": target.scale,
            "target_value": target.value,
            "z_threshold": self.policy.z_threshold,
            "expected_direction": expected,
            "target_observation_address": target.content_address,
            "reference_batch_address": references.content_address,
        }

        def unresolved(state: RNAEvidenceState, *reasons: str) -> ExpressionOutlierResult:
            return ExpressionOutlierResult(
                **base,
                state=state,
                direction=ExpressionDirection.UNKNOWN,
                reference_count=0,
                reference_median=None,
                dispersion=None,
                dispersion_method=DispersionMethod.NONE,
                robust_z=None,
                reason_codes=tuple(reasons),
            )

        if requested_context is not None and target.context_key != requested_context:
            return unresolved(RNAEvidenceState.OUT_OF_DOMAIN, "target_context_mismatch")
        if target.context_key != references.context_key:
            return unresolved(RNAEvidenceState.OUT_OF_DOMAIN, "reference_context_mismatch")
        if target.scale != references.scale:
            return unresolved(RNAEvidenceState.OUT_OF_DOMAIN, "expression_scale_mismatch")
        if not target.scale.cohort_comparable:
            return unresolved(RNAEvidenceState.OUT_OF_DOMAIN, "unnormalized_expression_scale")

        same_feature = [
            item for item in references.observations if item.feature_id == target.feature_id
        ]
        if not same_feature:
            return unresolved(RNAEvidenceState.OUT_OF_DOMAIN, "feature_not_in_reference")
        cohort = [item.value for item in same_feature if item.sample_key != target.sample_key]
        if len(cohort) < self.policy.min_reference_count:
            result = unresolved(RNAEvidenceState.ABSTAINED, "insufficient_reference_count")
            return replace(result, reference_count=len(cohort))

        center = float(median(cohort))
        mad = float(median(abs(value - center) for value in cohort))
        method = DispersionMethod.MAD
        spread = mad * self.policy.mad_consistency_constant
        reason_codes: tuple[str, ...] = ()
        if spread == 0.0:
            iqr = _quantile(cohort, 0.75) - _quantile(cohort, 0.25)
            spread = iqr / self.policy.iqr_consistency_constant
            method = DispersionMethod.IQR
            reason_codes = ("mad_zero_iqr_fallback",)
        if spread == 0.0:
            return ExpressionOutlierResult(
                **base,
                state=RNAEvidenceState.ABSTAINED,
                direction=ExpressionDirection.UNKNOWN,
                reference_count=len(cohort),
                reference_median=center,
                dispersion=None,
                dispersion_method=DispersionMethod.NONE,
                robust_z=None,
                reason_codes=("zero_reference_dispersion",),
            )

        robust_z = (target.value - center) / spread
        if robust_z > 0:
            direction = ExpressionDirection.UP
        elif robust_z < 0:
            direction = ExpressionDirection.DOWN
        else:
            direction = ExpressionDirection.NEUTRAL
        significant = abs(robust_z) >= self.policy.z_threshold
        if not significant:
            state = RNAEvidenceState.MEASURED_NEGATIVE
            reason_codes += ("no_expression_outlier",)
        else:
            expected_observed = {
                RegulatoryDirection.GAIN: ExpressionDirection.UP,
                RegulatoryDirection.LOSS: ExpressionDirection.DOWN,
            }.get(expected)
            if expected_observed is not None and direction is not expected_observed:
                state = RNAEvidenceState.CONTRADICTORY
                reason_codes += ("outlier_opposes_prediction",)
            else:
                state = RNAEvidenceState.SUPPORTED
                reason_codes += ("expression_outlier_detected",)
        return ExpressionOutlierResult(
            **base,
            state=state,
            direction=direction,
            reference_count=len(cohort),
            reference_median=center,
            dispersion=spread,
            dispersion_method=method,
            robust_z=robust_z,
            reason_codes=reason_codes,
        )


ExpressionOutlierAnalyzer = RobustExpressionOutlierAnalyzer


def analyze_expression_outlier(
    target: ExpressionObservation,
    references: ExpressionBatch,
    *,
    expected_direction: RegulatoryDirection | str | None = None,
    policy: RobustOutlierPolicy | None = None,
    expected_context_key: str | None = None,
) -> ExpressionOutlierResult:
    return RobustExpressionOutlierAnalyzer(policy).analyze(
        target,
        references,
        expected_direction=expected_direction,
        expected_context_key=expected_context_key,
    )


@dataclass(frozen=True, slots=True)
class AllelicCountObservation:
    """Private ref/alt/other RNA counts and a non-naive expected baseline."""

    feature_id: str
    variant_id: str
    sample_key: str
    ref_count: int
    alt_count: int
    phase: PhaseStatus
    context_key: str
    source_id: str
    source_version: str = "unspecified"
    other_count: int = 0
    expected_alt_fraction: float | None = None
    ref_copy_number: float | None = None
    alt_copy_number: float | None = None
    purity: float | None = None
    normal_ref_copy_number: float = 1.0
    normal_alt_copy_number: float = 1.0
    mapping_bias: float | None = None
    mapping_bias_flag: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", _text(self.feature_id, "feature_id", key=True))
        object.__setattr__(self, "variant_id", _text(self.variant_id, "variant_id", key=True))
        object.__setattr__(self, "sample_key", _text(self.sample_key, "sample_key", key=True))
        object.__setattr__(self, "ref_count", _count(self.ref_count, "ref_count"))
        object.__setattr__(self, "alt_count", _count(self.alt_count, "alt_count"))
        object.__setattr__(self, "other_count", _count(self.other_count, "other_count"))
        object.__setattr__(self, "phase", _enum(self.phase, PhaseStatus, "phase"))
        object.__setattr__(self, "context_key", _text(self.context_key, "context_key"))
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id", key=True))
        object.__setattr__(
            self,
            "source_version",
            _text(self.source_version, "source_version", key=True),
        )
        if not isinstance(self.mapping_bias_flag, bool):
            raise ValidationError("mapping_bias_flag must be boolean")
        if self.mapping_bias is not None:
            bias = _finite(self.mapping_bias, "mapping_bias")
            if not -1.0 <= bias <= 1.0:
                raise ValidationError("mapping_bias must be between -1 and 1")
            object.__setattr__(self, "mapping_bias", bias)
        if self.expected_alt_fraction is not None:
            expected = _finite(self.expected_alt_fraction, "expected_alt_fraction")
            if not 0.0 <= expected <= 1.0:
                raise ValidationError("expected_alt_fraction must be between 0 and 1")
            object.__setattr__(self, "expected_alt_fraction", expected)

        copy_fields = (self.ref_copy_number, self.alt_copy_number, self.purity)
        if any(value is not None for value in copy_fields) and not all(
            value is not None for value in copy_fields
        ):
            raise ValidationError(
                "ref_copy_number, alt_copy_number, and purity must be supplied together"
            )
        for field_name in (
            "ref_copy_number",
            "alt_copy_number",
            "normal_ref_copy_number",
            "normal_alt_copy_number",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            normalized = _finite(value, field_name)
            if normalized < 0:
                raise ValidationError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, normalized)
        if self.purity is not None:
            purity = _finite(self.purity, "purity")
            if not 0.0 <= purity <= 1.0:
                raise ValidationError("purity must be between 0 and 1")
            object.__setattr__(self, "purity", purity)
            derived = self._copy_number_expected_fraction()
            if self.expected_alt_fraction is not None and not math.isclose(
                self.expected_alt_fraction, derived, rel_tol=1e-9, abs_tol=1e-12
            ):
                raise ValidationError(
                    "declared expected_alt_fraction conflicts with copy-number/purity baseline"
                )

    @property
    def informative_depth(self) -> int:
        return self.ref_count + self.alt_count

    @property
    def total_depth(self) -> int:
        return self.informative_depth + self.other_count

    def _copy_number_expected_fraction(self) -> float:
        assert self.ref_copy_number is not None
        assert self.alt_copy_number is not None
        assert self.purity is not None
        alt_mass = (
            self.purity * self.alt_copy_number
            + (1.0 - self.purity) * self.normal_alt_copy_number
        )
        ref_mass = (
            self.purity * self.ref_copy_number
            + (1.0 - self.purity) * self.normal_ref_copy_number
        )
        denominator = alt_mass + ref_mass
        if denominator <= 0.0:
            raise ValidationError("copy-number/purity baseline has zero total allele mass")
        return alt_mass / denominator

    @property
    def resolved_expected_alt_fraction(self) -> float | None:
        if self.expected_alt_fraction is not None:
            return self.expected_alt_fraction
        if self.purity is not None:
            return self._copy_number_expected_fraction()
        return None

    @property
    def expected_fraction_method(self) -> ExpectedFractionMethod:
        if self.expected_alt_fraction is not None:
            return ExpectedFractionMethod.DECLARED
        if self.purity is not None:
            return ExpectedFractionMethod.COPY_NUMBER_PURITY
        return ExpectedFractionMethod.MISSING

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "feature_id": self.feature_id,
            "variant_id": self.variant_id,
            "sample_key": self.sample_key,
            "ref_count": self.ref_count,
            "alt_count": self.alt_count,
            "other_count": self.other_count,
            "phase": self.phase.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "expected_alt_fraction": self.expected_alt_fraction,
            "ref_copy_number": self.ref_copy_number,
            "alt_copy_number": self.alt_copy_number,
            "purity": self.purity,
            "normal_ref_copy_number": self.normal_ref_copy_number,
            "normal_alt_copy_number": self.normal_alt_copy_number,
            "mapping_bias": self.mapping_bias,
            "mapping_bias_flag": self.mapping_bias_flag,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="allelic-count-observation")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "feature_id": self.feature_id,
            "variant_id": self.variant_id,
            "phase": self.phase.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "content_address": self.content_address,
        }

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> AllelicCountObservation:
        value = _mapping(raw, "allelic count observation")
        result = cls(
            feature_id=value.get("feature_id"),
            variant_id=value.get("variant_id"),
            sample_key=value.get("sample_key"),
            ref_count=value.get("ref_count"),
            alt_count=value.get("alt_count"),
            other_count=value.get("other_count", 0),
            phase=value.get("phase"),
            context_key=value.get("context_key"),
            source_id=value.get("source_id"),
            source_version=value.get("source_version", "unspecified"),
            expected_alt_fraction=value.get("expected_alt_fraction"),
            ref_copy_number=value.get("ref_copy_number"),
            alt_copy_number=value.get("alt_copy_number"),
            purity=value.get("purity", value.get("tumor_purity")),
            normal_ref_copy_number=value.get("normal_ref_copy_number", 1.0),
            normal_alt_copy_number=value.get("normal_alt_copy_number", 1.0),
            mapping_bias=value.get("mapping_bias"),
            mapping_bias_flag=value.get("mapping_bias_flag", False),
        )
        _verify_address(value, result.content_address, "allelic count observation")
        return result

    @classmethod
    def from_json(cls, text: str) -> AllelicCountObservation:
        return cls.from_mapping(_json_mapping(text, "allelic count observation"))


@dataclass(frozen=True, slots=True)
class AllelicCountBatch:
    """Canonical allelic rows from one source and biological context."""

    observations: tuple[AllelicCountObservation, ...]

    def __post_init__(self) -> None:
        values = tuple(self.observations)
        if not values:
            raise ValidationError("allelic count batch must contain observations")
        if any(not isinstance(item, AllelicCountObservation) for item in values):
            raise ValidationError("allelic batch rows must be AllelicCountObservation objects")
        ordered = tuple(sorted(values, key=lambda item: (
            item.feature_id, item.variant_id, item.sample_key, item.content_address
        )))
        keys = [(item.feature_id, item.variant_id, item.sample_key) for item in ordered]
        if len(keys) != len(set(keys)):
            raise ValidationError(
                "allelic count batch contains duplicate feature/variant/sample keys"
            )
        for attribute, label in (
            ("context_key", "contexts"),
            ("source_id", "sources"),
            ("source_version", "source versions"),
        ):
            if len({getattr(item, attribute) for item in ordered}) != 1:
                raise ValidationError(f"allelic count batch must not mix {label}")
        object.__setattr__(self, "observations", ordered)

    @classmethod
    def from_observations(
        cls, observations: Iterable[AllelicCountObservation]
    ) -> AllelicCountBatch:
        return cls(tuple(observations))

    @property
    def context_key(self) -> str:
        return self.observations[0].context_key

    @property
    def source_id(self) -> str:
        return self.observations[0].source_id

    @property
    def source_version(self) -> str:
        return self.observations[0].source_version

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "observations": [item.to_dict() for item in self.observations],
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="allelic-count-batch")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "observation_count": len(self.observations),
            "feature_count": len({item.feature_id for item in self.observations}),
            "variant_count": len({item.variant_id for item in self.observations}),
            "content_address": self.content_address,
        }

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> AllelicCountBatch:
        value = _mapping(raw, "allelic count batch")
        rows = value.get("observations")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValidationError("allelic count batch observations must be a sequence")
        result = cls(tuple(
            AllelicCountObservation.from_mapping(_mapping(row, "row")) for row in rows
        ))
        for field_name, actual in (
            ("context_key", result.context_key),
            ("source_id", result.source_id),
            ("source_version", result.source_version),
        ):
            if field_name in value and value[field_name] != actual:
                raise ValidationError(f"allelic count batch {field_name} disagrees with its rows")
        _verify_address(value, result.content_address, "allelic count batch")
        return result

    @classmethod
    def from_json(cls, text: str) -> AllelicCountBatch:
        return cls.from_mapping(_json_mapping(text, "allelic count batch"))


def exact_two_sided_binomial_pvalue(successes: int, trials: int, probability: float) -> float:
    """Return the probability-ordering exact two-sided binomial p-value.

    This matches the definition used by exact binomial tests: sum the null
    probabilities of every outcome no more likely than the observed outcome.
    Computation is in log space to avoid overflowing ``comb`` or underflowing
    individual probability products.  Runtime is linear in ``trials``, so the
    public function rejects values above :data:`MAX_EXACT_BINOMIAL_TRIALS`
    before entering the exact enumeration.
    """

    successes = _count(successes, "successes")
    trials = _count(trials, "trials")
    if successes > trials:
        raise ValidationError("successes must not exceed trials")
    if trials > MAX_EXACT_BINOMIAL_TRIALS:
        raise ValidationError(
            "trials must not exceed "
            f"MAX_EXACT_BINOMIAL_TRIALS ({MAX_EXACT_BINOMIAL_TRIALS})"
        )
    probability = _finite(probability, "probability")
    if not 0.0 <= probability <= 1.0:
        raise ValidationError("probability must be between 0 and 1")
    if trials == 0:
        return 1.0
    if probability == 0.0:
        return 1.0 if successes == 0 else 0.0
    if probability == 1.0:
        return 1.0 if successes == trials else 0.0

    log_p = math.log(probability)
    log_q = math.log1p(-probability)

    def log_pmf(count: int) -> float:
        return (
            math.lgamma(trials + 1)
            - math.lgamma(count + 1)
            - math.lgamma(trials - count + 1)
            + count * log_p
            + (trials - count) * log_q
        )

    observed = log_pmf(successes)
    maximum = -math.inf
    scaled_sum = 0.0
    tolerance = 1e-12 * max(1.0, abs(observed))
    for count in range(trials + 1):
        candidate = log_pmf(count)
        if candidate > observed + tolerance:
            continue
        if candidate > maximum:
            scaled_sum = scaled_sum * math.exp(maximum - candidate) + 1.0
            maximum = candidate
        else:
            scaled_sum += math.exp(candidate - maximum)
    if maximum == -math.inf:
        return 0.0
    return min(1.0, math.exp(maximum + math.log(scaled_sum)))


exact_binomial_two_sided_p_value = exact_two_sided_binomial_pvalue
two_sided_binomial_p_value = exact_two_sided_binomial_pvalue


def benjamini_hochberg(p_values: Sequence[float]) -> tuple[float, ...]:
    """Adjust finite p-values while preserving caller order and stable ties."""

    normalized = tuple(_finite(value, "p_value") for value in p_values)
    if any(not 0.0 <= value <= 1.0 for value in normalized):
        raise ValidationError("p_values must be between 0 and 1")
    size = len(normalized)
    if size == 0:
        return ()
    ranked = sorted(enumerate(normalized), key=lambda item: (item[1], item[0]))
    adjusted = [1.0] * size
    running = 1.0
    for rank_index in range(size - 1, -1, -1):
        original_index, p_value = ranked[rank_index]
        rank = rank_index + 1
        running = min(running, p_value * size / rank)
        adjusted[original_index] = min(1.0, running)
    return tuple(adjusted)


@dataclass(frozen=True, slots=True)
class AllelicImbalancePolicy:
    """QC and bounded-computation policy for exact allelic inference."""

    min_informative_depth: int = 20
    max_other_fraction: float = 0.10
    max_abs_mapping_bias: float = 0.10
    alpha: float = 0.05
    max_informative_depth: int = MAX_EXACT_BINOMIAL_TRIALS

    def __post_init__(self) -> None:
        if (
            isinstance(self.min_informative_depth, bool)
            or not isinstance(self.min_informative_depth, int)
            or self.min_informative_depth < 1
        ):
            raise ValidationError("min_informative_depth must be a positive integer")
        if (
            isinstance(self.max_informative_depth, bool)
            or not isinstance(self.max_informative_depth, int)
            or self.max_informative_depth < 1
        ):
            raise ValidationError("max_informative_depth must be a positive integer")
        if self.max_informative_depth < self.min_informative_depth:
            raise ValidationError(
                "max_informative_depth must be at least min_informative_depth"
            )
        if self.max_informative_depth > MAX_EXACT_BINOMIAL_TRIALS:
            raise ValidationError(
                "max_informative_depth must not exceed "
                f"MAX_EXACT_BINOMIAL_TRIALS ({MAX_EXACT_BINOMIAL_TRIALS})"
            )
        for field_name in ("max_other_fraction", "max_abs_mapping_bias", "alpha"):
            value = _finite(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{field_name} must be between 0 and 1")
            object.__setattr__(self, field_name, value)
        if self.alpha == 0.0:
            raise ValidationError("alpha must be positive")


@dataclass(frozen=True, slots=True)
class AllelicImbalanceResult:
    """Sample-free exact allelic-imbalance result."""

    feature_id: str
    variant_id: str
    context_key: str
    state: RNAEvidenceState
    direction: AllelicDirection
    informative_depth: int
    other_count: int
    observed_alt_fraction: float | None
    expected_alt_fraction: float | None
    expected_fraction_method: ExpectedFractionMethod
    p_value: float | None
    q_value: float | None
    log2_ratio: float | None
    expected_direction: RegulatoryDirection | None
    reason_codes: tuple[str, ...]
    observation_address: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", _text(self.feature_id, "feature_id", key=True))
        object.__setattr__(self, "variant_id", _text(self.variant_id, "variant_id", key=True))
        object.__setattr__(self, "context_key", _text(self.context_key, "context_key"))
        object.__setattr__(self, "state", _enum(self.state, RNAEvidenceState, "state"))
        object.__setattr__(
            self, "direction", _enum(self.direction, AllelicDirection, "direction")
        )
        object.__setattr__(self, "informative_depth", _count(
            self.informative_depth, "informative_depth"
        ))
        object.__setattr__(self, "other_count", _count(self.other_count, "other_count"))
        for field_name in (
            "observed_alt_fraction",
            "expected_alt_fraction",
            "p_value",
            "q_value",
            "log2_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _finite(value, field_name))
        for field_name in (
            "observed_alt_fraction",
            "expected_alt_fraction",
            "p_value",
            "q_value",
        ):
            value = getattr(self, field_name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValidationError(f"{field_name} must be between 0 and 1")
        object.__setattr__(self, "expected_fraction_method", _enum(
            self.expected_fraction_method,
            ExpectedFractionMethod,
            "expected_fraction_method",
        ))
        if self.expected_direction is not None:
            object.__setattr__(self, "expected_direction", _enum(
                self.expected_direction, RegulatoryDirection, "expected_direction"
            ))
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))
        _text(self.observation_address, "observation_address")

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "feature_id": self.feature_id,
            "variant_id": self.variant_id,
            "context_key": self.context_key,
            "state": self.state.value,
            "direction": self.direction.value,
            "informative_depth": self.informative_depth,
            "other_count": self.other_count,
            "observed_alt_fraction": self.observed_alt_fraction,
            "expected_alt_fraction": self.expected_alt_fraction,
            "expected_fraction_method": self.expected_fraction_method.value,
            "p_value": self.p_value,
            "q_value": self.q_value,
            "log2_ratio": self.log2_ratio,
            "expected_direction": (
                self.expected_direction.value if self.expected_direction is not None else None
            ),
            "reason_codes": list(self.reason_codes),
            "observation_address": self.observation_address,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="allelic-imbalance")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        return self.to_dict()

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> AllelicImbalanceResult:
        value = _mapping(raw, "allelic imbalance result")
        result = cls(
            feature_id=value.get("feature_id"),
            variant_id=value.get("variant_id"),
            context_key=value.get("context_key"),
            state=value.get("state"),
            direction=value.get("direction"),
            informative_depth=value.get("informative_depth"),
            other_count=value.get("other_count"),
            observed_alt_fraction=value.get("observed_alt_fraction"),
            expected_alt_fraction=value.get("expected_alt_fraction"),
            expected_fraction_method=value.get("expected_fraction_method"),
            p_value=value.get("p_value"),
            q_value=value.get("q_value"),
            log2_ratio=value.get("log2_ratio"),
            expected_direction=value.get("expected_direction"),
            reason_codes=tuple(value.get("reason_codes", ())),
            observation_address=value.get("observation_address"),
        )
        _verify_address(value, result.content_address, "allelic imbalance result")
        return result

    @classmethod
    def from_json(cls, text: str) -> AllelicImbalanceResult:
        return cls.from_mapping(_json_mapping(text, "allelic imbalance result"))


def _log2_expected_adjusted_odds(
    alt_count: int, ref_count: int, expected_alt_fraction: float
) -> float | None:
    if expected_alt_fraction in {0.0, 1.0}:
        return None
    if alt_count == 0 or ref_count == 0:
        observed_odds = (alt_count + 0.5) / (ref_count + 0.5)
    else:
        observed_odds = alt_count / ref_count
    expected_odds = expected_alt_fraction / (1.0 - expected_alt_fraction)
    return math.log2(observed_odds / expected_odds)


def _allelic_direction(observed: float, expected: float) -> AllelicDirection:
    if math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-15):
        return AllelicDirection.BALANCED
    return (
        AllelicDirection.ALT_ENRICHED
        if observed > expected
        else AllelicDirection.REF_ENRICHED
    )


def _classify_allelic(
    direction: AllelicDirection,
    q_value: float,
    alpha: float,
    expected: RegulatoryDirection | None,
) -> tuple[RNAEvidenceState, str]:
    if q_value > alpha:
        return RNAEvidenceState.MEASURED_NEGATIVE, "no_significant_allelic_imbalance"
    expected_observed = {
        RegulatoryDirection.GAIN: AllelicDirection.ALT_ENRICHED,
        RegulatoryDirection.LOSS: AllelicDirection.REF_ENRICHED,
    }.get(expected)
    if expected_observed is not None and direction is not expected_observed:
        return RNAEvidenceState.CONTRADICTORY, "allelic_imbalance_opposes_prediction"
    return RNAEvidenceState.SUPPORTED, "allelic_imbalance_detected"


class AllelicImbalanceAnalyzer:
    """Apply phase/QC gates and bounded exact inference to allelic counts.

    Depth above the policy maximum is an explicit abstention: the observation
    may remain biologically in-domain, but exact enumeration was not performed.
    """

    def __init__(self, policy: AllelicImbalancePolicy | None = None) -> None:
        self.policy = policy or AllelicImbalancePolicy()

    def analyze(
        self,
        observation: AllelicCountObservation,
        *,
        expected_direction: RegulatoryDirection | str | None = None,
        expected_context_key: str | None = None,
    ) -> AllelicImbalanceResult:
        return self._analyze_one(
            observation,
            expected_direction=expected_direction,
            expected_context_key=expected_context_key,
        )

    def _analyze_one(
        self,
        observation: AllelicCountObservation,
        *,
        expected_direction: RegulatoryDirection | str | None,
        expected_context_key: str | None,
    ) -> AllelicImbalanceResult:
        if not isinstance(observation, AllelicCountObservation):
            raise ValidationError("observation must be an AllelicCountObservation")
        expected = (
            None
            if expected_direction is None
            else _enum(expected_direction, RegulatoryDirection, "expected_direction")
        )
        requested_context = (
            None
            if expected_context_key is None
            else _text(expected_context_key, "expected_context_key")
        )
        baseline = observation.resolved_expected_alt_fraction
        base = {
            "feature_id": observation.feature_id,
            "variant_id": observation.variant_id,
            "context_key": observation.context_key,
            "informative_depth": observation.informative_depth,
            "other_count": observation.other_count,
            "expected_alt_fraction": baseline,
            "expected_fraction_method": observation.expected_fraction_method,
            "expected_direction": expected,
            "observation_address": observation.content_address,
        }

        def abstain(state: RNAEvidenceState, reason: str) -> AllelicImbalanceResult:
            return AllelicImbalanceResult(
                **base,
                state=state,
                direction=AllelicDirection.UNKNOWN,
                observed_alt_fraction=(
                    observation.alt_count / observation.informative_depth
                    if observation.informative_depth
                    else None
                ),
                p_value=None,
                q_value=None,
                log2_ratio=None,
                reason_codes=(reason,),
            )

        if requested_context is not None and observation.context_key != requested_context:
            return abstain(RNAEvidenceState.OUT_OF_DOMAIN, "context_mismatch")
        if observation.phase is not PhaseStatus.PHASED:
            return abstain(RNAEvidenceState.ABSTAINED, "allele_phase_unresolved")
        if observation.informative_depth < self.policy.min_informative_depth:
            return abstain(RNAEvidenceState.ABSTAINED, "low_informative_depth")
        if observation.informative_depth > self.policy.max_informative_depth:
            return abstain(
                RNAEvidenceState.ABSTAINED,
                _EXACT_BINOMIAL_DEPTH_LIMIT_REASON,
            )
        if observation.total_depth and (
            observation.other_count / observation.total_depth > self.policy.max_other_fraction
        ):
            return abstain(RNAEvidenceState.ABSTAINED, "excess_other_allele_fraction")
        if observation.mapping_bias_flag or (
            observation.mapping_bias is not None
            and abs(observation.mapping_bias) > self.policy.max_abs_mapping_bias
        ):
            return abstain(RNAEvidenceState.ABSTAINED, "mapping_bias")
        if baseline is None:
            return abstain(RNAEvidenceState.ABSTAINED, "missing_expected_alt_fraction")

        observed = observation.alt_count / observation.informative_depth
        direction = _allelic_direction(observed, baseline)
        p_value = exact_two_sided_binomial_pvalue(
            observation.alt_count, observation.informative_depth, baseline
        )
        state, reason = _classify_allelic(direction, p_value, self.policy.alpha, expected)
        return AllelicImbalanceResult(
            **base,
            state=state,
            direction=direction,
            observed_alt_fraction=observed,
            p_value=p_value,
            q_value=p_value,
            log2_ratio=_log2_expected_adjusted_odds(
                observation.alt_count, observation.ref_count, baseline
            ),
            reason_codes=(reason,),
        )

    def analyze_batch(
        self,
        batch: AllelicCountBatch,
        *,
        expected_directions: Mapping[str, RegulatoryDirection | str] | None = None,
        expected_context_key: str | None = None,
    ) -> tuple[AllelicImbalanceResult, ...]:
        if not isinstance(batch, AllelicCountBatch):
            raise ValidationError("batch must be an AllelicCountBatch")
        direction_map = expected_directions or {}
        preliminary = tuple(
            self._analyze_one(
                observation,
                expected_direction=direction_map.get(
                    observation.variant_id, direction_map.get(observation.feature_id)
                ),
                expected_context_key=expected_context_key,
            )
            for observation in batch.observations
        )
        tested_indexes = [
            index for index, result in enumerate(preliminary) if result.p_value is not None
        ]
        q_values = benjamini_hochberg(
            tuple(preliminary[index].p_value for index in tested_indexes)  # type: ignore[arg-type]
        )
        adjusted = list(preliminary)
        for index, q_value in zip(tested_indexes, q_values, strict=True):
            result = preliminary[index]
            state, reason = _classify_allelic(
                result.direction,
                q_value,
                self.policy.alpha,
                result.expected_direction,
            )
            adjusted[index] = replace(
                result,
                state=state,
                q_value=q_value,
                reason_codes=(reason,),
            )
        return tuple(adjusted)


def analyze_allelic_imbalance(
    observation: AllelicCountObservation,
    *,
    expected_direction: RegulatoryDirection | str | None = None,
    policy: AllelicImbalancePolicy | None = None,
    expected_context_key: str | None = None,
) -> AllelicImbalanceResult:
    return AllelicImbalanceAnalyzer(policy).analyze(
        observation,
        expected_direction=expected_direction,
        expected_context_key=expected_context_key,
    )


@dataclass(frozen=True, slots=True)
class PredictedRegulatoryEffect:
    """A sample-free gain/loss prediction to be checked against matched RNA."""

    prediction_id: str
    variant_id: str
    feature_id: str
    direction: RegulatoryDirection
    context_key: str
    source_id: str
    source_version: str = "unspecified"
    confidence: float | None = None

    def __post_init__(self) -> None:
        for field_name in ("prediction_id", "variant_id", "feature_id", "source_id"):
            object.__setattr__(
                self, field_name, _text(getattr(self, field_name), field_name, key=True)
            )
        object.__setattr__(self, "context_key", _text(self.context_key, "context_key"))
        object.__setattr__(self, "source_version", _text(
            self.source_version, "source_version", key=True
        ))
        object.__setattr__(
            self, "direction", _enum(self.direction, RegulatoryDirection, "direction")
        )
        if self.confidence is not None:
            confidence = _finite(self.confidence, "confidence")
            if not 0.0 <= confidence <= 1.0:
                raise ValidationError("confidence must be between 0 and 1")
            object.__setattr__(self, "confidence", confidence)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "prediction_id": self.prediction_id,
            "variant_id": self.variant_id,
            "feature_id": self.feature_id,
            "direction": self.direction.value,
            "context_key": self.context_key,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "confidence": self.confidence,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="regulatory-effect-prediction")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    public_projection = to_dict
    to_public_dict = to_dict

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> PredictedRegulatoryEffect:
        value = _mapping(raw, "predicted regulatory effect")
        result = cls(
            prediction_id=value.get("prediction_id"),
            variant_id=value.get("variant_id"),
            feature_id=value.get("feature_id"),
            direction=value.get("direction"),
            context_key=value.get("context_key"),
            source_id=value.get("source_id"),
            source_version=value.get("source_version", "unspecified"),
            confidence=value.get("confidence"),
        )
        _verify_address(value, result.content_address, "predicted regulatory effect")
        return result

    @classmethod
    def from_json(cls, text: str) -> PredictedRegulatoryEffect:
        return cls.from_mapping(_json_mapping(text, "predicted regulatory effect"))


@dataclass(frozen=True, slots=True)
class RNAConsequenceEvidence:
    """Privacy-bounded join of a prediction and matched RNA consequences."""

    prediction_id: str
    prediction_address: str
    variant_id: str
    feature_id: str
    context_key: str
    predicted_direction: RegulatoryDirection
    state: RNAEvidenceState
    expression_state: RNAEvidenceState | None
    expression_direction: ExpressionDirection | None
    expression_robust_z: float | None
    expression_result_address: str | None
    allelic_state: RNAEvidenceState | None
    allelic_direction: AllelicDirection | None
    allelic_log2_ratio: float | None
    allelic_q_value: float | None
    allelic_result_address: str | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("prediction_id", "variant_id", "feature_id"):
            object.__setattr__(
                self, field_name, _text(getattr(self, field_name), field_name, key=True)
            )
        object.__setattr__(self, "prediction_address", _text(
            self.prediction_address, "prediction_address"
        ))
        object.__setattr__(self, "context_key", _text(self.context_key, "context_key"))
        object.__setattr__(self, "predicted_direction", _enum(
            self.predicted_direction, RegulatoryDirection, "predicted_direction"
        ))
        object.__setattr__(self, "state", _enum(self.state, RNAEvidenceState, "state"))
        for field_name, enum_type in (
            ("expression_state", RNAEvidenceState),
            ("expression_direction", ExpressionDirection),
            ("allelic_state", RNAEvidenceState),
            ("allelic_direction", AllelicDirection),
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _enum(value, enum_type, field_name))
        for field_name in ("expression_robust_z", "allelic_log2_ratio", "allelic_q_value"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _finite(value, field_name))
        if self.allelic_q_value is not None and not 0.0 <= self.allelic_q_value <= 1.0:
            raise ValidationError("allelic_q_value must be between 0 and 1")
        for field_name in ("expression_result_address", "allelic_result_address"):
            value = getattr(self, field_name)
            if value is not None:
                _text(value, field_name)
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "prediction_id": self.prediction_id,
            "prediction_address": self.prediction_address,
            "variant_id": self.variant_id,
            "feature_id": self.feature_id,
            "context_key": self.context_key,
            "predicted_direction": self.predicted_direction.value,
            "state": self.state.value,
            "expression_state": (
                self.expression_state.value if self.expression_state is not None else None
            ),
            "expression_direction": (
                self.expression_direction.value if self.expression_direction is not None else None
            ),
            "expression_robust_z": self.expression_robust_z,
            "expression_result_address": self.expression_result_address,
            "allelic_state": self.allelic_state.value if self.allelic_state is not None else None,
            "allelic_direction": (
                self.allelic_direction.value if self.allelic_direction is not None else None
            ),
            "allelic_log2_ratio": self.allelic_log2_ratio,
            "allelic_q_value": self.allelic_q_value,
            "allelic_result_address": self.allelic_result_address,
            "reason_codes": list(self.reason_codes),
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="rna-consequence-evidence")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def public_projection(self) -> dict[str, Any]:
        """The integration object is already a strict, sample-free projection."""

        return self.to_dict()

    to_public_dict = public_projection

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> RNAConsequenceEvidence:
        value = _mapping(raw, "RNA consequence evidence")
        result = cls(
            prediction_id=value.get("prediction_id"),
            prediction_address=value.get("prediction_address"),
            variant_id=value.get("variant_id"),
            feature_id=value.get("feature_id"),
            context_key=value.get("context_key"),
            predicted_direction=value.get("predicted_direction"),
            state=value.get("state"),
            expression_state=value.get("expression_state"),
            expression_direction=value.get("expression_direction"),
            expression_robust_z=value.get("expression_robust_z"),
            expression_result_address=value.get("expression_result_address"),
            allelic_state=value.get("allelic_state"),
            allelic_direction=value.get("allelic_direction"),
            allelic_log2_ratio=value.get("allelic_log2_ratio"),
            allelic_q_value=value.get("allelic_q_value"),
            allelic_result_address=value.get("allelic_result_address"),
            reason_codes=tuple(value.get("reason_codes", ())),
        )
        _verify_address(value, result.content_address, "RNA consequence evidence")
        return result

    @classmethod
    def from_json(cls, text: str) -> RNAConsequenceEvidence:
        return cls.from_mapping(_json_mapping(text, "RNA consequence evidence"))


class RNAConsequenceIntegrator:
    """Join a gain/loss prediction to expression and allelic result summaries."""

    def integrate(
        self,
        prediction: PredictedRegulatoryEffect,
        *,
        expression: ExpressionOutlierResult | None = None,
        allelic: AllelicImbalanceResult | None = None,
    ) -> RNAConsequenceEvidence:
        if expression is None and allelic is None:
            state = RNAEvidenceState.ABSTAINED
            reasons = ["no_rna_result"]
        else:
            reasons = []
            identifier_mismatch = False
            if expression is not None:
                identifier_mismatch |= expression.feature_id != prediction.feature_id
                identifier_mismatch |= expression.context_key != prediction.context_key
            if allelic is not None:
                identifier_mismatch |= allelic.feature_id != prediction.feature_id
                identifier_mismatch |= allelic.variant_id != prediction.variant_id
                identifier_mismatch |= allelic.context_key != prediction.context_key
            if identifier_mismatch:
                state = RNAEvidenceState.OUT_OF_DOMAIN
                reasons.append("prediction_rna_scope_mismatch")
            else:
                state, reasons = self._combine(prediction, expression, allelic)
        return RNAConsequenceEvidence(
            prediction_id=prediction.prediction_id,
            prediction_address=prediction.content_address,
            variant_id=prediction.variant_id,
            feature_id=prediction.feature_id,
            context_key=prediction.context_key,
            predicted_direction=prediction.direction,
            state=state,
            expression_state=expression.state if expression is not None else None,
            expression_direction=expression.direction if expression is not None else None,
            expression_robust_z=expression.robust_z if expression is not None else None,
            expression_result_address=(
                expression.content_address if expression is not None else None
            ),
            allelic_state=allelic.state if allelic is not None else None,
            allelic_direction=allelic.direction if allelic is not None else None,
            allelic_log2_ratio=allelic.log2_ratio if allelic is not None else None,
            allelic_q_value=allelic.q_value if allelic is not None else None,
            allelic_result_address=allelic.content_address if allelic is not None else None,
            reason_codes=tuple(reasons),
        )

    @staticmethod
    def _combine(
        prediction: PredictedRegulatoryEffect,
        expression: ExpressionOutlierResult | None,
        allelic: AllelicImbalanceResult | None,
    ) -> tuple[RNAEvidenceState, list[str]]:
        components = tuple(item for item in (expression, allelic) if item is not None)
        if any(item.state is RNAEvidenceState.OUT_OF_DOMAIN for item in components):
            return RNAEvidenceState.OUT_OF_DOMAIN, ["rna_component_out_of_domain"]
        if any(item.state is RNAEvidenceState.CONTRADICTORY for item in components):
            return RNAEvidenceState.CONTRADICTORY, ["rna_component_contradicts_prediction"]

        concordant = False
        opposite = False
        if expression is not None and expression.state is RNAEvidenceState.SUPPORTED:
            expected_expression = {
                RegulatoryDirection.GAIN: ExpressionDirection.UP,
                RegulatoryDirection.LOSS: ExpressionDirection.DOWN,
            }.get(prediction.direction)
            concordant |= expected_expression is None or expression.direction is expected_expression
            opposite |= (
                expected_expression is not None
                and expression.direction is not expected_expression
            )
        if allelic is not None and allelic.state is RNAEvidenceState.SUPPORTED:
            expected_allelic = {
                RegulatoryDirection.GAIN: AllelicDirection.ALT_ENRICHED,
                RegulatoryDirection.LOSS: AllelicDirection.REF_ENRICHED,
            }.get(prediction.direction)
            concordant |= expected_allelic is None or allelic.direction is expected_allelic
            opposite |= expected_allelic is not None and allelic.direction is not expected_allelic
        if opposite:
            return RNAEvidenceState.CONTRADICTORY, ["rna_direction_opposes_prediction"]
        if concordant:
            return RNAEvidenceState.SUPPORTED, ["rna_direction_concordant"]
        if any(item.state is RNAEvidenceState.MEASURED_NEGATIVE for item in components):
            return RNAEvidenceState.MEASURED_NEGATIVE, ["rna_measured_without_directional_support"]
        return RNAEvidenceState.ABSTAINED, ["rna_components_abstained"]


def integrate_rna_consequence(
    prediction: PredictedRegulatoryEffect,
    *,
    expression: ExpressionOutlierResult | None = None,
    allelic: AllelicImbalanceResult | None = None,
) -> RNAConsequenceEvidence:
    return RNAConsequenceIntegrator().integrate(
        prediction, expression=expression, allelic=allelic
    )


def expression_evidence_capabilities() -> dict[str, Any]:
    """Return a stable, sample-free capability declaration."""

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module": "glio_noncode.expression_evidence",
        "operations": [
            "robust_expression_outlier",
            "exact_allelic_imbalance",
            "benjamini_hochberg_adjustment",
            "rna_direction_integration",
        ],
        "evidence_states": [item.value for item in RNAEvidenceState],
        "expression_dispersion": [DispersionMethod.MAD.value, DispersionMethod.IQR.value],
        "allelic_baselines": [
            ExpectedFractionMethod.DECLARED.value,
            ExpectedFractionMethod.COPY_NUMBER_PURITY.value,
        ],
        "computational_bounds": {
            "max_exact_binomial_trials": MAX_EXACT_BINOMIAL_TRIALS,
            "default_max_informative_depth": AllelicImbalancePolicy().max_informative_depth,
            "over_limit_state": RNAEvidenceState.ABSTAINED.value,
            "over_limit_reason_code": _EXACT_BINOMIAL_DEPTH_LIMIT_REASON,
        },
        "privacy": {
            "public_results_are_sample_free": True,
            "raw_cohort_vectors_excluded": True,
            "private_inputs_are_content_addressed": True,
        },
        "limitations": [
            "research evidence only",
            "raw count expression is not compared across samples",
            "allelic tests abstain without phase and an expected fraction",
            "allelic exact inference abstains above the declared maximum informative depth",
            "mapping bias is gated, not statistically corrected",
        ],
    }
    return body | {
        "content_address": content_hash(body, prefix="expression-evidence-capabilities")
    }


def expression_evidence_schema(*, public: bool = True) -> dict[str, Any]:
    """Return a compact JSON-Schema-like contract for callers and surfaces."""

    result_fields = {
        "feature_id": {"type": "string"},
        "context_key": {"type": "string"},
        "state": {"enum": [item.value for item in RNAEvidenceState]},
        "content_address": {"type": "string"},
    }
    definitions: dict[str, Any] = {
        "AllelicImbalancePolicy": {
            "type": "object",
            "required": [
                "min_informative_depth",
                "max_informative_depth",
                "max_other_fraction",
                "max_abs_mapping_bias",
                "alpha",
            ],
            "properties": {
                "min_informative_depth": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_EXACT_BINOMIAL_TRIALS,
                },
                "max_informative_depth": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_EXACT_BINOMIAL_TRIALS,
                    "default": MAX_EXACT_BINOMIAL_TRIALS,
                    "description": "Must be at least min_informative_depth.",
                },
                "max_other_fraction": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "max_abs_mapping_bias": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "alpha": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "additionalProperties": False,
        },
        "ExpressionOutlierResult": {
            "type": "object",
            "required": list(result_fields),
            "properties": result_fields
            | {
                "direction": {"enum": [item.value for item in ExpressionDirection]},
                "robust_z": {"type": ["number", "null"]},
            },
            "additionalProperties": False,
        },
        "AllelicImbalanceResult": {
            "type": "object",
            "required": list(result_fields) + ["variant_id"],
            "properties": result_fields
            | {
                "variant_id": {"type": "string"},
                "direction": {"enum": [item.value for item in AllelicDirection]},
                "p_value": {"type": ["number", "null"]},
                "q_value": {"type": ["number", "null"]},
            },
            "additionalProperties": False,
        },
        "RNAConsequenceEvidence": {
            "type": "object",
            "required": [
                "prediction_id",
                "variant_id",
                "feature_id",
                "context_key",
                "predicted_direction",
                "state",
                "content_address",
            ],
            "properties": {
                "prediction_id": {"type": "string"},
                "variant_id": {"type": "string"},
                "feature_id": {"type": "string"},
                "context_key": {"type": "string"},
                "predicted_direction": {
                    "enum": [item.value for item in RegulatoryDirection]
                },
                "state": {"enum": [item.value for item in RNAEvidenceState]},
                "content_address": {"type": "string"},
            },
            "additionalProperties": True,
        },
    }
    if not public:
        definitions |= {
            "ExpressionObservation": {
                "type": "object",
                "required": [
                    "feature_id",
                    "sample_key",
                    "value",
                    "scale",
                    "context_key",
                    "source_id",
                ],
            },
            "AllelicCountObservation": {
                "type": "object",
                "required": [
                    "feature_id",
                    "variant_id",
                    "sample_key",
                    "ref_count",
                    "alt_count",
                    "phase",
                    "context_key",
                    "source_id",
                ],
            },
        }
    body: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:expression-evidence:1",
        "title": "Matched tumour RNA consequence evidence",
        "schema_version": SCHEMA_VERSION,
        "public": public,
        "computational_bounds": {
            "max_exact_binomial_trials": MAX_EXACT_BINOMIAL_TRIALS,
        },
        "$defs": definitions,
    }
    return body | {"content_address": content_hash(body, prefix="expression-evidence-schema")}


def public_projection(value: object) -> dict[str, Any]:
    """Return the explicit safe projection for a module object."""

    projector = getattr(value, "public_projection", None)
    if projector is None or not callable(projector):
        raise ValidationError("value does not provide an expression-evidence public projection")
    projected = projector()
    if not isinstance(projected, dict):
        raise ValidationError("public projection must be a mapping")
    return projected


capabilities = expression_evidence_capabilities
capability_manifest = expression_evidence_capabilities
schema = expression_evidence_schema
schema_contract = expression_evidence_schema


__all__ = [
    "AllelicCountBatch",
    "AllelicCountObservation",
    "AllelicDirection",
    "AllelicImbalanceAnalyzer",
    "AllelicImbalancePolicy",
    "AllelicImbalanceResult",
    "DispersionMethod",
    "ExpectedFractionMethod",
    "ExpressionBatch",
    "ExpressionDirection",
    "ExpressionObservation",
    "ExpressionOutlierAnalyzer",
    "ExpressionOutlierResult",
    "ExpressionScale",
    "MAX_EXACT_BINOMIAL_TRIALS",
    "PhaseStatus",
    "PredictedRegulatoryEffect",
    "RNAConsequenceEvidence",
    "RNAConsequenceIntegrator",
    "RNAEvidenceState",
    "RegulatoryDirection",
    "RobustExpressionOutlierAnalyzer",
    "RobustOutlierPolicy",
    "analyze_allelic_imbalance",
    "analyze_expression_outlier",
    "benjamini_hochberg",
    "capabilities",
    "capability_manifest",
    "exact_binomial_two_sided_p_value",
    "exact_two_sided_binomial_pvalue",
    "expression_evidence_capabilities",
    "expression_evidence_schema",
    "integrate_rna_consequence",
    "public_projection",
    "schema",
    "schema_contract",
    "two_sided_binomial_p_value",
]
