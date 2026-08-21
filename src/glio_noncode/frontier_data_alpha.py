"""Deep data-foundation and reference-governance frontier capabilities.

This module implements the first frontier expansion wave for domains D01-D04.
The routines are deliberately bounded: they validate declared records, retain
uncertainty and policy receipts, and return reviewable outputs instead of
turning incomplete data into scientific conclusions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class FrontierState(StrEnum):
    """Shared state vocabulary for bounded frontier outputs."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    COMPATIBLE = "compatible"
    DRIFT = "drift"


@dataclass(frozen=True, slots=True)
class FrontierIssue:
    """A structured, non-destructive issue attached to a frontier record."""

    code: str
    message: str
    severity: str = "review"
    field: str | None = None
    record_id: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.code, "code")
        require_non_empty(self.message, "message")
        if self.severity not in {"info", "warning", "review", "blocking"}:
            raise ValidationError("severity must be info, warning, review, or blocking")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _mapping(value: Mapping[str, Any] | Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _text(value: Any, *, field: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _required_text(value: Any, *, field: str) -> str:
    return require_non_empty(_text(value, field=field), field)


def _float(value: Any, *, field: str, default: float | None = None) -> float:
    if value is None and default is not None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if not isfinite(result):
        raise ValidationError(f"{field} must be finite")
    return result


def _bounded(value: Any, *, field: str, low: float = 0.0, high: float = 1.0) -> float:
    result = _float(value, field=field)
    if result < low or result > high:
        raise ValidationError(f"{field} must be between {low} and {high}")
    return result


def _tuple_text(values: Any, *, field: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, Sequence):
        raise ValidationError(f"{field} must be a list")
    return tuple(_text(item, field=field) for item in values if _text(item, field=field))


def _context(row: Mapping[str, Any], fallback: str | None) -> str:
    return _required_text(row.get("context_key", fallback), field="context_key")


def _address(payload: Any, *, prefix: str = "sha256") -> str:
    return content_hash(jsonable(payload), prefix=prefix)


def _sequence(value: Any) -> str:
    return "".join(ch for ch in _text(value, field="sequence").upper() if not ch.isspace())


@dataclass(frozen=True, slots=True)
class ConsentAttachment:
    record_id: str
    context_key: str
    policy_id: str
    policy_version: str
    purpose: str
    permitted_uses: tuple[str, ...]
    consent_status: str
    expires_at: str | None
    source_id: str
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ConsentAttachmentReport:
    attachments: tuple[ConsentAttachment, ...]
    accepted_record_ids: tuple[str, ...]
    blocked_record_ids: tuple[str, ...]
    issues: tuple[FrontierIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ConsentPolicyAttacher:
    """Attach explicit data-use policy receipts to intake records."""

    def attach(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        policy_id: str,
        policy_version: str,
        purpose: str,
        permitted_uses: Sequence[str],
        source_id: str,
    ) -> ConsentAttachmentReport:
        context_key = require_non_empty(context_key, "context_key")
        policy_id = require_non_empty(policy_id, "policy_id")
        policy_version = require_non_empty(policy_version, "policy_version")
        purpose = require_non_empty(purpose, "purpose")
        source_id = require_non_empty(source_id, "source_id")
        uses = tuple(require_non_empty(str(item), "permitted_use") for item in permitted_uses)
        if not uses:
            raise ValidationError("permitted_uses must not be empty")
        attachments: list[ConsentAttachment] = []
        issues: list[FrontierIssue] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"record {index}")
            record_id = _text(row.get("record_id", row.get("id")), field="record_id")
            local: list[FrontierIssue] = []
            if not record_id:
                record_id = f"unidentified:{index}"
                local.append(
                    FrontierIssue(
                        "missing_record_id",
                        "consent attachment cannot identify the source record",
                        "blocking",
                        "record_id",
                        record_id,
                    )
                )
            status = _text(row.get("consent_status", "unknown"), field="consent_status").lower()
            if status not in {"granted", "active", "approved"}:
                local.append(
                    FrontierIssue(
                        "consent_not_active",
                        "record does not declare active consent for the requested use",
                        "blocking",
                        "consent_status",
                        record_id,
                    )
                )
            row_context = _text(row.get("context_key", context_key), field="context_key")
            if row_context != context_key:
                local.append(
                    FrontierIssue(
                        "context_mismatch",
                        "record context differs from the requested attachment context",
                        "blocking",
                        "context_key",
                        record_id,
                    )
                )
            expiry = _text(row.get("consent_expires_at"), field="consent_expires_at") or None
            state = FrontierState.BLOCKED if local else FrontierState.ACCEPTED
            attachments.append(
                ConsentAttachment(
                    record_id,
                    context_key,
                    policy_id,
                    policy_version,
                    purpose,
                    uses,
                    status,
                    expiry,
                    source_id,
                    state,
                    tuple(local),
                )
            )
            issues.extend(local)
        accepted = tuple(
            item.record_id for item in attachments if item.state == FrontierState.ACCEPTED
        )
        blocked = tuple(
            item.record_id for item in attachments if item.state == FrontierState.BLOCKED
        )
        payload = {"attachments": attachments, "issues": issues}
        return ConsentAttachmentReport(
            tuple(attachments), accepted, blocked, tuple(issues), _address(payload)
        )


@dataclass(frozen=True, slots=True)
class AnomalyObservation:
    record_id: str
    context_key: str
    anomaly_codes: tuple[str, ...]
    severity: str
    state: FrontierState
    source_id: str
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AnomalyQuarantineReport:
    observations: tuple[AnomalyObservation, ...]
    accepted_record_ids: tuple[str, ...]
    quarantined_record_ids: tuple[str, ...]
    issues: tuple[FrontierIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class InputAnomalyQuarantine:
    """Detect malformed intake rows and quarantine them without deletion."""

    def inspect(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        source_id: str,
        allowed_bases: str = "ACGTN",
    ) -> AnomalyQuarantineReport:
        context_key = require_non_empty(context_key, "context_key")
        source_id = require_non_empty(source_id, "source_id")
        allowed = set(allowed_bases.upper())
        if not allowed:
            raise ValidationError("allowed_bases must not be empty")
        observations: list[AnomalyObservation] = []
        issues: list[FrontierIssue] = []
        seen: set[str] = set()
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"record {index}")
            record_id = _text(row.get("record_id", row.get("id")), field="record_id")
            if not record_id:
                record_id = f"unidentified:{index}"
            codes: list[str] = []
            details: dict[str, Any] = {}
            if record_id in seen:
                codes.append("duplicate_record_id")
            seen.add(record_id)
            row_context = _text(row.get("context_key"), field="context_key")
            if not row_context:
                codes.append("missing_context_key")
            elif row_context != context_key:
                codes.append("context_mismatch")
            start_raw = row.get("start", row.get("position"))
            end_raw = row.get("end", start_raw)
            try:
                start = int(start_raw)
                end = int(end_raw)
                if start < 1 or end < start:
                    raise ValueError
            except (TypeError, ValueError):
                codes.append("invalid_coordinate")
            sequence = _sequence(row.get("sequence", ""))
            if sequence and not set(sequence).issubset(allowed):
                codes.append("invalid_sequence")
                details["unexpected_bases"] = sorted(set(sequence) - allowed)
            if not _text(row.get("source_id", source_id), field="source_id"):
                codes.append("missing_source_id")
            severity = "blocking" if codes else "info"
            state = FrontierState.QUARANTINED if codes else FrontierState.ACCEPTED
            observation = AnomalyObservation(
                record_id,
                context_key,
                tuple(sorted(set(codes))),
                severity,
                state,
                source_id,
                details,
            )
            observations.append(observation)
            issues.extend(
                FrontierIssue(
                    code,
                    f"input row quarantined for {code}",
                    "blocking",
                    record_id=record_id,
                )
                for code in observation.anomaly_codes
            )
        accepted = tuple(
            item.record_id for item in observations if item.state == FrontierState.ACCEPTED
        )
        quarantined = tuple(
            item.record_id for item in observations if item.state == FrontierState.QUARANTINED
        )
        payload = {"observations": observations, "issues": issues}
        return AnomalyQuarantineReport(
            tuple(observations), accepted, quarantined, tuple(issues), _address(payload)
        )


@dataclass(frozen=True, slots=True)
class CompletenessScore:
    record_id: str
    context_key: str
    score: float
    present_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    invalid_fields: tuple[str, ...]
    state: FrontierState
    source_id: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CompletenessReport:
    scores: tuple[CompletenessScore, ...]
    mean_score: float
    accepted_record_ids: tuple[str, ...]
    review_record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DataCompletenessScorer:
    """Score required intake fields with transparent missingness accounting."""

    def score(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        required_fields: Sequence[str],
        weights: Mapping[str, float] | None = None,
        minimum_score: float = 0.8,
        source_id: str = "completeness",
    ) -> CompletenessReport:
        context_key = require_non_empty(context_key, "context_key")
        fields = tuple(require_non_empty(str(field), "required_field") for field in required_fields)
        if not fields:
            raise ValidationError("required_fields must not be empty")
        minimum_score = _bounded(minimum_score, field="minimum_score")
        weight_map = {
            field: _float((weights or {}).get(field, 1.0), field=field) for field in fields
        }
        if any(value <= 0 for value in weight_map.values()):
            raise ValidationError("field weights must be positive")
        total_weight = sum(weight_map.values())
        scores: list[CompletenessScore] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"record {index}")
            record_id = (
                _text(row.get("record_id", row.get("id")), field="record_id") or f"row:{index}"
            )
            present: list[str] = []
            missing: list[str] = []
            invalid: list[str] = []
            earned = 0.0
            for field in fields:
                value = row.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    missing.append(field)
                    continue
                if field.endswith(("_position", "_start", "_end")):
                    try:
                        if int(value) < 1:
                            raise ValueError
                    except (TypeError, ValueError):
                        invalid.append(field)
                        continue
                present.append(field)
                earned += weight_map[field]
            score = round(earned / total_weight, 6)
            state = (
                FrontierState.ACCEPTED
                if score >= minimum_score and not invalid
                else FrontierState.REVIEW
            )
            scores.append(
                CompletenessScore(
                    record_id,
                    _context(row, context_key),
                    score,
                    tuple(present),
                    tuple(missing),
                    tuple(invalid),
                    state,
                    _text(row.get("source_id", source_id), field="source_id") or source_id,
                )
            )
        mean = round(sum(item.score for item in scores) / max(1, len(scores)), 6)
        accepted = tuple(item.record_id for item in scores if item.state == FrontierState.ACCEPTED)
        review = tuple(item.record_id for item in scores if item.state == FrontierState.REVIEW)
        return CompletenessReport(tuple(scores), mean, accepted, review, _address(scores))


@dataclass(frozen=True, slots=True)
class IntakeBundle:
    bundle_id: str
    context_key: str
    source_ids: tuple[str, ...]
    record_count: int
    records: tuple[Mapping[str, Any], ...]
    manifest: Mapping[str, Any]
    content_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class IntakeBundleExporter:
    """Create deterministic, replayable intake manifests from accepted rows."""

    def export(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        source_ids: Sequence[str] = (),
        require_accepted: bool = True,
    ) -> IntakeBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        normalized = tuple(dict(_mapping(item, label="intake record")) for item in records)
        issues: list[str] = []
        for row in normalized:
            if _text(row.get("context_key"), field="context_key") not in {"", context_key}:
                issues.append(f"context:{row.get('record_id', 'unknown')}")
            if require_accepted and _text(row.get("state"), field="state") in {
                "quarantined",
                "blocked",
                "review",
            }:
                issues.append(f"state:{row.get('record_id', 'unknown')}")
        if issues:
            raise ValidationError(f"intake bundle contains blocked records: {', '.join(issues)}")
        normalized_sources = tuple(
            sorted({require_non_empty(str(item), "source_id") for item in source_ids})
        )
        if not normalized_sources:
            normalized_sources = tuple(
                sorted(
                    {
                        _text(row.get("source_id"), field="source_id")
                        for row in normalized
                        if _text(row.get("source_id"), field="source_id")
                    }
                )
            )
        records_address = _address(normalized)
        manifest = {
            "bundle_id": bundle_id,
            "context_key": context_key,
            "record_count": len(normalized),
            "source_ids": normalized_sources,
            "records_address": records_address,
            "schema_version": "frontier-intake-v1",
        }
        address = _address({"manifest": manifest, "records": normalized})
        return IntakeBundle(
            bundle_id,
            context_key,
            normalized_sources,
            len(normalized),
            normalized,
            manifest,
            address,
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class TandemRepeatObservation:
    repeat_id: str
    context_key: str
    chromosome: str
    start: int
    end: int
    motif: str
    reference_units: float
    observed_units: float
    copy_delta: float
    uncertainty_units: float
    state: FrontierState
    source_id: str
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TandemRepeatReport:
    observations: tuple[TandemRepeatObservation, ...]
    expanded_ids: tuple[str, ...]
    contracted_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TandemRepeatInterpreter:
    """Interpret repeat copy estimates while preserving measurement uncertainty."""

    def interpret(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        source_id: str,
        minimum_motif_length: int = 1,
    ) -> TandemRepeatReport:
        context_key = require_non_empty(context_key, "context_key")
        source_id = require_non_empty(source_id, "source_id")
        if minimum_motif_length < 1:
            raise ValidationError("minimum_motif_length must be positive")
        observations: list[TandemRepeatObservation] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"repeat {index}")
            repeat_id = (
                _text(row.get("repeat_id", row.get("id")), field="repeat_id") or f"repeat:{index}"
            )
            motif = _sequence(row.get("motif"))
            local: list[FrontierIssue] = []
            if len(motif) < minimum_motif_length:
                local.append(
                    FrontierIssue(
                        "short_motif",
                        "repeat motif is shorter than the configured minimum",
                        "blocking",
                        "motif",
                        repeat_id,
                    )
                )
            if not motif or not set(motif).issubset(set("ACGTN")):
                local.append(
                    FrontierIssue(
                        "invalid_motif",
                        "repeat motif contains unsupported bases",
                        "blocking",
                        "motif",
                        repeat_id,
                    )
                )
            try:
                start = int(row.get("start"))
                end = int(row.get("end"))
                if start < 1 or end < start:
                    raise ValueError
            except (TypeError, ValueError):
                start, end = 0, 0
                local.append(
                    FrontierIssue(
                        "invalid_interval",
                        "repeat interval is invalid",
                        "blocking",
                        "start",
                        repeat_id,
                    )
                )
            reference = _float(row.get("reference_units"), field="reference_units")
            observed = _float(row.get("observed_units"), field="observed_units")
            uncertainty = _float(row.get("uncertainty_units", 0.0), field="uncertainty_units")
            if reference < 0 or observed < 0 or uncertainty < 0:
                local.append(
                    FrontierIssue(
                        "negative_repeat_measurement",
                        "repeat copy estimates cannot be negative",
                        "blocking",
                        record_id=repeat_id,
                    )
                )
            delta = round(observed - reference, 6)
            state = FrontierState.REVIEW if local else FrontierState.ACCEPTED
            observations.append(
                TandemRepeatObservation(
                    repeat_id,
                    context_key,
                    _text(row.get("chromosome", "unknown"), field="chromosome") or "unknown",
                    start,
                    end,
                    motif,
                    reference,
                    observed,
                    delta,
                    uncertainty,
                    state,
                    source_id,
                    tuple(local),
                )
            )
        expanded = tuple(
            item.repeat_id
            for item in observations
            if item.state == FrontierState.ACCEPTED and item.copy_delta > item.uncertainty_units
        )
        contracted = tuple(
            item.repeat_id
            for item in observations
            if item.state == FrontierState.ACCEPTED and item.copy_delta < -item.uncertainty_units
        )
        review = tuple(
            item.repeat_id for item in observations if item.state != FrontierState.ACCEPTED
        )
        return TandemRepeatReport(
            tuple(observations), expanded, contracted, review, _address(observations)
        )


@dataclass(frozen=True, slots=True)
class HaplotypeEvaluation:
    haplotype_id: str
    context_key: str
    variant_ids: tuple[str, ...]
    observed_variant_ids: tuple[str, ...]
    missing_variant_ids: tuple[str, ...]
    phase_state: str
    completeness: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HaplotypeEvaluationReport:
    evaluations: tuple[HaplotypeEvaluation, ...]
    compatible_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CompoundHaplotypeEvaluator:
    """Evaluate compound noncoding haplotypes without fabricating phase."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_completeness: float = 0.8,
    ) -> HaplotypeEvaluationReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_completeness = _bounded(minimum_completeness, field="minimum_completeness")
        evaluations: list[HaplotypeEvaluation] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"haplotype {index}")
            haplotype_id = (
                _text(row.get("haplotype_id", row.get("id")), field="haplotype_id")
                or f"haplotype:{index}"
            )
            required = _tuple_text(
                row.get("variant_ids", row.get("required_variant_ids", ())), field="variant_ids"
            )
            observed = _tuple_text(
                row.get("observed_variant_ids", ()), field="observed_variant_ids"
            )
            observed_set = set(observed)
            missing = tuple(item for item in required if item not in observed_set)
            completeness = round((len(required) - len(missing)) / max(1, len(required)), 6)
            phase_state = (
                _text(row.get("phase_state", "unknown"), field="phase_state").lower() or "unknown"
            )
            issues: list[FrontierIssue] = []
            if not required:
                issues.append(
                    FrontierIssue(
                        "empty_haplotype",
                        "haplotype has no declared variants",
                        "blocking",
                        record_id=haplotype_id,
                    )
                )
            if missing:
                issues.append(
                    FrontierIssue(
                        "incomplete_haplotype",
                        "one or more required variants are absent",
                        "review",
                        record_id=haplotype_id,
                    )
                )
            if phase_state not in {"cis", "trans", "unknown", "phased", "unphased"}:
                issues.append(
                    FrontierIssue(
                        "invalid_phase_state",
                        "phase state is not recognized",
                        "review",
                        "phase_state",
                        haplotype_id,
                    )
                )
            state = (
                FrontierState.ACCEPTED
                if completeness >= minimum_completeness
                and not any(item.severity == "blocking" for item in issues)
                else FrontierState.REVIEW
            )
            evaluations.append(
                HaplotypeEvaluation(
                    haplotype_id,
                    context_key,
                    required,
                    observed,
                    missing,
                    phase_state,
                    completeness,
                    state,
                    tuple(issues),
                )
            )
        compatible = tuple(
            item.haplotype_id for item in evaluations if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.haplotype_id for item in evaluations if item.state != FrontierState.ACCEPTED
        )
        return HaplotypeEvaluationReport(
            tuple(evaluations), compatible, review, _address(evaluations)
        )


@dataclass(frozen=True, slots=True)
class BreakpointInterval:
    breakpoint_id: str
    context_key: str
    chromosome: str
    left_min: int
    left_max: int
    right_min: int
    right_max: int
    propagated_uncertainty_bp: int
    confidence: float
    state: FrontierState
    source_id: str
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BreakpointPropagationReport:
    intervals: tuple[BreakpointInterval, ...]
    high_confidence_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BreakpointUncertaintyPropagator:
    """Propagate interval uncertainty through paired structural breakpoints."""

    def propagate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        source_id: str,
        minimum_confidence: float = 0.7,
    ) -> BreakpointPropagationReport:
        context_key = require_non_empty(context_key, "context_key")
        source_id = require_non_empty(source_id, "source_id")
        minimum_confidence = _bounded(minimum_confidence, field="minimum_confidence")
        intervals: list[BreakpointInterval] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"breakpoint {index}")
            breakpoint_id = (
                _text(row.get("breakpoint_id", row.get("id")), field="breakpoint_id")
                or f"breakpoint:{index}"
            )
            issues: list[FrontierIssue] = []
            values: list[int] = []
            for field in ("left_min", "left_max", "right_min", "right_max"):
                try:
                    value = int(row.get(field))
                    if value < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    value = 0
                    issues.append(
                        FrontierIssue(
                            "invalid_breakpoint_bound",
                            f"{field} must be a positive integer",
                            "blocking",
                            field,
                            breakpoint_id,
                        )
                    )
                values.append(value)
            left_min, left_max, right_min, right_max = values
            if left_max and left_min and left_max < left_min:
                issues.append(
                    FrontierIssue(
                        "inverted_left_interval",
                        "left breakpoint interval is inverted",
                        "blocking",
                        "left_max",
                        breakpoint_id,
                    )
                )
            if right_max and right_min and right_max < right_min:
                issues.append(
                    FrontierIssue(
                        "inverted_right_interval",
                        "right breakpoint interval is inverted",
                        "blocking",
                        "right_max",
                        breakpoint_id,
                    )
                )
            uncertainty = max(0, left_max - left_min) + max(0, right_max - right_min)
            confidence = _bounded(row.get("confidence", 0.0), field="confidence")
            state = (
                FrontierState.ACCEPTED
                if not issues and confidence >= minimum_confidence
                else FrontierState.REVIEW
            )
            intervals.append(
                BreakpointInterval(
                    breakpoint_id,
                    context_key,
                    _text(row.get("chromosome", "unknown"), field="chromosome") or "unknown",
                    left_min,
                    left_max,
                    right_min,
                    right_max,
                    uncertainty,
                    confidence,
                    state,
                    source_id,
                    tuple(issues),
                )
            )
        high = tuple(
            item.breakpoint_id for item in intervals if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.breakpoint_id for item in intervals if item.state != FrontierState.ACCEPTED
        )
        return BreakpointPropagationReport(tuple(intervals), high, review, _address(intervals))


@dataclass(frozen=True, slots=True)
class StructuralEvidenceBundle:
    bundle_id: str
    context_key: str
    evidence: tuple[Mapping[str, Any], ...]
    source_ids: tuple[str, ...]
    evidence_count: int
    content_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class StructuralVariantEvidenceExporter:
    """Export structural-variant evidence with deterministic source accounting."""

    def export(
        self,
        evidence: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        required_fields: Sequence[str] = ("variant_id", "evidence_type", "source_id"),
    ) -> StructuralEvidenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        fields = tuple(require_non_empty(str(item), "required_field") for item in required_fields)
        rows: list[Mapping[str, Any]] = []
        sources: set[str] = set()
        for index, raw in enumerate(evidence, start=1):
            row = _mapping(raw, label=f"evidence {index}")
            missing = [field for field in fields if not _text(row.get(field), field=field)]
            if missing:
                raise ValidationError(
                    f"evidence {index} missing required fields: {', '.join(missing)}"
                )
            row_context = _text(row.get("context_key", context_key), field="context_key")
            if row_context != context_key:
                raise ValidationError(f"evidence {index} context does not match bundle")
            normalized = dict(row)
            normalized["context_key"] = context_key
            rows.append(normalized)
            sources.add(_required_text(row.get("source_id"), field="source_id"))
        ordered = tuple(
            sorted(
                rows,
                key=lambda item: (
                    _text(item.get("variant_id"), field="variant_id"),
                    _text(item.get("source_id"), field="source_id"),
                ),
            )
        )
        address = _address(
            {"bundle_id": bundle_id, "context_key": context_key, "evidence": ordered}
        )
        return StructuralEvidenceBundle(
            bundle_id,
            context_key,
            ordered,
            tuple(sorted(sources)),
            len(ordered),
            address,
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class PreanalyticQualityObservation:
    specimen_id: str
    context_key: str
    metrics: Mapping[str, float]
    failed_metrics: tuple[str, ...]
    quality_score: float
    state: FrontierState
    source_id: str
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PreanalyticQualityReport:
    observations: tuple[PreanalyticQualityObservation, ...]
    pass_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BiospecimenPreanalyticQualityAssessor:
    """Assess declared specimen handling metrics against explicit thresholds."""

    def assess(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        source_id: str,
        thresholds: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> PreanalyticQualityReport:
        context_key = require_non_empty(context_key, "context_key")
        source_id = require_non_empty(source_id, "source_id")
        threshold_map = thresholds or {
            "ischemia_minutes": {"max": 60.0},
            "storage_temperature_c": {"min": -90.0, "max": -60.0},
            "rna_integrity": {"min": 0.6},
        }
        observations: list[PreanalyticQualityObservation] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"specimen {index}")
            specimen_id = (
                _text(row.get("specimen_id", row.get("id")), field="specimen_id")
                or f"specimen:{index}"
            )
            metrics: dict[str, float] = {}
            failed: list[str] = []
            issues: list[FrontierIssue] = []
            for name, rule_raw in threshold_map.items():
                rule = _mapping(rule_raw, label=f"threshold {name}")
                try:
                    value = _float(row.get(name), field=name)
                except ValidationError:
                    failed.append(name)
                    issues.append(
                        FrontierIssue(
                            "missing_quality_metric",
                            f"quality metric {name} is unavailable",
                            "review",
                            name,
                            specimen_id,
                        )
                    )
                    continue
                metrics[name] = value
                if "min" in rule and value < _float(rule["min"], field=f"{name}.min"):
                    failed.append(name)
                if "max" in rule and value > _float(rule["max"], field=f"{name}.max"):
                    failed.append(name)
            score = round((len(metrics) - len(set(failed))) / max(1, len(threshold_map)), 6)
            if failed:
                issues.append(
                    FrontierIssue(
                        "preanalytic_threshold_failed",
                        "one or more preanalytic metrics fail declared thresholds",
                        "review",
                        record_id=specimen_id,
                    )
                )
            state = FrontierState.ACCEPTED if not failed and metrics else FrontierState.REVIEW
            observations.append(
                PreanalyticQualityObservation(
                    specimen_id,
                    context_key,
                    metrics,
                    tuple(sorted(set(failed))),
                    score,
                    state,
                    source_id,
                    tuple(issues),
                )
            )
        passed = tuple(
            item.specimen_id for item in observations if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.specimen_id for item in observations if item.state != FrontierState.ACCEPTED
        )
        return PreanalyticQualityReport(tuple(observations), passed, review, _address(observations))


@dataclass(frozen=True, slots=True)
class ProtocolLineageNode:
    node_id: str
    specimen_id: str
    protocol_id: str
    parent_node_id: str | None
    assay: str
    operator_id: str
    started_at: str
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProtocolLineageReport:
    nodes: tuple[ProtocolLineageNode, ...]
    root_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AssayLineageProtocolTracker:
    """Track specimen-to-assay derivation and identify lineage conflicts."""

    def track(
        self, records: Iterable[Mapping[str, Any]], *, context_key: str
    ) -> ProtocolLineageReport:
        context_key = require_non_empty(context_key, "context_key")
        nodes: list[ProtocolLineageNode] = []
        ids: set[str] = set()
        parent_ids: set[str] = set()
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"lineage {index}")
            node_id = _text(row.get("node_id", row.get("id")), field="node_id") or f"node:{index}"
            specimen_id = _required_text(row.get("specimen_id"), field="specimen_id")
            protocol_id = _required_text(row.get("protocol_id"), field="protocol_id")
            parent = _text(row.get("parent_node_id"), field="parent_node_id") or None
            issues: list[FrontierIssue] = []
            if node_id in ids:
                issues.append(
                    FrontierIssue(
                        "duplicate_lineage_node",
                        "lineage node ID is duplicated",
                        "blocking",
                        "node_id",
                        node_id,
                    )
                )
            if parent:
                parent_ids.add(parent)
            ids.add(node_id)
            if _text(row.get("context_key", context_key), field="context_key") != context_key:
                issues.append(
                    FrontierIssue(
                        "lineage_context_mismatch",
                        "lineage node has a different context",
                        "blocking",
                        "context_key",
                        node_id,
                    )
                )
            nodes.append(
                ProtocolLineageNode(
                    node_id,
                    specimen_id,
                    protocol_id,
                    parent,
                    _required_text(row.get("assay"), field="assay"),
                    _required_text(row.get("operator_id"), field="operator_id"),
                    _required_text(row.get("started_at"), field="started_at"),
                    FrontierState.REVIEW if issues else FrontierState.ACCEPTED,
                    tuple(issues),
                )
            )
        known = {item.node_id for item in nodes}
        conflicts = tuple(
            sorted(
                {
                    item.node_id
                    for item in nodes
                    if item.parent_node_id and item.parent_node_id not in known
                }
                | parent_ids - known
            )
        )
        if conflicts:
            nodes = [
                ProtocolLineageNode(
                    item.node_id,
                    item.specimen_id,
                    item.protocol_id,
                    item.parent_node_id,
                    item.assay,
                    item.operator_id,
                    item.started_at,
                    FrontierState.REVIEW if item.node_id in conflicts else item.state,
                    item.issues
                    + (
                        (
                            FrontierIssue(
                                "missing_parent_node",
                                "parent lineage node is not present in the bundle",
                                "review",
                                "parent_node_id",
                                item.node_id,
                            ),
                        )
                        if item.node_id in conflicts
                        else ()
                    ),
                )
                for item in nodes
            ]
        roots = tuple(item.node_id for item in nodes if item.parent_node_id is None)
        return ProtocolLineageReport(tuple(nodes), roots, conflicts, _address(nodes))


@dataclass(frozen=True, slots=True)
class IdentityConflictDecision:
    specimen_id: str
    context_key: str
    observed_identities: tuple[str, ...]
    concordant_identities: tuple[str, ...]
    conflicting_identities: tuple[str, ...]
    agreement: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityConflictReport:
    decisions: tuple[IdentityConflictDecision, ...]
    accepted_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class IdentityConflictAdjudicator:
    """Adjudicate identity observations with explicit agreement and abstention."""

    def adjudicate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_agreement: float = 0.8,
    ) -> IdentityConflictReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_agreement = _bounded(minimum_agreement, field="minimum_agreement")
        decisions: list[IdentityConflictDecision] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"identity {index}")
            specimen_id = (
                _text(row.get("specimen_id", row.get("id")), field="specimen_id")
                or f"specimen:{index}"
            )
            observed = _tuple_text(
                row.get("observed_identities", row.get("identities", ())),
                field="observed_identities",
            )
            counts = Counter(observed)
            concordant = tuple(
                sorted(
                    identity
                    for identity, count in counts.items()
                    if count == max(counts.values(), default=0)
                )
            )
            conflicting = tuple(
                sorted(identity for identity in counts if identity not in concordant)
            )
            agreement = round((max(counts.values(), default=0) / max(1, len(observed))), 6)
            issues: list[FrontierIssue] = []
            if len(concordant) != 1:
                issues.append(
                    FrontierIssue(
                        "identity_tie",
                        "identity observations do not identify one unique mode",
                        "review",
                        record_id=specimen_id,
                    )
                )
            if conflicting:
                issues.append(
                    FrontierIssue(
                        "identity_conflict",
                        "conflicting identity observations require adjudication",
                        "review",
                        record_id=specimen_id,
                    )
                )
            state = (
                FrontierState.ACCEPTED
                if len(concordant) == 1 and agreement >= minimum_agreement and not conflicting
                else FrontierState.REVIEW
            )
            decisions.append(
                IdentityConflictDecision(
                    specimen_id,
                    context_key,
                    observed,
                    concordant,
                    conflicting,
                    agreement,
                    state,
                    tuple(issues),
                )
            )
        accepted = tuple(
            item.specimen_id for item in decisions if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.specimen_id for item in decisions if item.state != FrontierState.ACCEPTED
        )
        return IdentityConflictReport(tuple(decisions), accepted, review, _address(decisions))


@dataclass(frozen=True, slots=True)
class SpecimenContextEnvelope:
    envelope_id: str
    context_key: str
    specimen_ids: tuple[str, ...]
    lineage_address: str
    quality_address: str
    identity_address: str
    publication_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SpecimenContextEnvelopePublisher:
    """Publish a context envelope only after constituent receipts are present."""

    def publish(
        self,
        *,
        envelope_id: str,
        context_key: str,
        specimen_ids: Sequence[str],
        lineage_address: str,
        quality_address: str,
        identity_address: str,
    ) -> SpecimenContextEnvelope:
        envelope_id = require_non_empty(envelope_id, "envelope_id")
        context_key = require_non_empty(context_key, "context_key")
        ids = tuple(sorted({require_non_empty(str(item), "specimen_id") for item in specimen_ids}))
        if not ids:
            raise ValidationError("specimen_ids must not be empty")
        receipts = {
            "lineage_address": lineage_address,
            "quality_address": quality_address,
            "identity_address": identity_address,
        }
        for field, value in receipts.items():
            require_non_empty(str(value), field)
        publication_address = _address(
            {
                "envelope_id": envelope_id,
                "context_key": context_key,
                "specimen_ids": ids,
                **receipts,
            }
        )
        return SpecimenContextEnvelope(
            envelope_id,
            context_key,
            ids,
            str(lineage_address),
            str(quality_address),
            str(identity_address),
            publication_address,
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class ProvenanceCheck:
    source_id: str
    context_key: str
    source_uri: str
    declared_checksum: str
    observed_checksum: str | None
    checksum_matches: bool
    license_id: str
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProvenanceCheckReport:
    checks: tuple[ProvenanceCheck, ...]
    compatible_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SourceProvenanceChecker:
    """Check source receipts, checksums, license declarations and context."""

    def check(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        require_checksum_match: bool = True,
    ) -> ProvenanceCheckReport:
        context_key = require_non_empty(context_key, "context_key")
        checks: list[ProvenanceCheck] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"source {index}")
            source_id = (
                _text(row.get("source_id", row.get("id")), field="source_id") or f"source:{index}"
            )
            uri = _text(row.get("source_uri"), field="source_uri")
            declared = _text(
                row.get("declared_checksum", row.get("checksum")), field="declared_checksum"
            )
            observed = _text(row.get("observed_checksum"), field="observed_checksum") or None
            license_id = _text(row.get("license_id"), field="license_id")
            issues: list[FrontierIssue] = []
            if not uri:
                issues.append(
                    FrontierIssue(
                        "missing_source_uri",
                        "source URI is missing",
                        "blocking",
                        "source_uri",
                        source_id,
                    )
                )
            if not declared:
                issues.append(
                    FrontierIssue(
                        "missing_checksum",
                        "source checksum is missing",
                        "blocking",
                        "declared_checksum",
                        source_id,
                    )
                )
            if not license_id:
                issues.append(
                    FrontierIssue(
                        "missing_license",
                        "source license is missing",
                        "blocking",
                        "license_id",
                        source_id,
                    )
                )
            matches = observed is not None and observed == declared
            if require_checksum_match and not matches:
                issues.append(
                    FrontierIssue(
                        "checksum_unverified",
                        "observed checksum is absent or does not match",
                        "review",
                        "observed_checksum",
                        source_id,
                    )
                )
            if _text(row.get("context_key", context_key), field="context_key") != context_key:
                issues.append(
                    FrontierIssue(
                        "provenance_context_mismatch",
                        "source context differs from requested context",
                        "blocking",
                        "context_key",
                        source_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            checks.append(
                ProvenanceCheck(
                    source_id,
                    context_key,
                    uri,
                    declared,
                    observed,
                    matches,
                    license_id,
                    state,
                    tuple(issues),
                )
            )
        compatible = tuple(
            item.source_id for item in checks if item.state == FrontierState.ACCEPTED
        )
        review = tuple(item.source_id for item in checks if item.state != FrontierState.ACCEPTED)
        return ProvenanceCheckReport(tuple(checks), compatible, review, _address(checks))


@dataclass(frozen=True, slots=True)
class AnnotationDriftFinding:
    annotation_id: str
    context_key: str
    changed_fields: tuple[str, ...]
    old_values: Mapping[str, Any]
    new_values: Mapping[str, Any]
    change_score: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AnnotationDriftReport:
    findings: tuple[AnnotationDriftFinding, ...]
    drifted_ids: tuple[str, ...]
    stable_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AnnotationDriftDetector:
    """Compare versioned annotation rows and surface substantive field changes."""

    def compare(
        self,
        previous: Iterable[Mapping[str, Any]],
        current: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        identity_field: str = "annotation_id",
        ignored_fields: Sequence[str] = ("retrieved_at", "source_uri"),
        drift_threshold: float = 0.2,
    ) -> AnnotationDriftReport:
        context_key = require_non_empty(context_key, "context_key")
        drift_threshold = _bounded(drift_threshold, field="drift_threshold")
        prior = {
            _required_text(row.get(identity_field), field=identity_field): dict(
                _mapping(row, label="previous annotation")
            )
            for row in previous
        }
        findings: list[AnnotationDriftFinding] = []
        ignored = set(ignored_fields)
        for raw in current:
            row = _mapping(raw, label="current annotation")
            annotation_id = _required_text(row.get(identity_field), field=identity_field)
            old = prior.get(annotation_id, {})
            changed = tuple(
                sorted(
                    field
                    for field in set(old) | set(row)
                    if field not in ignored and old.get(field) != row.get(field)
                )
            )
            score = round(len(changed) / max(1, len(set(old) | set(row)) - len(ignored)), 6)
            state = (
                FrontierState.DRIFT
                if annotation_id not in prior or score >= drift_threshold
                else FrontierState.ACCEPTED
            )
            findings.append(
                AnnotationDriftFinding(
                    annotation_id,
                    context_key,
                    changed,
                    {field: old.get(field) for field in changed},
                    {field: row.get(field) for field in changed},
                    score,
                    state,
                )
            )
        drifted = tuple(
            item.annotation_id for item in findings if item.state == FrontierState.DRIFT
        )
        stable = tuple(
            item.annotation_id for item in findings if item.state == FrontierState.ACCEPTED
        )
        return AnnotationDriftReport(tuple(findings), drifted, stable, _address(findings))


@dataclass(frozen=True, slots=True)
class ReferenceBundle:
    bundle_id: str
    context_key: str
    reference_ids: tuple[str, ...]
    records: tuple[Mapping[str, Any], ...]
    schema_hash: str
    bundle_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReproducibleReferenceBundleBuilder:
    """Build a content-addressed reference bundle from provenance-checked rows."""

    def build(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        schema_hash: str,
        require_available: bool = True,
    ) -> ReferenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        schema_hash = require_non_empty(schema_hash, "schema_hash")
        normalized: list[Mapping[str, Any]] = []
        for index, raw in enumerate(records, start=1):
            row = dict(_mapping(raw, label=f"reference {index}"))
            reference_id = _required_text(
                row.get("reference_id", row.get("dataset_id")), field="reference_id"
            )
            if _text(row.get("context_key", context_key), field="context_key") != context_key:
                raise ValidationError(f"reference {reference_id} context does not match bundle")
            if require_available and _text(
                row.get("status", "available"), field="status"
            ).lower() not in {"available", "validated", "active"}:
                raise ValidationError(f"reference {reference_id} is not available")
            normalized.append(row)
        ordered = tuple(
            sorted(
                normalized,
                key=lambda item: _text(
                    item.get("reference_id", item.get("dataset_id")), field="reference_id"
                ),
            )
        )
        address = _address(
            {
                "bundle_id": bundle_id,
                "context_key": context_key,
                "schema_hash": schema_hash,
                "records": ordered,
            }
        )
        ids = tuple(
            _required_text(item.get("reference_id", item.get("dataset_id")), field="reference_id")
            for item in ordered
        )
        return ReferenceBundle(
            bundle_id, context_key, ids, ordered, schema_hash, address, FrontierState.PUBLISHED
        )


@dataclass(frozen=True, slots=True)
class ReferenceReleaseDecision:
    release_id: str
    context_key: str
    bundle_address: str
    checks: Mapping[str, bool]
    failed_checks: tuple[str, ...]
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceReleaseGate:
    """Gate a reference release on explicit integrity and policy checks."""

    def evaluate(
        self,
        *,
        release_id: str,
        context_key: str,
        bundle_address: str,
        checks: Mapping[str, Any],
        required_checks: Sequence[str] = ("checksum", "schema", "license", "context", "source"),
    ) -> ReferenceReleaseDecision:
        release_id = require_non_empty(release_id, "release_id")
        context_key = require_non_empty(context_key, "context_key")
        bundle_address = require_non_empty(bundle_address, "bundle_address")
        normalized = {
            require_non_empty(str(key), "check"): bool(value) for key, value in checks.items()
        }
        required = tuple(require_non_empty(str(key), "required_check") for key in required_checks)
        failed = tuple(key for key in required if not normalized.get(key, False))
        issues = tuple(
            FrontierIssue(
                "release_check_failed",
                f"reference release check failed: {key}",
                "blocking",
                key,
                release_id,
            )
            for key in failed
        )
        state = FrontierState.PUBLISHED if not failed else FrontierState.BLOCKED
        return ReferenceReleaseDecision(
            release_id, context_key, bundle_address, normalized, failed, state, issues
        )


def run_frontier_operation(
    operation: str, payload: Mapping[str, Any], *, context_key: str | None = None
) -> Any:
    """Run one frontier operation from a JSON payload for CLI and integrations."""

    operation = require_non_empty(operation, "operation")
    data = _mapping(payload, label="payload")
    context = context_key or _text(data.get("context_key"), field="context_key")
    if operation == "attach-consent-policy":
        return ConsentPolicyAttacher().attach(
            data.get("records", ()),
            context_key=context,
            policy_id=_required_text(data.get("policy_id"), field="policy_id"),
            policy_version=_required_text(data.get("policy_version"), field="policy_version"),
            purpose=_required_text(data.get("purpose"), field="purpose"),
            permitted_uses=_tuple_text(data.get("permitted_uses"), field="permitted_uses"),
            source_id=_required_text(data.get("source_id"), field="source_id"),
        )
    if operation == "quarantine-input-anomalies":
        return InputAnomalyQuarantine().inspect(
            data.get("records", ()),
            context_key=context,
            source_id=_required_text(data.get("source_id"), field="source_id"),
            allowed_bases=_text(data.get("allowed_bases", "ACGTN"), field="allowed_bases"),
        )
    if operation == "score-data-completeness":
        return DataCompletenessScorer().score(
            data.get("records", ()),
            context_key=context,
            required_fields=_tuple_text(data.get("required_fields"), field="required_fields"),
            weights=data.get("weights"),
            minimum_score=_float(data.get("minimum_score", 0.8), field="minimum_score"),
            source_id=_text(data.get("source_id", "completeness"), field="source_id")
            or "completeness",
        )
    if operation == "export-intake-bundle":
        return IntakeBundleExporter().export(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            source_ids=_tuple_text(data.get("source_ids", ()), field="source_ids"),
            require_accepted=bool(data.get("require_accepted", True)),
        )
    if operation == "interpret-tandem-repeats":
        return TandemRepeatInterpreter().interpret(
            data.get("records", ()),
            context_key=context,
            source_id=_required_text(data.get("source_id"), field="source_id"),
            minimum_motif_length=int(data.get("minimum_motif_length", 1)),
        )
    if operation == "evaluate-compound-haplotypes":
        return CompoundHaplotypeEvaluator().evaluate(
            data.get("records", ()),
            context_key=context,
            minimum_completeness=_float(
                data.get("minimum_completeness", 0.8), field="minimum_completeness"
            ),
        )
    if operation == "propagate-breakpoint-uncertainty":
        return BreakpointUncertaintyPropagator().propagate(
            data.get("records", ()),
            context_key=context,
            source_id=_required_text(data.get("source_id"), field="source_id"),
            minimum_confidence=_float(
                data.get("minimum_confidence", 0.7), field="minimum_confidence"
            ),
        )
    if operation == "export-structural-evidence":
        return StructuralVariantEvidenceExporter().export(
            data.get("evidence", data.get("records", ())),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            required_fields=_tuple_text(
                data.get("required_fields", ("variant_id", "evidence_type", "source_id")),
                field="required_fields",
            ),
        )
    if operation == "assess-preanalytic-quality":
        return BiospecimenPreanalyticQualityAssessor().assess(
            data.get("records", ()),
            context_key=context,
            source_id=_required_text(data.get("source_id"), field="source_id"),
            thresholds=data.get("thresholds"),
        )
    if operation == "track-assay-lineage":
        return AssayLineageProtocolTracker().track(data.get("records", ()), context_key=context)
    if operation == "adjudicate-identity-conflicts":
        return IdentityConflictAdjudicator().adjudicate(
            data.get("records", ()),
            context_key=context,
            minimum_agreement=_float(data.get("minimum_agreement", 0.8), field="minimum_agreement"),
        )
    if operation == "publish-specimen-context":
        return SpecimenContextEnvelopePublisher().publish(
            envelope_id=_required_text(data.get("envelope_id"), field="envelope_id"),
            context_key=context,
            specimen_ids=_tuple_text(data.get("specimen_ids"), field="specimen_ids"),
            lineage_address=_required_text(data.get("lineage_address"), field="lineage_address"),
            quality_address=_required_text(data.get("quality_address"), field="quality_address"),
            identity_address=_required_text(data.get("identity_address"), field="identity_address"),
        )
    if operation == "check-source-provenance":
        return SourceProvenanceChecker().check(
            data.get("records", ()),
            context_key=context,
            require_checksum_match=bool(data.get("require_checksum_match", True)),
        )
    if operation == "detect-annotation-drift":
        return AnnotationDriftDetector().compare(
            data.get("previous", ()),
            data.get("current", ()),
            context_key=context,
            identity_field=_text(
                data.get("identity_field", "annotation_id"), field="identity_field"
            )
            or "annotation_id",
            ignored_fields=_tuple_text(
                data.get("ignored_fields", ("retrieved_at", "source_uri")), field="ignored_fields"
            ),
            drift_threshold=_float(data.get("drift_threshold", 0.2), field="drift_threshold"),
        )
    if operation == "build-reference-bundle":
        return ReproducibleReferenceBundleBuilder().build(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            schema_hash=_required_text(data.get("schema_hash"), field="schema_hash"),
            require_available=bool(data.get("require_available", True)),
        )
    if operation == "gate-reference-release":
        return ReferenceReleaseGate().evaluate(
            release_id=_required_text(data.get("release_id"), field="release_id"),
            context_key=context,
            bundle_address=_required_text(data.get("bundle_address"), field="bundle_address"),
            checks=_mapping(data.get("checks", {}), label="checks"),
            required_checks=_tuple_text(
                data.get("required_checks", ("checksum", "schema", "license", "context", "source")),
                field="required_checks",
            ),
        )
    raise ValidationError(f"unknown frontier operation: {operation}")


FRONTIER_OPERATIONS = (
    "attach-consent-policy",
    "quarantine-input-anomalies",
    "score-data-completeness",
    "export-intake-bundle",
    "interpret-tandem-repeats",
    "evaluate-compound-haplotypes",
    "propagate-breakpoint-uncertainty",
    "export-structural-evidence",
    "assess-preanalytic-quality",
    "track-assay-lineage",
    "adjudicate-identity-conflicts",
    "publish-specimen-context",
    "check-source-provenance",
    "detect-annotation-drift",
    "build-reference-bundle",
    "gate-reference-release",
)
