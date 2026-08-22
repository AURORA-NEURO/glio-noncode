"""Typed adapters for the four Domain 07 context operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .chromatin_context import (
    AccessibilityDeltaEstimator,
    AccessibilityMeasurement,
    ChromatinContextRetriever,
    ChromatinState,
    ChromatinTrackKind,
    ChromatinTrackParser,
    H3K27acActivityEstimator,
)
from .chromatin_context_frontier_public_data import (
    ChromatinContextFrontierExpectedState,
    ChromatinContextFrontierOperation,
    ChromatinContextFrontierRecord,
)
from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierAdapterSpec:
    operation: ChromatinContextFrontierOperation
    primitive: str
    required_fields: tuple[str, ...]
    output_states: tuple[str, ...]
    evidence_types: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.primitive or not self.required_fields or not self.output_states:
            raise ValidationError("context adapter spec is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierAdapterResult:
    record_id: str
    operation: ChromatinContextFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any]
    warnings: tuple[str, ...]
    primitive_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.state or not self.detail:
            raise ValidationError("context adapter result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierAdapterRegistry:
    specs: tuple[ChromatinContextFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.specs) != len(ChromatinContextFrontierOperation):
            raise ValidationError("context adapter registry must cover four operations")
        if len({item.operation for item in self.specs}) != len(self.specs):
            raise ValidationError("context adapter operations must be unique")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: ChromatinContextFrontierOperation
    ) -> ChromatinContextFrontierAdapterSpec:
        for item in self.specs:
            if item.operation is operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rows(record: ChromatinContextFrontierRecord) -> list[dict[str, Any]]:
    raw = record.payload.get("track_text", "")
    try:
        payload = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError("track_text must be JSON") from error
    rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise ValidationError("track_text must contain an observations list")
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _context(key: str) -> ReferenceContext:
    parts = key.split("|")
    if len(parts) != 6:
        raise ValidationError("context key must have six parts")
    return ReferenceContext(*parts[:4], territory=parts[4], treatment_phase=parts[5])


def _codes(issues: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item.code) for item in issues))


def _result(
    record: ChromatinContextFrontierRecord,
    state: str,
    issue_codes: tuple[str, ...],
    detail: str,
    measurements: Mapping[str, Any],
    warnings: tuple[str, ...],
    primitive_state: str,
) -> ChromatinContextFrontierAdapterResult:
    return ChromatinContextFrontierAdapterResult(
        record_id=record.record_id,
        operation=record.operation,
        state=state,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        detail=detail,
        measurements=measurements,
        warnings=warnings,
        primitive_state=primitive_state,
    )


def _track_operation(
    record: ChromatinContextFrontierRecord,
) -> ChromatinContextFrontierAdapterResult:
    payload = record.payload
    batch = ChromatinTrackParser().parse_text(
        str(payload["track_text"]),
        source_id=record.source_ids[0],
        track_kind=str(payload.get("track_kind", "atac")),
        input_format="json",
    )
    query = ChromatinContextRetriever(batch.observations).query(
        str(payload.get("track_kind", "atac")),
        str(payload.get("chromosome", "chr7")),
        int(payload.get("start", 100)),
        int(payload.get("end", 120)),
        _context(record.context_key),
    )
    codes = _codes(batch.issues)
    primitive_state = query.state.value
    if query.state is ChromatinState.OUT_OF_DOMAIN:
        state = ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN.value
    elif query.state is ChromatinState.AMBIGUOUS:
        state = ChromatinContextFrontierExpectedState.AMBIGUOUS.value
    elif query.state is ChromatinState.SUPPORTED and batch.issues:
        state = ChromatinContextFrontierExpectedState.PARTIAL.value
    elif query.state is ChromatinState.SUPPORTED:
        state = ChromatinContextFrontierExpectedState.SUPPORTED.value
    else:
        state = ChromatinContextFrontierExpectedState.ABSTAINED.value
    return _result(
        record,
        state,
        codes,
        "track coordinates, assay kind, context gate, and replicate spread are retained",
        {
            "parsed_count": len(batch.observations),
            "quarantined_count": len(batch.issues),
            "query_state": query.state.value,
            "median_signal": query.median_signal,
            "replicate_spread": query.replicate_spread,
            "observation_ids": [item.observation_id for item in query.observations],
            "mark_values": sorted({item.mark for item in query.observations if item.mark}),
        },
        ("Interval overlap is not an enhancer or regulatory truth claim.",),
        primitive_state,
    )


def _accessibility_operation(
    record: ChromatinContextFrontierRecord,
) -> ChromatinContextFrontierAdapterResult:
    payload = record.payload
    measured_context = str(payload.get("context_key", record.context_key))
    if measured_context != record.context_key:
        return _result(
            record,
            ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN.value,
            ("context_mismatch",),
            "measurement context does not match the declared fixture context",
            {"measurement_context": measured_context},
            ("Cross-context measurements are not transported into the target context.",),
            "out_of_domain",
        )
    measurement = AccessibilityMeasurement(
        measurement_id=str(payload["measurement_id"]),
        variant_id=str(payload["variant_id"]),
        context_key=measured_context,
        assay=ChromatinTrackKind(str(payload["assay"])),
        reference_signal=payload.get("reference_signal"),
        alternate_signal=payload.get("alternate_signal"),
        source_id=str(payload["source_id"]),
        raw_hash=str(payload["raw_hash"]),
        replicate_count=int(payload.get("replicate_count", 1)),
    )
    delta = AccessibilityDeltaEstimator().estimate(measurement)
    return _result(
        record,
        delta.state.value,
        (),
        "measured reference and alternate accessibility remain separate from causal interpretation",
        {
            "variant_id": delta.variant_id,
            "assay": measurement.assay.value,
            "reference_signal": measurement.reference_signal,
            "alternate_signal": measurement.alternate_signal,
            "delta": delta.delta,
            "relative_delta": delta.relative_delta,
            "replicate_count": delta.replicate_count,
        },
        delta.limitations,
        delta.state.value,
    )


def _histone_operation(
    record: ChromatinContextFrontierRecord,
) -> ChromatinContextFrontierAdapterResult:
    result = _track_operation(record)
    measurements = dict(result.measurements)
    measurements["requested_mark"] = record.payload.get("mark")
    return ChromatinContextFrontierAdapterResult(
        record_id=result.record_id,
        operation=result.operation,
        state=result.state,
        issue_codes=result.issue_codes,
        detail="histone mark metadata, context gating, and replicate spread are retained",
        measurements=measurements,
        warnings=result.warnings
        + ("Mark presence does not establish a complete chromatin mechanism.",),
        primitive_state=result.primitive_state,
    )


def _h3k27ac_operation(
    record: ChromatinContextFrontierRecord,
) -> ChromatinContextFrontierAdapterResult:
    payload = record.payload
    batch = ChromatinTrackParser().parse_text(
        str(payload["track_text"]),
        source_id=record.source_ids[0],
        track_kind=ChromatinTrackKind.H3K27AC,
        input_format="json",
    )
    query = ChromatinContextRetriever(batch.observations).query(
        ChromatinTrackKind.H3K27AC,
        str(payload.get("chromosome", "chr7")),
        int(payload.get("start", 100)),
        int(payload.get("end", 120)),
        _context(record.context_key),
    )
    activity = H3K27acActivityEstimator().estimate(str(payload["element_id"]), query)
    codes = _codes(batch.issues)
    state = activity.state.value
    if query.state is ChromatinState.OUT_OF_DOMAIN:
        state = ChromatinContextFrontierExpectedState.OUT_OF_DOMAIN.value
        codes = tuple(dict.fromkeys(codes + ("context_mismatch",)))
    elif query.state is ChromatinState.SUPPORTED and batch.issues:
        state = ChromatinContextFrontierExpectedState.PARTIAL.value
    return _result(
        record,
        state,
        codes,
        "H3K27ac signal is surfaced as a replicate-aware observation with explicit limits",
        {
            "element_id": activity.element_id,
            "signal": activity.signal,
            "replicate_count": activity.replicate_count,
            "query_state": query.state.value,
            "replicate_spread": query.replicate_spread,
        },
        activity.limitations,
        activity.state.value,
    )


def execute_chromatin_context_frontier_record(
    record: ChromatinContextFrontierRecord,
) -> ChromatinContextFrontierAdapterResult:
    """Execute one fixture row against the matching low-level primitive."""

    try:
        if record.operation is ChromatinContextFrontierOperation.TRACK_RETRIEVAL:
            return _track_operation(record)
        if record.operation is ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA:
            return _accessibility_operation(record)
        if record.operation is ChromatinContextFrontierOperation.HISTONE_CONTEXT:
            return _histone_operation(record)
        if record.operation is ChromatinContextFrontierOperation.H3K27AC_ACTIVITY:
            return _h3k27ac_operation(record)
    except (TypeError, ValueError, ValidationError, KeyError) as error:
        return _result(
            record,
            ChromatinContextFrontierExpectedState.INVALID.value,
            ("invalid_payload",),
            str(error),
            {},
            ("Malformed input remains visible as an invalid result.",),
            "invalid",
        )
    raise ValidationError(f"unsupported context operation: {record.operation}")


def build_chromatin_context_frontier_adapters() -> ChromatinContextFrontierAdapterRegistry:
    states = tuple(item.value for item in ChromatinContextFrontierExpectedState)
    common = ("context", "coordinate", "source_receipt")
    specs = (
        ChromatinContextFrontierAdapterSpec(
            ChromatinContextFrontierOperation.TRACK_RETRIEVAL,
            "ChromatinTrackParser.parse_text + ChromatinContextRetriever.query",
            common + ("track_text", "track_kind"),
            states,
            ("BED-like interval", "assay", "replicate", "context key"),
            ("Overlap is evidence retrieval only.", "Malformed rows are quarantined."),
        ),
        ChromatinContextFrontierAdapterSpec(
            ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA,
            "AccessibilityDeltaEstimator.estimate",
            common + ("measurement_id", "reference_signal", "alternate_signal"),
            states,
            ("reference signal", "alternate signal", "absolute delta", "relative delta"),
            ("Zero baseline blocks relative normalization.", "Missing values abstain."),
        ),
        ChromatinContextFrontierAdapterSpec(
            ChromatinContextFrontierOperation.HISTONE_CONTEXT,
            "ChromatinTrackParser.parse_text + ChromatinContextRetriever.query",
            common + ("track_text", "track_kind", "mark"),
            states,
            ("histone mark", "coordinate", "replicate", "context key"),
            (
                "Mark presence does not establish a mechanism.",
                "Cross-assay calibration is not inferred.",
            ),
        ),
        ChromatinContextFrontierAdapterSpec(
            ChromatinContextFrontierOperation.H3K27AC_ACTIVITY,
            "H3K27acActivityEstimator.estimate",
            common + ("track_text", "element_id"),
            states,
            ("H3K27ac signal", "replicate count", "signal spread", "limitations"),
            (
                "Signal is not a target-gene linkage.",
                "Activity claims require independent evidence.",
            ),
        ),
    )
    return ChromatinContextFrontierAdapterRegistry(specs, True)


__all__ = [
    "ChromatinContextFrontierAdapterRegistry",
    "ChromatinContextFrontierAdapterResult",
    "ChromatinContextFrontierAdapterSpec",
    "build_chromatin_context_frontier_adapters",
    "execute_chromatin_context_frontier_record",
]
