"""Adapters from aggregate records to the four Domain 06 primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_alpha import (
    NucleosomeSequencePropensityModel,
    PromoterCoreGrammarModel,
    PromoterGrammarRule,
    PromoterMotifDefinition,
    SequenceAlphaState,
    SpliceMotifDefinition,
    SpliceRegulatoryNoncodingScanner,
    UtrMotifDefinition,
    UtrRegulatoryScanner,
)
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationOperation,
    SequenceRegulationRecord,
    SequenceRegulationState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationAdapterSpec:
    operation: SequenceRegulationOperation
    primitive: str
    required_fields: tuple[str, ...]
    output_states: tuple[str, ...]
    evidence_types: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.primitive or not self.required_fields:
            raise ValidationError("adapter spec requires primitive and fields")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "primitive": self.primitive,
                        "required_fields": self.required_fields,
                        "output_states": self.output_states,
                        "evidence_types": self.evidence_types,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationAdapterResult:
    record_id: str
    operation: SequenceRegulationOperation
    state: SequenceRegulationState
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any]
    warnings: tuple[str, ...] = ()
    primitive_state: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.detail:
            raise ValidationError("adapter result requires identity and detail")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "state": self.state,
                        "issue_codes": self.issue_codes,
                        "detail": self.detail,
                        "measurements": self.measurements,
                        "warnings": self.warnings,
                        "primitive_state": self.primitive_state,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationAdapterRegistry:
    specs: tuple[SequenceRegulationAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.specs:
            raise ValidationError("adapter registry cannot be empty")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"specs": self.specs, "accepted": self.accepted}),
            )

    def for_operation(
        self, operation: SequenceRegulationOperation
    ) -> SequenceRegulationAdapterSpec:
        for spec in self.specs:
            if spec.operation is operation:
                return spec
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "specs": [spec.to_dict() for spec in self.specs],
            "content_address": self.content_address,
        }


def _state(value: SequenceAlphaState | str) -> SequenceRegulationState:
    return SequenceRegulationState(
        str(value.value if isinstance(value, SequenceAlphaState) else value)
    )


def _result(
    record: SequenceRegulationRecord,
    state: SequenceRegulationState,
    issue_codes: tuple[str, ...],
    detail: str,
    measurements: Mapping[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
    primitive_state: str = "",
) -> SequenceRegulationAdapterResult:
    return SequenceRegulationAdapterResult(
        record_id=record.record_id,
        operation=record.operation,
        state=state,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        detail=detail,
        measurements=measurements or {},
        warnings=warnings,
        primitive_state=primitive_state,
    )


def _nucleosome(record: SequenceRegulationRecord) -> SequenceRegulationAdapterResult:
    payload = record.payload
    try:
        report = NucleosomeSequencePropensityModel().predict(
            [payload], context_key=record.context_key
        )
    except (TypeError, ValueError, ValidationError) as error:
        return _result(record, SequenceRegulationState.INVALID, ("invalid_payload",), str(error))
    codes = [issue.code for issue in report.issues]
    if report.state is SequenceAlphaState.OUT_OF_DOMAIN:
        codes.append("context_mismatch")
        return _result(
            record,
            SequenceRegulationState.OUT_OF_DOMAIN,
            tuple(codes),
            "sequence window is outside the checked-in context",
            {"window_count": 0},
            report.warnings,
            report.state.value,
        )
    if report.issues:
        codes.append(
            "invalid_sequence_alphabet"
            if any(
                "alphabet" in issue.message or "only A/C/G/T/N" in issue.message
                for issue in report.issues
            )
            else "invalid_payload"
        )
        return _result(
            record,
            SequenceRegulationState.INVALID,
            tuple(codes),
            "nucleosome window rejected",
            {"window_count": len(report.windows)},
            report.warnings,
            report.state.value,
        )
    window = report.windows[0] if report.windows else None
    if window is None:
        return _result(
            record,
            SequenceRegulationState.ABSTAINED,
            ("empty_sequence_window",),
            "no nucleosome window was evaluated",
            {"window_count": 0},
            report.warnings,
            report.state.value,
        )
    state = _state(window.state)
    codes.append("propensity_observed")
    if window.sequence_length < 147:
        codes.append("short_window")
    return _result(
        record,
        state,
        tuple(codes),
        "bounded nucleosome propensity features retained",
        {
            "window_count": 1,
            "sequence_length": window.sequence_length,
            "gc_fraction": window.gc_fraction,
            "periodicity_score": window.periodicity_score,
            "gc_balance_score": window.gc_balance_score,
            "propensity_score": window.propensity_score,
            "positioning_label": window.positioning_label,
        },
        report.warnings,
        report.state.value,
    )


def _splice_motifs(payload: Mapping[str, Any]) -> tuple[SpliceMotifDefinition, ...]:
    rows = payload.get("motifs", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("splice motifs must be a list")
    return tuple(
        SpliceMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", "")),
            consensus=str(row.get("consensus", "")),
            role=str(row.get("role", "")),
            source_id=str(row.get("source_id", "splice-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 0.8)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _splice(record: SequenceRegulationRecord) -> SequenceRegulationAdapterResult:
    payload = record.payload
    try:
        report = SpliceRegulatoryNoncodingScanner().scan(
            [payload], _splice_motifs(payload), context_key=record.context_key
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "invalid_sequence_alphabet" if "alphabet" in str(error) else "invalid_payload"
        return _result(record, SequenceRegulationState.INVALID, (code,), str(error))
    codes = [issue.code for issue in report.issues]
    if report.state is SequenceAlphaState.OUT_OF_DOMAIN:
        codes.append("context_mismatch")
        state = SequenceRegulationState.OUT_OF_DOMAIN
    elif report.issues:
        codes.append(
            "invalid_sequence_alphabet"
            if any(
                "alphabet" in issue.message or "only A/C/G/T/N" in issue.message
                for issue in report.issues
            )
            else "invalid_payload"
        )
        state = SequenceRegulationState.INVALID
    elif not report.windows:
        codes.append("no_splice_observation")
        state = SequenceRegulationState.ABSTAINED
    else:
        window = report.windows[0]
        if window.disrupted_hits:
            codes.append("motif_disrupted")
        if window.created_hits:
            codes.append("motif_created")
        if not window.created_hits and not window.disrupted_hits:
            codes.append("no_motif_change")
        state = (
            SequenceRegulationState.ABSTAINED
            if not window.created_hits and not window.disrupted_hits
            else _state(window.state)
        )
    window = report.windows[0] if report.windows else None
    return _result(
        record,
        state,
        tuple(codes),
        "splice motif observations and allele deltas retained",
        {
            "window_count": len(report.windows),
            "reference_hit_count": len(window.reference_hits) if window else 0,
            "alternate_hit_count": len(window.alternate_hits) if window else 0,
            "created_hit_count": len(window.created_hits) if window else 0,
            "disrupted_hit_count": len(window.disrupted_hits) if window else 0,
        },
        report.warnings,
        report.state.value,
    )


def _utr_motifs(payload: Mapping[str, Any]) -> tuple[UtrMotifDefinition, ...]:
    rows = payload.get("motifs", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("UTR motifs must be a list")
    return tuple(
        UtrMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", "")),
            consensus=str(row.get("consensus", "")),
            element_kind=str(row.get("element_kind", "")),
            region=str(row.get("region", "")),
            source_id=str(row.get("source_id", "utr-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 0.8)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _utr(record: SequenceRegulationRecord) -> SequenceRegulationAdapterResult:
    payload = record.payload
    try:
        report = UtrRegulatoryScanner().scan(
            [payload], _utr_motifs(payload), context_key=record.context_key
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "invalid_utr_region" if "region" in str(error) else "invalid_payload"
        return _result(record, SequenceRegulationState.INVALID, (code,), str(error))
    codes = [issue.code for issue in report.issues]
    if report.state is SequenceAlphaState.OUT_OF_DOMAIN:
        codes.append("context_mismatch")
        state = SequenceRegulationState.OUT_OF_DOMAIN
    elif report.issues:
        codes.append(
            "invalid_utr_region"
            if any("region" in issue.message for issue in report.issues)
            else "invalid_payload"
        )
        state = SequenceRegulationState.INVALID
    elif not report.windows:
        codes.append("no_utr_observation")
        state = SequenceRegulationState.ABSTAINED
    else:
        window = report.windows[0]
        if window.reference_hits:
            codes.append("utr_element_observed")
        if window.upstream_orfs:
            codes.append("uorf_observed")
        if not window.reference_hits and not window.upstream_orfs:
            codes.append("no_utr_observation")
        if "N" in str(payload.get("sequence", "")).upper():
            codes.append("ambiguous_bases")
        state = _state(window.state)
    window = report.windows[0] if report.windows else None
    return _result(
        record,
        state,
        tuple(codes),
        "UTR element and bounded upstream-pattern observations retained",
        {
            "window_count": len(report.windows),
            "reference_hit_count": len(window.reference_hits) if window else 0,
            "alternate_hit_count": len(window.alternate_hits) if window else 0,
            "created_hit_count": len(window.created_hits) if window else 0,
            "disrupted_hit_count": len(window.disrupted_hits) if window else 0,
            "upstream_orf_count": len(window.upstream_orfs) if window else 0,
        },
        report.warnings,
        report.state.value,
    )


def _promoter_motifs(payload: Mapping[str, Any]) -> tuple[PromoterMotifDefinition, ...]:
    rows = payload.get("motifs", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("promoter motifs must be a list")
    return tuple(
        PromoterMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", "")),
            consensus=str(row.get("consensus", "")),
            element_kind=str(row.get("element_kind", "")),
            source_id=str(row.get("source_id", "promoter-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 0.8)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _promoter_rules(payload: Mapping[str, Any]) -> tuple[PromoterGrammarRule, ...]:
    rows = payload.get("rules", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("promoter rules must be a list")
    return tuple(
        PromoterGrammarRule(
            rule_id=str(row.get("rule_id", "")),
            motif_a=str(row.get("motif_a", "")),
            motif_b=str(row.get("motif_b", "")),
            minimum_spacing=int(row.get("minimum_spacing", 0)),
            maximum_spacing=int(row.get("maximum_spacing", 0)),
            allowed_orientations=tuple(
                str(value) for value in row.get("allowed_orientations", ("any",))
            ),
            weight=float(row.get("weight", 1.0)),
            source_id=str(row.get("source_id", "promoter-input")),
            source_version=str(row.get("source_version", "unspecified")),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _promoter(record: SequenceRegulationRecord) -> SequenceRegulationAdapterResult:
    payload = record.payload
    try:
        report = PromoterCoreGrammarModel().evaluate(
            [payload],
            _promoter_motifs(payload),
            _promoter_rules(payload),
            context_key=record.context_key,
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "invalid_sequence_alphabet" if "alphabet" in str(error) else "invalid_payload"
        return _result(record, SequenceRegulationState.INVALID, (code,), str(error))
    codes = [issue.code for issue in report.issues]
    if report.state is SequenceAlphaState.OUT_OF_DOMAIN:
        codes.append("context_mismatch")
        state = SequenceRegulationState.OUT_OF_DOMAIN
    elif report.issues:
        codes.append(
            "invalid_sequence_alphabet"
            if any(
                "alphabet" in issue.message or "only A/C/G/T/N" in issue.message
                for issue in report.issues
            )
            else "invalid_payload"
        )
        state = SequenceRegulationState.INVALID
    elif not report.evaluations:
        codes.append("no_grammar_evaluation")
        state = SequenceRegulationState.ABSTAINED
    else:
        evaluation = report.evaluations[0]
        if evaluation.compatible_pairs:
            codes.append("grammar_rule_matched")
        else:
            codes.append("no_grammar_pair")
        state = _state(evaluation.state)
    evaluation = report.evaluations[0] if report.evaluations else None
    return _result(
        record,
        state,
        tuple(codes),
        "promoter motif hits and declared spacing grammar retained",
        {
            "evaluation_count": len(report.evaluations),
            "hit_count": len(evaluation.hits) if evaluation else 0,
            "pair_count": len(evaluation.compatible_pairs) if evaluation else 0,
            "matched_rule_count": len(evaluation.matched_rule_ids) if evaluation else 0,
            "unmatched_rule_count": len(evaluation.unmatched_rule_ids) if evaluation else 0,
            "weighted_coverage": evaluation.weighted_coverage if evaluation else 0.0,
        },
        report.warnings,
        report.state.value,
    )


def execute_sequence_regulation_record(
    record: SequenceRegulationRecord,
) -> SequenceRegulationAdapterResult:
    """Execute one record through its declared low-level primitive."""

    if record.operation is SequenceRegulationOperation.NUCLEOSOME_PROPENSITY:
        return _nucleosome(record)
    if record.operation is SequenceRegulationOperation.SPLICE_REGULATION:
        return _splice(record)
    if record.operation is SequenceRegulationOperation.UTR_REGULATION:
        return _utr(record)
    if record.operation is SequenceRegulationOperation.PROMOTER_GRAMMAR:
        return _promoter(record)
    raise AssertionError(record.operation)


def build_sequence_regulation_adapters() -> SequenceRegulationAdapterRegistry:
    """Return the closed adapter registry for the four operations."""

    states = tuple(state.value for state in SequenceRegulationState)
    specs = (
        SequenceRegulationAdapterSpec(
            SequenceRegulationOperation.NUCLEOSOME_PROPENSITY,
            "NucleosomeSequencePropensityModel",
            ("sequence", "context_key"),
            states,
            ("sequence_index", "public_aggregate"),
        ),
        SequenceRegulationAdapterSpec(
            SequenceRegulationOperation.SPLICE_REGULATION,
            "SpliceRegulatoryNoncodingScanner",
            ("reference_sequence", "alternate_sequence", "motifs"),
            states,
            ("motif_catalog", "allele_comparison"),
        ),
        SequenceRegulationAdapterSpec(
            SequenceRegulationOperation.UTR_REGULATION,
            "UtrRegulatoryScanner",
            ("region", "sequence", "motifs"),
            states,
            ("utr_elements", "bounded_uorf"),
        ),
        SequenceRegulationAdapterSpec(
            SequenceRegulationOperation.PROMOTER_GRAMMAR,
            "PromoterCoreGrammarModel",
            ("sequence", "motifs", "rules"),
            states,
            ("motif_catalog", "spacing_grammar"),
        ),
    )
    return SequenceRegulationAdapterRegistry(
        specs, accepted=len(specs) == len(SequenceRegulationOperation)
    )


__all__ = [
    "SequenceRegulationAdapterRegistry",
    "SequenceRegulationAdapterResult",
    "SequenceRegulationAdapterSpec",
    "build_sequence_regulation_adapters",
    "execute_sequence_regulation_record",
]
