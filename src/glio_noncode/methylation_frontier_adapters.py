"""Adapters from aggregate records to methylation-beta primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_beta import (
    CpGCreationLossAnalyzer,
    IdhHypermethylationContextModel,
    MethylationBetaState,
    MethylationContextRetriever,
    MethylationRecord,
    MethylationRecordParser,
    MethylationSensitiveMotifAnalyzer,
    MethylationSensitiveMotifDefinition,
)
from .methylation_frontier_public_data import (
    MethylationFrontierOperation,
    MethylationFrontierRecord,
    MethylationFrontierState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierAdapterSpec:
    operation: MethylationFrontierOperation
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
class MethylationFrontierAdapterResult:
    record_id: str
    operation: MethylationFrontierOperation
    state: MethylationFrontierState
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
class MethylationFrontierAdapterRegistry:
    specs: tuple[MethylationFrontierAdapterSpec, ...]
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
        self, operation: MethylationFrontierOperation
    ) -> MethylationFrontierAdapterSpec:
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


def _state(value: MethylationBetaState | str) -> MethylationFrontierState:
    return MethylationFrontierState(
        str(value.value if isinstance(value, MethylationBetaState) else value)
    )


def _result(
    record: MethylationFrontierRecord,
    state: MethylationFrontierState,
    issue_codes: tuple[str, ...],
    detail: str,
    measurements: Mapping[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
    primitive_state: str = "",
) -> MethylationFrontierAdapterResult:
    return MethylationFrontierAdapterResult(
        record_id=record.record_id,
        operation=record.operation,
        state=state,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        detail=detail,
        measurements=measurements or {},
        warnings=warnings,
        primitive_state=primitive_state,
    )


def _records(
    payload: Mapping[str, Any], key: str = "methylation_records"
) -> tuple[MethylationRecord | Mapping[str, Any], ...]:
    rows = payload.get(key, ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError(f"{key} must be a list")
    return tuple(row for row in rows if isinstance(row, (MethylationRecord, Mapping)))


def _context_record_mismatch(payload: Mapping[str, Any], context_key: str) -> bool:
    rows = payload.get("methylation_records", ())
    return any(
        isinstance(row, Mapping) and row.get("context_key") not in {None, context_key}
        for row in rows
    )


def _context_retrieval(record: MethylationFrontierRecord) -> MethylationFrontierAdapterResult:
    payload = record.payload
    try:
        batch = MethylationRecordParser().parse_text(
            str(payload.get("text", "")),
            source_id=str(payload.get("source_id", "methylation-input")),
            source_version=str(payload.get("source_version", "unspecified")),
            input_format=str(payload.get("input_format", "tsv")),
            coordinate_system=str(payload.get("coordinate_system", "one_based")),
        )
        query = payload.get("query", {})
        if not isinstance(query, Mapping):
            raise ValidationError("methylation query must be an object")
        result = MethylationContextRetriever(batch.records).query(
            str(query.get("chromosome", "")),
            int(query.get("start", 0)),
            int(query.get("end", 0)),
            context_key=record.context_key,
            beta_spread_tolerance=float(payload.get("beta_spread_tolerance", 0.20)),
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "empty_input" if not str(payload.get("text", "")).strip() else "invalid_payload"
        return _result(record, MethylationFrontierState.INVALID, (code,), str(error))
    codes = [issue.code for issue in batch.issues]
    if batch.issues:
        codes.append("parse_issue")
    state = _state(result.state)
    if result.state is MethylationBetaState.OUT_OF_DOMAIN:
        codes.append("context_mismatch")
    elif result.state is MethylationBetaState.ABSENT:
        codes.append("no_context_overlap")
    elif result.state is MethylationBetaState.SUPPORTED:
        codes.append("context_query_supported")
    if batch.issues and state is MethylationFrontierState.SUPPORTED:
        state = MethylationFrontierState.PARTIAL
    return _result(
        record,
        state,
        tuple(codes),
        "parsed methylation records and exact-context query retained",
        {
            "parsed_record_count": len(batch.records),
            "parse_issue_count": len(batch.issues),
            "query_record_count": len(result.records),
            "median_beta": result.median_beta,
            "beta_spread": result.beta_spread,
            "median_coverage": result.median_coverage,
        },
        ("Exact-context methylation retrieval does not impute missing beta values.",),
        result.state.value,
    )


def _cpg_change(record: MethylationFrontierRecord) -> MethylationFrontierAdapterResult:
    payload = record.payload
    try:
        report = CpGCreationLossAnalyzer().analyze(
            str(payload.get("reference_sequence", "")),
            str(payload.get("alternate_sequence", "")),
            variant_id=str(payload.get("variant_id", "")),
            window_start=int(payload.get("window_start", 1)),
            chromosome=str(payload.get("chromosome", "unspecified")),
            context_key=record.context_key,
            methylation_records=_records(payload),
            methylated_threshold=float(payload.get("methylated_threshold", 0.50)),
        )
    except (TypeError, ValueError, ValidationError) as error:
        return _result(record, MethylationFrontierState.INVALID, ("invalid_payload",), str(error))
    codes = [issue.code for issue in report.issues]
    if report.created:
        codes.append("cpg_created")
    if report.lost:
        codes.append("cpg_lost")
    if report.methylation_context_state is MethylationBetaState.SUPPORTED:
        codes.append("methylation_supported")
    elif report.methylation_context_state is MethylationBetaState.AMBIGUOUS:
        codes.append("methylation_ambiguous")
    if report.state is MethylationBetaState.INVALID:
        state = MethylationFrontierState.INVALID
        if any(issue.code == "invalid_sequence_alphabet" for issue in report.issues):
            codes.append("invalid_sequence_alphabet")
    elif report.state is MethylationBetaState.OUT_OF_DOMAIN:
        state = MethylationFrontierState.OUT_OF_DOMAIN
        codes.append("length_change_out_of_domain")
    elif not report.created and not report.lost:
        state = MethylationFrontierState.ABSTAINED
        codes.append("no_cpg_change")
    else:
        state = _state(report.methylation_context_state)
        if state is MethylationFrontierState.ABSTAINED:
            state = MethylationFrontierState.SUPPORTED
    return _result(
        record,
        state,
        tuple(codes),
        "equal-length CpG creation/loss and exact methylation context retained",
        {
            "reference_cpg_count": len(report.reference_cpg_starts),
            "alternate_cpg_count": len(report.alternate_cpg_starts),
            "created_count": len(report.created),
            "lost_count": len(report.lost),
            "methylated_change_count": sum(
                change.methylation_state == "methylated" for change in report.created + report.lost
            ),
            "methylation_context_state": report.methylation_context_state.value,
        },
        report.warnings,
        report.state.value,
    )


def _motifs(payload: Mapping[str, Any]) -> tuple[MethylationSensitiveMotifDefinition, ...]:
    rows = payload.get("motifs", ())
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("methylation-sensitive motifs must be a list")
    return tuple(
        MethylationSensitiveMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", "")),
            consensus=str(row.get("consensus", "")),
            source_id=str(row.get("source_id", "motif-input")),
            source_version=str(row.get("source_version", "unspecified")),
            sensitive_positions=tuple(int(value) for value in row.get("sensitive_positions", ())),
            threshold=float(row.get("threshold", 1.0)),
            methylated_threshold=float(row.get("methylated_threshold", 0.50)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _sensitive_motif(record: MethylationFrontierRecord) -> MethylationFrontierAdapterResult:
    payload = record.payload
    try:
        report = MethylationSensitiveMotifAnalyzer().analyze(
            str(payload.get("sequence", "")),
            sequence_id=str(payload.get("sequence_id", "")),
            motifs=_motifs(payload),
            methylation_records=_records(payload),
            window_start=int(payload.get("window_start", 1)),
            chromosome=str(payload.get("chromosome", "unspecified")),
            context_key=record.context_key,
        )
    except (TypeError, ValueError, ValidationError) as error:
        code = "invalid_sequence_window" if "sequence" in str(error) else "invalid_payload"
        return _result(record, MethylationFrontierState.INVALID, (code,), str(error))
    codes = [issue.code for issue in report.issues]
    if report.hits:
        codes.append("sensitive_motif_observed")
    states = {hit.methylation_state for hit in report.hits}
    if "missing" in states:
        codes.append("missing_methylation")
    if "ambiguous" in states:
        codes.append("methylation_ambiguous")
    if states & {"methylated", "unmethylated"}:
        codes.append("methylation_supported")
    if _context_record_mismatch(payload, record.context_key):
        codes.append("context_mismatch")
    state = _state(report.state)
    if report.state is MethylationBetaState.SUPPORTED and "context_mismatch" in codes:
        state = MethylationFrontierState.PARTIAL
    if report.state is MethylationBetaState.ABSENT:
        codes.append("no_sensitive_motif")
    return _result(
        record,
        state,
        tuple(codes),
        "methylation-sensitive motif hits and measured offsets retained",
        {
            "hit_count": len(report.hits),
            "methylated_hit_count": sum(
                hit.methylation_state == "methylated" for hit in report.hits
            ),
            "missing_hit_count": sum(hit.methylation_state == "missing" for hit in report.hits),
            "ambiguous_hit_count": sum(hit.methylation_state == "ambiguous" for hit in report.hits),
            "source_count": len(report.source_ids),
        },
        report.warnings,
        report.state.value,
    )


def _idh_context(record: MethylationFrontierRecord) -> MethylationFrontierAdapterResult:
    payload = record.payload
    try:
        report = IdhHypermethylationContextModel().assess(
            _records(payload, "target_records"),
            context_key=str(payload.get("context_key", record.context_key)),
            molecular_state=str(payload.get("molecular_state", "IDH-mutant")),
            comparator_records=_records(payload, "comparator_records"),
            comparator_state=str(payload.get("comparator_state", "IDH-wildtype")),
            model_id=str(payload.get("model_id", "idh-input")),
            model_version=str(payload.get("model_version", "unspecified")),
            methylated_threshold=float(payload.get("methylated_threshold", 0.70)),
            minimum_sites=int(payload.get("minimum_sites", 3)),
        )
    except (TypeError, ValueError, ValidationError) as error:
        return _result(record, MethylationFrontierState.INVALID, ("invalid_payload",), str(error))
    codes: list[str] = []
    if report.state is MethylationBetaState.SUPPORTED:
        codes.extend(("idh_panel_supported", "comparator_supported"))
    elif report.state is MethylationBetaState.PARTIAL:
        codes.append("comparator_support_incomplete")
    elif report.state is MethylationBetaState.OUT_OF_DOMAIN:
        codes.append("context_mismatch")
    elif report.state is MethylationBetaState.ABSTAINED:
        codes.append("target_support_absent")
    return _result(
        record,
        _state(report.state),
        tuple(codes),
        "descriptive IDH panel summary and comparator delta retained",
        {
            "measured_site_count": report.measured_site_count,
            "high_methylation_site_count": report.high_methylation_site_count,
            "high_methylation_fraction": report.high_methylation_fraction,
            "mean_beta": report.mean_beta,
            "median_beta": report.median_beta,
            "coverage_weighted_beta": report.coverage_weighted_beta,
            "comparator_site_count": report.comparator_site_count,
            "comparator_mean_beta": report.comparator_mean_beta,
            "delta_vs_comparator": report.delta_vs_comparator,
            "hypermethylated": report.hypermethylated,
        },
        report.warnings,
        report.state.value,
    )


def execute_methylation_frontier_record(
    record: MethylationFrontierRecord,
) -> MethylationFrontierAdapterResult:
    """Execute one record through its declared methylation operation."""

    if record.operation is MethylationFrontierOperation.CONTEXT_RETRIEVAL:
        return _context_retrieval(record)
    if record.operation is MethylationFrontierOperation.CPG_CHANGE:
        return _cpg_change(record)
    if record.operation is MethylationFrontierOperation.SENSITIVE_MOTIF:
        return _sensitive_motif(record)
    if record.operation is MethylationFrontierOperation.IDH_CONTEXT:
        return _idh_context(record)
    raise AssertionError(record.operation)


def build_methylation_frontier_adapters() -> MethylationFrontierAdapterRegistry:
    """Return the closed adapter registry for C05-C08."""

    states = tuple(state.value for state in MethylationFrontierState)
    specs = (
        MethylationFrontierAdapterSpec(
            MethylationFrontierOperation.CONTEXT_RETRIEVAL,
            "MethylationRecordParser+MethylationContextRetriever",
            ("text", "source_id", "query", "context_key"),
            states,
            ("methylation_track", "exact_context_query"),
        ),
        MethylationFrontierAdapterSpec(
            MethylationFrontierOperation.CPG_CHANGE,
            "CpGCreationLossAnalyzer",
            ("reference_sequence", "alternate_sequence", "variant_id"),
            states,
            ("sequence_delta", "methylation_context"),
        ),
        MethylationFrontierAdapterSpec(
            MethylationFrontierOperation.SENSITIVE_MOTIF,
            "MethylationSensitiveMotifAnalyzer",
            ("sequence", "motifs", "methylation_records"),
            states,
            ("motif_catalog", "sensitive_offsets"),
        ),
        MethylationFrontierAdapterSpec(
            MethylationFrontierOperation.IDH_CONTEXT,
            "IdhHypermethylationContextModel",
            ("target_records", "comparator_records", "model_id", "model_version"),
            states,
            ("aggregate_panel", "comparator_delta"),
        ),
    )
    return MethylationFrontierAdapterRegistry(
        specs,
        accepted=len(specs) == len(MethylationFrontierOperation),
    )


__all__ = [
    "MethylationFrontierAdapterRegistry",
    "MethylationFrontierAdapterResult",
    "MethylationFrontierAdapterSpec",
    "build_methylation_frontier_adapters",
    "execute_methylation_frontier_record",
]
