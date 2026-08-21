"""External-alpha validation planning contracts.

Domain 13 external-alpha planning is deliberately bounded:

* model-system eligibility is evaluated from declared context and model
  metadata, not inferred from a model name;
* guide and oligo rows are adapted losslessly with sequence, strand, design,
  and source receipts;
* controls and randomization are deterministic planning records, not an
  execution schedule or an assurance of assay validity;
* power and replication estimates expose assumptions, required replicates,
  and planned shortfalls using a transparent normal-approximation proxy.

These objects are research planning artifacts. They do not establish guide
efficacy, off-target safety, assay success, causal effects, clinical utility,
or institutional approval.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import ceil, erf, isfinite, log, sqrt
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class ValidationAlphaState(StrEnum):
    """State for external-alpha validation planning outputs."""

    ELIGIBLE = "eligible"
    READY_FOR_REVIEW = "ready_for_review"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class OligoType(StrEnum):
    """Oligo sequence role retained by the adapter."""

    GUIDE = "guide"
    DONOR = "donor"
    PBS = "pbs"
    RTT = "rtt"
    REPORTER = "reporter"
    CONTROL = "control"
    OTHER = "other"


class ControlType(StrEnum):
    """Planned control category."""

    NEGATIVE = "negative"
    NON_TARGETING = "non_targeting"
    POSITIVE = "positive"
    MOCK = "mock"
    REFERENCE = "reference"
    VEHICLE = "vehicle"


@dataclass(frozen=True, slots=True)
class ValidationAlphaIssue:
    """Quarantined validation record with source receipt."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    remediation: str = "Inspect the target, sequence, context, and design source before retrying."
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "validation alpha issue code")
        require_non_empty(self.message, "validation alpha issue message")
        require_non_empty(self.raw_hash, "validation alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("validation alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModelSystemEligibilityObservation:
    """Declared model-system support for one validation target."""

    observation_id: str
    target_id: str
    model_system: str
    context_key: str
    supported_contexts: tuple[str, ...]
    cell_state: str
    evidence_strength: float
    source_id: str
    source_version: str
    raw_hash: str
    eligible: bool | None = None
    blockers: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "target_id",
            "model_system",
            "context_key",
            "cell_state",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.evidence_strength <= 1:
            raise ValidationError("model-system evidence_strength must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModelSystemEligibilityResult:
    """Eligibility decision with blockers and candidate model systems."""

    target_id: str
    context_key: str
    state: ValidationAlphaState
    eligible: bool
    model_systems: tuple[str, ...]
    cell_states: tuple[str, ...]
    evidence_strength: float | None
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModelSystemEligibilityReport:
    """Model-system eligibility output."""

    input_hash: str
    context_key: str
    state: ValidationAlphaState
    results: tuple[ModelSystemEligibilityResult, ...]
    issues: tuple[ValidationAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ModelSystemEligibilityMatcher:
    """Match target eligibility against exact context and declared systems."""

    def match(
        self,
        observations: Iterable[ModelSystemEligibilityObservation | Mapping[str, Any]],
        *,
        context_key: str,
        model_system: str | None = None,
        minimum_evidence_strength: float = 0.5,
    ) -> ModelSystemEligibilityReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if not 0 <= minimum_evidence_strength <= 1:
            raise ValidationError("minimum_evidence_strength must be between zero and one")
        parsed: list[ModelSystemEligibilityObservation] = []
        issues: list[ValidationAlphaIssue] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_eligibility(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ValidationAlphaIssue(
                        "invalid_eligibility_row",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if item.context_key != context_key:
                mismatch = True
                issues.append(
                    ValidationAlphaIssue(
                        "context_mismatch",
                        "model-system observation is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(item)
        groups: dict[str, list[ModelSystemEligibilityObservation]] = defaultdict(list)
        for item in parsed:
            if model_system and item.model_system != model_system:
                continue
            groups[item.target_id].append(item)
        results: list[ModelSystemEligibilityResult] = []
        for target_id, group in sorted(groups.items()):
            blockers = sorted({blocker for item in group for blocker in item.blockers})
            eligible_rows = [item for item in group if item.eligible is True]
            strengths = [item.evidence_strength for item in eligible_rows]
            supported_context = any(context_key in item.supported_contexts for item in group)
            if not supported_context:
                blockers.append("context_not_declared_supported")
            if not eligible_rows:
                blockers.append("no_declared_eligible_model_system")
            if strengths and max(strengths) < minimum_evidence_strength:
                blockers.append("eligibility_evidence_below_threshold")
            eligible = bool(
                eligible_rows
                and supported_context
                and strengths
                and max(strengths) >= minimum_evidence_strength
                and not blockers
            )
            if eligible:
                state = ValidationAlphaState.ELIGIBLE
                reason = "model system, context, and declared evidence meet eligibility gates"
            elif eligible_rows or group:
                state = ValidationAlphaState.BLOCKED
                reason = "model-system eligibility is blocked by one or more declared gates"
            else:
                state = ValidationAlphaState.ABSTAINED
                reason = "no exact-context model-system observation was supplied"
            results.append(
                ModelSystemEligibilityResult(
                    target_id=target_id,
                    context_key=context_key,
                    state=state,
                    eligible=eligible,
                    model_systems=tuple(sorted({item.model_system for item in group})),
                    cell_states=tuple(sorted({item.cell_state for item in group})),
                    evidence_strength=None if not strengths else round(max(strengths), 9),
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    blockers=tuple(dict.fromkeys(blockers)),
                    reason=reason,
                    limitations=(
                        "Eligibility is a declared planning gate, not proof of model fidelity "
                        "or assay success.",
                        "Cell state, delivery, editing, and institutional review require "
                        "independent validation.",
                    ),
                    content_address=content_hash(
                        {
                            "target_id": target_id,
                            "context_key": context_key,
                            "state": state,
                            "eligible": eligible,
                            "blockers": tuple(dict.fromkeys(blockers)),
                        }
                    ),
                )
            )
        state = _aggregate_state(tuple(item.state for item in results), mismatch, issues)
        return ModelSystemEligibilityReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Model-system eligibility records are planning gates, not validation of "
                "biological fidelity.",
                "A missing model-system record is not evidence that no system is suitable.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class GuideOligoObservation:
    """One guide or oligo row adapted from a design source."""

    observation_id: str
    design_id: str
    target_id: str
    oligo_id: str
    oligo_type: OligoType
    sequence: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    guide_id: str | None = None
    strand: str | None = None
    start_offset: int | None = None
    pam: str | None = None
    notes: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "design_id",
            "target_id",
            "oligo_id",
            "sequence",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        normalized = self.sequence.upper().replace(" ", "")
        if any(base not in "ACGTN" for base in normalized):
            raise ValidationError("guide/oligo sequence contains unsupported bases")
        if not normalized:
            raise ValidationError("guide/oligo sequence cannot be empty")
        if self.start_offset is not None and self.start_offset < 0:
            raise ValidationError("guide/oligo start_offset cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GuideOligoBatch:
    """Adapted guide/oligo rows with malformed-row quarantine."""

    source_id: str
    input_hash: str
    observations: tuple[GuideOligoObservation, ...]
    issues: tuple[ValidationAlphaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["observations"] = tuple(item.to_dict() for item in self.observations)
        return payload


class GuideOligoDesignAdapter:
    """Parse guide and oligo designs without rewriting source sequences."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> GuideOligoBatch:
        rows, json_mode = _rows(text, input_format, "observations")
        observations: list[GuideOligoObservation] = []
        issues: list[ValidationAlphaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    ValidationAlphaIssue(
                        "invalid_guide_oligo_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                observations.append(
                    GuideOligoObservation(
                        observation_id=str(
                            _value(row, "observation_id", "id", default=f"{source_id}:{index}")
                        ),
                        design_id=str(_value(row, "design_id", "design")),
                        target_id=str(_value(row, "target_id", "target")),
                        oligo_id=str(
                            _value(row, "oligo_id", "guide_id", "id", default=f"oligo:{index}")
                        ),
                        oligo_type=_oligo_type(
                            _value(row, "oligo_type", "type", default=OligoType.GUIDE.value)
                        ),
                        sequence=str(_value(row, "sequence", "guide_sequence", "oligo_sequence")),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        guide_id=_optional_text(row, "guide_id"),
                        strand=_optional_text(row, "strand"),
                        start_offset=_optional_int(row, "start_offset", "offset"),
                        pam=_optional_text(row, "pam"),
                        notes=tuple(
                            str(item) for item in row.get("notes", ()) if str(item).strip()
                        ),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ValidationAlphaIssue(
                        "invalid_guide_oligo_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return GuideOligoBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "input_hash": input_hash,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ControlAssignment:
    """One deterministic control or replicate assignment."""

    assignment_id: str
    target_id: str
    condition: str
    control_type: ControlType
    biological_replicate: int
    technical_replicate: int
    randomization_key: str
    context_key: str
    source_ids: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlsRandomizationReport:
    """Deterministic controls and randomization plan."""

    plan_id: str
    context_key: str
    state: ValidationAlphaState
    assignments: tuple[ControlAssignment, ...]
    control_types: tuple[ControlType, ...]
    biological_replicates: int
    technical_replicates: int
    randomization_seed: str
    target_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ControlsRandomizationPlanner:
    """Create reproducible control and replicate planning assignments."""

    def plan(
        self,
        targets: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        plan_id: str = "validation-alpha-plan",
        control_types: Iterable[ControlType] = (ControlType.NEGATIVE, ControlType.NON_TARGETING),
        biological_replicates: int = 3,
        technical_replicates: int = 1,
        randomization_seed: str = "seed-1",
    ) -> ControlsRandomizationReport:
        values = tuple(targets)
        controls = tuple(dict.fromkeys(ControlType(item) for item in control_types))
        if not plan_id.strip() or not randomization_seed.strip():
            raise ValidationError("control plan_id and randomization_seed are required")
        if not controls:
            raise ValidationError("at least one control type is required")
        if biological_replicates < 1 or technical_replicates < 1:
            raise ValidationError("replicate counts must be positive")
        assignments: list[ControlAssignment] = []
        blockers: list[str] = []
        target_ids: list[str] = []
        for index, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                blockers.append(f"row-{index}:not_an_object")
                continue
            target_id = str(row.get("target_id", row.get("id", ""))).strip()
            row_context = str(row.get("context_key", row.get("context", context_key)))
            if not target_id:
                blockers.append(f"row-{index}:missing_target_id")
                continue
            target_ids.append(target_id)
            if row_context != context_key:
                blockers.append(f"{target_id}:context_mismatch")
                continue
            condition = str(row.get("condition", row.get("assay_condition", "target")))
            source_id = str(row.get("source_id", "target-input"))
            for control_type in controls:
                for biological in range(1, biological_replicates + 1):
                    for technical in range(1, technical_replicates + 1):
                        randomization_key = content_hash(
                            {
                                "seed": randomization_seed,
                                "target": target_id,
                                "condition": condition,
                                "control": control_type,
                                "biological": biological,
                                "technical": technical,
                            },
                            prefix="randomization",
                        )
                        assignments.append(
                            ControlAssignment(
                                assignment_id=content_hash(
                                    {"plan": plan_id, "randomization_key": randomization_key},
                                    prefix="assignment",
                                ),
                                target_id=target_id,
                                condition=condition,
                                control_type=control_type,
                                biological_replicate=biological,
                                technical_replicate=technical,
                                randomization_key=randomization_key,
                                context_key=context_key,
                                source_ids=(source_id,),
                                notes=(
                                    "Assignment is a deterministic planning record; execution "
                                    "order and balance require review.",
                                ),
                            )
                        )
        if not values:
            blockers.append("no_targets")
        state = (
            ValidationAlphaState.BLOCKED
            if blockers
            else ValidationAlphaState.READY_FOR_REVIEW
            if assignments
            else ValidationAlphaState.ABSTAINED
        )
        assignments_tuple = tuple(
            sorted(assignments, key=lambda item: (item.randomization_key, item.assignment_id))
        )
        return ControlsRandomizationReport(
            plan_id=plan_id,
            context_key=context_key,
            state=state,
            assignments=assignments_tuple,
            control_types=controls,
            biological_replicates=biological_replicates,
            technical_replicates=technical_replicates,
            randomization_seed=randomization_seed,
            target_ids=tuple(dict.fromkeys(target_ids)),
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=(
                "Control assignments are deterministic planning records, not execution or "
                "balance guarantees.",
                "Negative, non-targeting, positive, mock, reference, and vehicle controls "
                "require assay-specific review.",
            ),
            content_address=content_hash(
                {
                    "plan_id": plan_id,
                    "context_key": context_key,
                    "state": state,
                    "assignments": assignments_tuple,
                    "blockers": tuple(dict.fromkeys(blockers)),
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class PowerReplicationObservation:
    """Effect/noise and planned-replicate inputs for power estimation."""

    observation_id: str
    design_id: str
    assay_id: str
    effect_size: float
    variance: float
    alpha: float
    target_power: float
    planned_replicates: int
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    blocking_factor_count: int = 1
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "design_id",
            "assay_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not isfinite(self.effect_size) or self.effect_size == 0:
            raise ValidationError("power effect_size must be finite and non-zero")
        if not isfinite(self.variance) or self.variance <= 0:
            raise ValidationError("power variance must be finite and positive")
        if not 0 < self.alpha < 1 or not 0 < self.target_power < 1:
            raise ValidationError("power alpha and target_power must be between zero and one")
        if self.planned_replicates < 1 or self.blocking_factor_count < 1:
            raise ValidationError("power replicate and blocking counts must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PowerReplicationEstimate:
    """Transparent required/achieved power estimate."""

    design_id: str
    assay_id: str
    context_key: str
    state: ValidationAlphaState
    required_replicates: int
    planned_replicates: int
    achieved_power: float
    target_power: float
    effect_size: float
    variance: float
    alpha: float
    blocking_factor_count: int
    replicate_shortfall: int
    source_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    reason: str
    assumptions: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PowerReplicationReport:
    """Power and replication estimates."""

    input_hash: str
    context_key: str
    state: ValidationAlphaState
    results: tuple[PowerReplicationEstimate, ...]
    issues: tuple[ValidationAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PowerReplicationEstimator:
    """Estimate replicate requirements with an explicit normal approximation."""

    def estimate(
        self,
        observations: Iterable[PowerReplicationObservation | Mapping[str, Any]],
        *,
        context_key: str,
    ) -> PowerReplicationReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        parsed: list[PowerReplicationObservation] = []
        issues: list[ValidationAlphaIssue] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_power(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ValidationAlphaIssue(
                        "invalid_power_row",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if item.context_key != context_key:
                mismatch = True
                issues.append(
                    ValidationAlphaIssue(
                        "context_mismatch",
                        "power observation is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(item)
        groups: dict[tuple[str, str], list[PowerReplicationObservation]] = defaultdict(list)
        for item in parsed:
            groups[(item.design_id, item.assay_id)].append(item)
        results: list[PowerReplicationEstimate] = []
        for (design_id, assay_id), group in sorted(groups.items()):
            effect = fmean(item.effect_size for item in group)
            variance = fmean(item.variance for item in group)
            alpha = fmean(item.alpha for item in group)
            target_power = fmean(item.target_power for item in group)
            planned = max(item.planned_replicates for item in group)
            blocking = max(item.blocking_factor_count for item in group)
            z_alpha = _normal_quantile(1 - alpha / 2)
            z_power = _normal_quantile(target_power)
            raw_required = 2 * ((z_alpha + z_power) ** 2) * variance / (effect * effect)
            required = max(2, ceil(raw_required) * blocking)
            achieved = _normal_cdf(sqrt(max(1, planned) / (2 * variance)) * abs(effect) - z_alpha)
            shortfall = max(0, required - planned)
            state = (
                ValidationAlphaState.READY_FOR_REVIEW
                if shortfall == 0
                else ValidationAlphaState.PARTIAL
            )
            reason = (
                "planned replicates meet the transparent normal-approximation requirement"
                if shortfall == 0
                else (
                    "planned replicates fall below the transparent normal-approximation requirement"
                )
            )
            results.append(
                PowerReplicationEstimate(
                    design_id=design_id,
                    assay_id=assay_id,
                    context_key=context_key,
                    state=state,
                    required_replicates=required,
                    planned_replicates=planned,
                    achieved_power=round(max(0.0, min(1.0, achieved)), 9),
                    target_power=round(target_power, 9),
                    effect_size=round(effect, 9),
                    variance=round(variance, 9),
                    alpha=round(alpha, 9),
                    blocking_factor_count=blocking,
                    replicate_shortfall=shortfall,
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    reason=reason,
                    assumptions=(
                        "Two-sided normal approximation with independent observations and "
                        "declared variance.",
                        "Blocking factor count multiplies the required replicate estimate.",
                        "Effect size, variance, alpha, and target power require assay-specific "
                        "calibration.",
                    ),
                    content_address=content_hash(
                        {
                            "design_id": design_id,
                            "assay_id": assay_id,
                            "context_key": context_key,
                            "required": required,
                            "planned": planned,
                            "achieved": achieved,
                        }
                    ),
                )
            )
        state = _aggregate_state(tuple(item.state for item in results), mismatch, issues)
        return PowerReplicationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Power is a transparent planning approximation, not a validated statistical "
                "guarantee.",
                "Independence, variance, effect scale, blocking, missingness, and assay "
                "design require review.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


def _rows(
    text: str,
    input_format: str | None,
    collection_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("validation alpha input must not be empty")
    selected = (input_format or "").strip().lower()
    if not selected:
        selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
    if selected == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid validation alpha JSON: {exc}") from exc
        rows = payload.get(collection_key, payload) if isinstance(payload, Mapping) else payload
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValidationError(f"validation alpha JSON must contain a {collection_key} list")
        return tuple(rows), True
    if selected == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("validation alpha TSV requires a header")
        return tuple(reader), False
    raise ValidationError(f"unsupported validation alpha format: {selected}")


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    if default is not None:
        return default
    raise ValidationError(f"validation alpha field is required: {names[0]}")


def _optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return None


def _optional_int(row: Mapping[str, Any], *names: str) -> int | None:
    value = _optional_text(row, *names)
    return None if value is None else int(value)


def _oligo_type(value: Any) -> OligoType:
    normalized = str(value).strip().lower().replace("-", "_")
    try:
        return OligoType(normalized)
    except ValueError:
        return OligoType.OTHER


def _coerce_eligibility(
    value: ModelSystemEligibilityObservation | Mapping[str, Any],
) -> ModelSystemEligibilityObservation:
    if isinstance(value, ModelSystemEligibilityObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("model-system eligibility observation must be a mapping")
    eligible = value.get("eligible")
    if eligible is not None:
        eligible = _as_bool(eligible)
    contexts = value.get("supported_contexts", value.get("contexts", ()))
    if isinstance(contexts, str):
        contexts = (contexts,)
    return ModelSystemEligibilityObservation(
        observation_id=str(value.get("observation_id", value.get("id", "eligibility-input"))),
        target_id=str(value.get("target_id", value.get("target", ""))),
        model_system=str(value.get("model_system", value.get("system", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        supported_contexts=tuple(str(item) for item in contexts),
        cell_state=str(value.get("cell_state", value.get("cell", "unspecified"))),
        evidence_strength=float(value.get("evidence_strength", value.get("strength", 0.0))),
        source_id=str(value.get("source_id", "eligibility-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        eligible=eligible,
        blockers=tuple(str(item) for item in value.get("blockers", ())),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_power(
    value: PowerReplicationObservation | Mapping[str, Any],
) -> PowerReplicationObservation:
    if isinstance(value, PowerReplicationObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("power observation must be a mapping")
    return PowerReplicationObservation(
        observation_id=str(value.get("observation_id", value.get("id", "power-input"))),
        design_id=str(value.get("design_id", value.get("design", ""))),
        assay_id=str(value.get("assay_id", value.get("assay", ""))),
        effect_size=float(value.get("effect_size", value.get("effect", 0.0))),
        variance=float(value.get("variance", value.get("noise_variance", 0.0))),
        alpha=float(value.get("alpha", 0.05)),
        target_power=float(value.get("target_power", value.get("power", 0.8))),
        planned_replicates=int(value.get("planned_replicates", value.get("replicates", 0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "power-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        blocking_factor_count=int(value.get("blocking_factor_count", value.get("blocks", 1))),
        attributes=dict(value.get("attributes", {})),
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _normal_quantile(probability: float) -> float:
    """Acklam-style rational approximation for a bounded normal quantile."""

    if not 0 < probability < 1:
        raise ValidationError("normal quantile probability must be between zero and one")
    coefficients = (
        -39.6968302866538,
        220.946098424521,
        -275.928510446969,
        138.357751867269,
        -30.6647980661472,
        2.50662827745924,
    )
    denominator = (
        -54.4760987982241,
        161.585836858041,
        -155.698979859887,
        66.8013118877197,
        -13.2806815528857,
        1.0,
    )
    lower = 0.02425
    upper = 1 - lower
    if probability < lower:
        q = sqrt(-2 * log(probability))
        return -sum(coefficients[index] * q ** (5 - index) for index in range(6)) / sum(
            denominator[index] * q ** (5 - index) for index in range(6)
        )
    if probability > upper:
        return -_normal_quantile(1 - probability)
    q = probability - 0.5
    r = q * q
    numerator = q * sum(coefficients[index] * r ** (5 - index) for index in range(6))
    denominator_value = sum(denominator[index] * r ** (5 - index) for index in range(6))
    return numerator / denominator_value


def _aggregate_state(
    states: tuple[ValidationAlphaState, ...],
    mismatch: bool,
    issues: Iterable[ValidationAlphaIssue],
) -> ValidationAlphaState:
    if not states:
        return ValidationAlphaState.OUT_OF_DOMAIN if mismatch else ValidationAlphaState.ABSTAINED
    if ValidationAlphaState.AMBIGUOUS in states:
        return ValidationAlphaState.AMBIGUOUS
    if ValidationAlphaState.BLOCKED in states:
        return ValidationAlphaState.BLOCKED
    if any(issue.severity == "error" for issue in issues):
        return ValidationAlphaState.PARTIAL
    if ValidationAlphaState.PARTIAL in states:
        return ValidationAlphaState.PARTIAL
    if all(
        item in {ValidationAlphaState.ELIGIBLE, ValidationAlphaState.READY_FOR_REVIEW}
        for item in states
    ):
        return ValidationAlphaState.READY_FOR_REVIEW
    return ValidationAlphaState.PARTIAL


__all__ = [
    "ControlAssignment",
    "ControlType",
    "ControlsRandomizationPlanner",
    "ControlsRandomizationReport",
    "GuideOligoBatch",
    "GuideOligoDesignAdapter",
    "GuideOligoObservation",
    "ModelSystemEligibilityMatcher",
    "ModelSystemEligibilityObservation",
    "ModelSystemEligibilityReport",
    "ModelSystemEligibilityResult",
    "OligoType",
    "PowerReplicationEstimate",
    "PowerReplicationEstimator",
    "PowerReplicationObservation",
    "PowerReplicationReport",
    "ValidationAlphaIssue",
    "ValidationAlphaState",
]
