"""Operation adapters for the Domain 06 C05-C08 aggregate frontier.

The adapters bind the public record shape to the deterministic motif primitives
in :mod:`glio_noncode.sequence_beta`.  They preserve raw boundary conditions,
keep every compatible hit or pair, and return explicit state plus issue codes.
The cooperative result remains a descriptive score and is never converted to a
probability.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import ValidationError
from .sequence_beta import (
    CooperativeTFGrammarModel,
    GrammarInteraction,
    MotifCreationScanner,
    MotifDefinition,
    MotifDisruptionScanner,
    MotifGrammarRule,
    MotifHit,
    MotifSpacingGrammarAnalyzer,
    SequenceBetaState,
)
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarOperation,
    SequenceGrammarRecord,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarAdapterResult:
    """Normalized result returned by every beta operation adapter."""

    record_id: str
    operation: SequenceGrammarOperation
    state: SequenceGrammarState
    issue_codes: tuple[str, ...]
    detail: str
    measurements: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.detail.strip():
            raise ValidationError("adapter results require record identity and detail")
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
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarAdapterSpec:
    operation: SequenceGrammarOperation
    implementation: str
    required_fields: tuple[str, ...]
    boundary_states: tuple[str, ...]
    source_families: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.implementation.strip() or not self.required_fields:
            raise ValidationError("adapter specification is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "implementation": self.implementation,
                        "required_fields": self.required_fields,
                        "boundary_states": self.boundary_states,
                        "source_families": self.source_families,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarAdapterRegistry:
    specifications: tuple[SequenceGrammarAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.specifications:
            raise ValidationError("adapter registry cannot be empty")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"specifications": self.specifications, "accepted": self.accepted}),
            )

    def for_operation(self, operation: SequenceGrammarOperation) -> SequenceGrammarAdapterSpec:
        for specification in self.specifications:
            if specification.operation is operation:
                return specification
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "specifications": [item.to_dict() for item in self.specifications],
            "content_address": self.content_address,
        }


def _motifs(payload: Mapping[str, Any]) -> tuple[MotifDefinition, ...]:
    rows = payload.get("motifs", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("motifs must be a list")
    return tuple(
        MotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", row.get("motif_id", ""))),
            consensus=str(row.get("consensus", "")),
            source_id=str(row.get("source_id", "motif-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 1.0)),
            strand_aware=bool(row.get("strand_aware", True)),
            attributes=row.get("attributes", {}),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _hits(payload: Mapping[str, Any]) -> tuple[MotifHit | Mapping[str, Any], ...]:
    rows = payload.get("hits", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("hits must be a list")
    return tuple(row for row in rows if isinstance(row, Mapping))


def _rules(payload: Mapping[str, Any]) -> tuple[MotifGrammarRule, ...]:
    rows = payload.get("rules", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("rules must be a list")
    return tuple(
        MotifGrammarRule(
            rule_id=str(row.get("rule_id", "")),
            motif_a=str(row.get("motif_a", "")),
            motif_b=str(row.get("motif_b", "")),
            minimum_spacing=int(row.get("minimum_spacing", 0)),
            maximum_spacing=int(row.get("maximum_spacing", 0)),
            allowed_orientations=tuple(
                str(value) for value in row.get("allowed_orientations", ("any",))
            ),
            source_id=str(row.get("source_id", "grammar-input")),
            source_version=str(row.get("source_version", "unspecified")),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _interactions(payload: Mapping[str, Any]) -> tuple[GrammarInteraction, ...]:
    rows = payload.get("interactions", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("interactions must be a list")
    return tuple(
        GrammarInteraction(
            interaction_id=str(row.get("interaction_id", "")),
            motif_a=str(row.get("motif_a", "")),
            motif_b=str(row.get("motif_b", "")),
            weight=float(row.get("weight", 0.0)),
            maximum_spacing=int(row.get("maximum_spacing", 0)),
            required=bool(row.get("required", False)),
            source_id=str(row.get("source_id", "grammar-model")),
            source_version=str(row.get("source_version", "unspecified")),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _state(value: SequenceBetaState | str) -> SequenceGrammarState:
    return SequenceGrammarState(str(value.value if isinstance(value, SequenceBetaState) else value))


def _result(
    record: SequenceGrammarRecord,
    state: SequenceGrammarState,
    issue_codes: tuple[str, ...],
    detail: str,
    measurements: Mapping[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
) -> SequenceGrammarAdapterResult:
    return SequenceGrammarAdapterResult(
        record_id=record.record_id,
        operation=record.operation,
        state=state,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        detail=detail,
        measurements=measurements or {},
        warnings=warnings,
    )


def _scan_record(record: SequenceGrammarRecord, *, creation: bool) -> SequenceGrammarAdapterResult:
    payload = record.payload
    try:
        motifs = _motifs(payload)
        if not motifs:
            return _result(
                record,
                SequenceGrammarState.ABSTAINED,
                ("empty_motif_catalog",),
                "no declared motifs",
                {"motif_count": 0},
            )
        scanner = MotifCreationScanner() if creation else MotifDisruptionScanner()
        report = scanner.scan(
            str(payload.get("reference", "")),
            str(payload.get("alternate", "")),
            variant_id=str(payload.get("variant_id", "")),
            motifs=motifs,
            window_start=int(payload.get("window_start", 1)),
            context_key=str(payload.get("context_key", "")) or None,
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "invalid_payload"
        if "alphabet" in str(error) or "sequence must" in str(error):
            code = "invalid_sequence_alphabet"
        return _result(record, SequenceGrammarState.INVALID, (code,), str(error))
    issue_codes = tuple(issue.code for issue in report.issues)
    if (
        "N" in str(payload.get("reference", "")).upper()
        or "N" in str(payload.get("alternate", "")).upper()
    ):
        issue_codes += ("ambiguous_bases",)
    if creation:
        if report.created_hits:
            issue_codes += ("motif_gain",)
        measurement = {
            "reference_hit_count": len(report.reference_hits),
            "alternate_hit_count": len(report.alternate_hits),
            "created_hit_count": len(report.created_hits),
            "disrupted_hit_count": len(report.disrupted_hits),
        }
        detail = "alternate-only motif hits retained"
    else:
        if report.disrupted_hits:
            issue_codes += ("motif_loss",)
        measurement = {
            "reference_hit_count": len(report.reference_hits),
            "alternate_hit_count": len(report.alternate_hits),
            "created_hit_count": len(report.created_hits),
            "disrupted_hit_count": len(report.disrupted_hits),
            "retained_hit_count": report.retained_hit_count,
        }
        detail = "reference-only motif hits retained"
    state = _state(report.state)
    if "invalid_sequence_alphabet" in issue_codes:
        state = SequenceGrammarState.INVALID
    elif "empty_sequence_window" in issue_codes:
        state = SequenceGrammarState.ABSTAINED
    if "ambiguous_bases" in issue_codes and state is SequenceGrammarState.SUPPORTED:
        state = SequenceGrammarState.PARTIAL
    return _result(record, state, issue_codes, detail, measurement, report.warnings)


def _spacing_record(record: SequenceGrammarRecord) -> SequenceGrammarAdapterResult:
    payload = record.payload
    try:
        hit_rows = _hits(payload)
        if not hit_rows:
            return _result(
                record,
                SequenceGrammarState.ABSTAINED,
                ("empty_hit_set",),
                "no motif hits supplied",
                {"hit_count": 0},
            )
        report = MotifSpacingGrammarAnalyzer().analyze(
            hit_rows, _rules(payload), context_key=str(payload.get("context_key", "")) or None
        )
    except (TypeError, ValueError, ValidationError) as error:
        return _result(record, SequenceGrammarState.INVALID, ("invalid_hit",), str(error))
    issue_codes = list(issue.code for issue in report.issues)
    if report.observations:
        issue_codes.append("compatible_spacing")
    if report.unmatched_rule_ids:
        issue_codes.append("unmatched_rule")
    return _result(
        record,
        _state(report.state),
        tuple(issue_codes),
        "all compatible motif pairs retained",
        {
            "hit_count": len(hit_rows),
            "rule_count": len(_rules(payload)),
            "observation_count": len(report.observations),
            "unmatched_rule_count": len(report.unmatched_rule_ids),
        },
        report.warnings,
    )


def _cooperative_record(record: SequenceGrammarRecord) -> SequenceGrammarAdapterResult:
    payload = record.payload
    try:
        interactions = _interactions(payload)
        report = CooperativeTFGrammarModel().score(
            _hits(payload),
            interactions,
            sequence_id=str(payload.get("sequence_id", "")),
            sequence=str(payload.get("sequence", "")),
            model_id=str(payload.get("model_id", "")),
            model_version=str(payload.get("model_version", "")),
            context_key=str(payload.get("context_key", "")) or None,
            baseline=float(payload.get("baseline", 0.0)),
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "invalid_payload"
        if "alphabet" in str(error) or "sequence must" in str(error):
            code = "invalid_sequence_alphabet"
        return _result(record, SequenceGrammarState.INVALID, (code,), str(error))
    issue_codes = list("missing_required_interaction" for _ in report.missing_required_interactions)
    if not interactions:
        issue_codes.append("empty_interaction_catalog")
    if report.interaction_contributions:
        issue_codes.append("interaction_supported")
    return _result(
        record,
        _state(report.state),
        tuple(issue_codes),
        "weighted motif interaction contributions retained",
        {
            "score": report.score,
            "interaction_count": len(interactions),
            "contribution_count": len(report.interaction_contributions),
            "missing_required_count": len(report.missing_required_interactions),
            "matched_motif_count": len(report.matched_motif_ids),
        },
        report.warnings,
    )


def execute_sequence_grammar_record(record: SequenceGrammarRecord) -> SequenceGrammarAdapterResult:
    """Execute exactly one fixture record through its declared operation."""

    if record.operation is SequenceGrammarOperation.MOTIF_DISRUPTION:
        return _scan_record(record, creation=False)
    if record.operation is SequenceGrammarOperation.MOTIF_CREATION:
        return _scan_record(record, creation=True)
    if record.operation is SequenceGrammarOperation.SPACING_GRAMMAR:
        return _spacing_record(record)
    if record.operation is SequenceGrammarOperation.COOPERATIVE_GRAMMAR:
        return _cooperative_record(record)
    raise AssertionError(record.operation)


def build_sequence_grammar_adapters() -> SequenceGrammarAdapterRegistry:
    """Return the closed adapter registry used by runtime and schema gates."""

    specs = (
        SequenceGrammarAdapterSpec(
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            "MotifDisruptionScanner",
            ("variant_id", "reference", "alternate", "motifs"),
            tuple(state.value for state in SequenceGrammarState),
            ("motif_catalog", "cis_regulatory_aggregate"),
        ),
        SequenceGrammarAdapterSpec(
            SequenceGrammarOperation.MOTIF_CREATION,
            "MotifCreationScanner",
            ("variant_id", "reference", "alternate", "motifs"),
            tuple(state.value for state in SequenceGrammarState),
            ("motif_catalog", "cis_regulatory_aggregate"),
        ),
        SequenceGrammarAdapterSpec(
            SequenceGrammarOperation.SPACING_GRAMMAR,
            "MotifSpacingGrammarAnalyzer",
            ("hits", "rules"),
            tuple(state.value for state in SequenceGrammarState),
            ("motif_catalog", "grammar_benchmark"),
        ),
        SequenceGrammarAdapterSpec(
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            "CooperativeTFGrammarModel",
            ("sequence", "hits", "interactions", "model_id", "model_version"),
            tuple(state.value for state in SequenceGrammarState),
            ("motif_catalog", "grammar_model"),
        ),
    )
    return SequenceGrammarAdapterRegistry(
        specs, accepted=len(specs) == len(SequenceGrammarOperation)
    )


__all__ = [
    "SequenceGrammarAdapterRegistry",
    "SequenceGrammarAdapterResult",
    "SequenceGrammarAdapterSpec",
    "build_sequence_grammar_adapters",
    "execute_sequence_grammar_record",
]
