"""Typed adapters from C09-C12 public rows to chromatin-alpha primitives."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .chromatin_alpha import (
    AlleleSpecificChromatinAnalyzer,
    BatchCellCompositionCorrector,
    ChromatinStateSegmentationAdapter,
    EpigenomicPurityDeconvolver,
)
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierOperation,
    ChromatinAlphaFrontierRecord,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierAdapterSpec:
    operation: ChromatinAlphaFrontierOperation
    primitive: str
    required_fields: tuple[str, ...]
    output_states: tuple[str, ...]
    evidence_types: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.primitive or not self.required_fields or not self.output_states:
            raise ValidationError("adapter spec is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierAdapterResult:
    record_id: str
    operation: ChromatinAlphaFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any]
    warnings: tuple[str, ...]
    primitive_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.detail or not self.state:
            raise ValidationError("adapter result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierAdapterRegistry:
    specs: tuple[ChromatinAlphaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.specs) != len(ChromatinAlphaFrontierOperation):
            raise ValidationError("adapter registry must cover four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: ChromatinAlphaFrontierOperation
    ) -> ChromatinAlphaFrontierAdapterSpec:
        for spec in self.specs:
            if spec.operation is operation:
                return spec
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rows(record: ChromatinAlphaFrontierRecord) -> list[dict[str, Any]]:
    raw = record.payload.get("input_text", "[]")
    try:
        value = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError("input_text must be a JSON list") from error
    if not isinstance(value, list):
        raise ValidationError("input_text must contain a list")
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _issue_codes(report: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(issue.code) for issue in report.issues))


def _result(
    record: ChromatinAlphaFrontierRecord,
    state: str,
    issue_codes: tuple[str, ...],
    detail: str,
    measurements: Mapping[str, Any],
    warnings: tuple[str, ...],
    primitive_state: str,
) -> ChromatinAlphaFrontierAdapterResult:
    return ChromatinAlphaFrontierAdapterResult(
        record_id=record.record_id,
        operation=record.operation,
        state=state,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        detail=detail,
        measurements=measurements,
        warnings=warnings,
        primitive_state=primitive_state,
    )


def _execute_segmentation(
    record: ChromatinAlphaFrontierRecord,
) -> ChromatinAlphaFrontierAdapterResult:
    payload = record.payload
    report = ChromatinStateSegmentationAdapter().segment(
        _rows(record),
        context_key=record.context_key,
        low_signal=float(payload.get("low_signal", 0.25)),
        high_signal=float(payload.get("high_signal", 0.75)),
    )
    issues = _issue_codes(report)
    return _result(
        record,
        report.state.value,
        issues,
        "interval boundaries, replicate labels, and transparent chromatin states retained",
        {
            "observation_count": len(report.observations),
            "segment_count": len(report.segments),
            "state_labels": sorted({segment.state_label for segment in report.segments}),
            "support_counts": [segment.support_count for segment in report.segments],
            "signal_spreads": [segment.signal_spread for segment in report.segments],
        },
        report.warnings,
        report.state.value,
    )


def _execute_allele_specific(
    record: ChromatinAlphaFrontierRecord,
) -> ChromatinAlphaFrontierAdapterResult:
    payload = record.payload
    report = AlleleSpecificChromatinAnalyzer().analyze(
        _rows(record),
        context_key=record.context_key,
        ambiguity_tolerance=float(payload.get("ambiguity_tolerance", 0.3)),
        delta_threshold=float(payload.get("delta_threshold", 0.1)),
    )
    issues = _issue_codes(report)
    return _result(
        record,
        report.state.value,
        issues,
        "replicate-aware reference/alternate signal deltas retained without causal interpretation",
        {
            "observation_count": len(report.observations),
            "result_count": len(report.results),
            "variant_ids": sorted({result.variant_id for result in report.results}),
            "directions": sorted({result.direction for result in report.results}),
            "median_deltas": [result.median_delta for result in report.results],
        },
        report.warnings,
        report.state.value,
    )


def _execute_purity(record: ChromatinAlphaFrontierRecord) -> ChromatinAlphaFrontierAdapterResult:
    payload = record.payload
    report = EpigenomicPurityDeconvolver().estimate(
        _rows(record),
        context_key=record.context_key,
        minimum_markers=int(payload.get("minimum_markers", 2)),
        spread_tolerance=float(payload.get("spread_tolerance", 0.2)),
    )
    issues = _issue_codes(report)
    return _result(
        record,
        report.state.value,
        issues,
        "declared tumor/normal marker mixture estimates retain denominators and spread",
        {
            "marker_count": len(report.marker_observations),
            "estimate_count": len(report.estimates),
            "aggregate_purity": report.aggregate_purity,
            "purity_spread": report.purity_spread,
            "estimate_states": sorted({estimate.state.value for estimate in report.estimates}),
        },
        report.warnings,
        report.state.value,
    )


def _execute_composition(
    record: ChromatinAlphaFrontierRecord,
) -> ChromatinAlphaFrontierAdapterResult:
    payload = record.payload
    offsets = payload.get("batch_offsets", {})
    target = payload.get("target_composition")
    report = BatchCellCompositionCorrector().correct(
        _rows(record),
        context_key=record.context_key,
        batch_offsets=offsets if isinstance(offsets, Mapping) else {},
        target_composition=target if isinstance(target, Mapping) else None,
    )
    issues = _issue_codes(report)
    return _result(
        record,
        report.state.value,
        issues,
        "raw signal, batch term, composition term, and corrected signal retained",
        {
            "observation_count": len(report.observations),
            "correction_count": len(report.corrections),
            "corrected_feature_ids": [correction.feature_id for correction in report.corrections],
            "corrected_signals": [correction.corrected_signal for correction in report.corrections],
            "batch_adjustments": [correction.batch_adjustment for correction in report.corrections],
            "composition_adjustments": [
                correction.composition_adjustment for correction in report.corrections
            ],
        },
        report.warnings,
        report.state.value,
    )


def execute_chromatin_alpha_frontier_record(
    record: ChromatinAlphaFrontierRecord,
) -> ChromatinAlphaFrontierAdapterResult:
    """Execute one typed record against exactly one low-level primitive."""

    try:
        if record.operation is ChromatinAlphaFrontierOperation.SEGMENTATION:
            return _execute_segmentation(record)
        if record.operation is ChromatinAlphaFrontierOperation.ALLELE_SPECIFIC:
            return _execute_allele_specific(record)
        if record.operation is ChromatinAlphaFrontierOperation.PURITY:
            return _execute_purity(record)
        if record.operation is ChromatinAlphaFrontierOperation.COMPOSITION_CORRECTION:
            return _execute_composition(record)
    except (TypeError, ValueError, ValidationError) as error:
        return _result(
            record,
            "invalid",
            ("invalid_payload",),
            str(error),
            {},
            ("Malformed primitive input remains visible as invalid.",),
            "invalid",
        )
    raise ValidationError(f"unsupported operation: {record.operation}")


def build_chromatin_alpha_frontier_adapters() -> ChromatinAlphaFrontierAdapterRegistry:
    states = ("supported", "partial", "ambiguous", "out_of_domain", "invalid", "abstained")
    specs = (
        ChromatinAlphaFrontierAdapterSpec(
            ChromatinAlphaFrontierOperation.SEGMENTATION,
            "ChromatinStateSegmentationAdapter.segment",
            ("input_text", "low_signal", "high_signal"),
            states,
            ("interval", "replicate", "state"),
        ),
        ChromatinAlphaFrontierAdapterSpec(
            ChromatinAlphaFrontierOperation.ALLELE_SPECIFIC,
            "AlleleSpecificChromatinAnalyzer.analyze",
            ("input_text", "ambiguity_tolerance", "delta_threshold"),
            states,
            ("reference_signal", "alternate_signal", "delta"),
        ),
        ChromatinAlphaFrontierAdapterSpec(
            ChromatinAlphaFrontierOperation.PURITY,
            "EpigenomicPurityDeconvolver.estimate",
            ("input_text", "minimum_markers", "spread_tolerance"),
            states,
            ("marker", "denominator", "bounded_estimate"),
        ),
        ChromatinAlphaFrontierAdapterSpec(
            ChromatinAlphaFrontierOperation.COMPOSITION_CORRECTION,
            "BatchCellCompositionCorrector.correct",
            ("input_text", "batch_offsets", "target_composition"),
            states,
            ("raw_signal", "batch_term", "composition_term", "corrected_signal"),
        ),
    )
    return ChromatinAlphaFrontierAdapterRegistry(
        specs, len({spec.operation for spec in specs}) == 4
    )


__all__ = [
    "ChromatinAlphaFrontierAdapterRegistry",
    "ChromatinAlphaFrontierAdapterResult",
    "ChromatinAlphaFrontierAdapterSpec",
    "build_chromatin_alpha_frontier_adapters",
    "execute_chromatin_alpha_frontier_record",
]
