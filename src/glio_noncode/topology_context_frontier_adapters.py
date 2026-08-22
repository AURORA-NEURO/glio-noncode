"""Typed operation adapters for the Domain 09 C01-C04 fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .models import ReferenceContext
from .serialization import content_hash, jsonable
from .topology_context import (
    ContactMatrixNormalizer,
    ContactMatrixParser,
    ContactMatrixQcEvaluator,
    InsulationScoreDeltaEstimator,
    InsulationScoreMeasurement,
    TadBoundaryEnsembleBuilder,
    TadBoundaryParser,
    TopologyAssay,
    TopologyContactRetriever,
    TopologyState,
)
from .topology_context_frontier_public_data import (
    TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY,
    TopologyContextFrontierOperation,
    TopologyContextFrontierRecord,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierAdapterSpec:
    operation: TopologyContextFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierAdapterResult:
    record_id: str
    operation: TopologyContextFrontierOperation
    state: str
    primitive_state: str
    issue_codes: tuple[str, ...]
    measurements: dict[str, Any]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierAdapterRegistry:
    specs: tuple[TopologyContextFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(
        self, operation: TopologyContextFrontierOperation | str
    ) -> TopologyContextFrontierAdapterSpec:
        value = TopologyContextFrontierOperation(str(operation))
        for spec in self.specs:
            if spec.operation is value:
                return spec
        raise KeyError(value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "specs": [item.to_dict() for item in self.specs],
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def _context(key: str) -> ReferenceContext:
    parts = key.split("|")
    if len(parts) != 6:
        raise ValueError("topology context key must have six fields")
    return ReferenceContext(
        parts[0],
        parts[1],
        parts[2],
        parts[3],
        territory=parts[4],
        treatment_phase=parts[5],
    )


def _rows(record: TopologyContextFrontierRecord, key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in record.payload.get(key, ()) if isinstance(item, dict)]


def _result(
    record: TopologyContextFrontierRecord,
    primitive_state: str,
    state: str | None = None,
    *,
    issue_codes: tuple[str, ...] = (),
    measurements: dict[str, Any] | None = None,
    evidence_ids: tuple[str, ...] = (),
) -> TopologyContextFrontierAdapterResult:
    value = state or primitive_state
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "state": value,
        "primitive_state": primitive_state,
        "issues": issue_codes,
        "measurements": measurements or {},
        "evidence_ids": evidence_ids,
    }
    return TopologyContextFrontierAdapterResult(
        record_id=record.record_id,
        operation=record.operation,
        state=value,
        primitive_state=primitive_state,
        issue_codes=issue_codes,
        measurements=measurements or {},
        source_ids=record.source_ids,
        evidence_ids=evidence_ids,
        content_address=content_hash(body),
    )


def _contact_result(record: TopologyContextFrontierRecord) -> TopologyContextFrontierAdapterResult:
    rows = _rows(record, "contacts")
    target_key = str(
        record.payload.get("target_context_key", TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY)
    )
    issues: list[str] = []
    try:
        batch = ContactMatrixParser().parse_text(
            json.dumps({"records": rows}),
            source_id=record.source_ids[0],
            assay=TopologyAssay.HI_C,
            input_format="json",
        )
        issues.extend(item.code for item in batch.issues)
        if target_key != record.context_key:
            issues.append("context_mismatch")
        if batch.records and not any(item.context_key == target_key for item in batch.records):
            issues.append("context_mismatch")
        if not batch.records:
            return _result(
                record,
                TopologyState.ABSTAINED.value,
                issue_codes=tuple(dict.fromkeys(issues or ["no_contact_rows"])),
                measurements={"record_count": 0, "parser_issue_count": len(batch.issues)},
            )
        first = batch.records[0]
        query = TopologyContactRetriever(batch.records).query(
            first.assay,
            first.chromosome_a,
            first.start_a,
            first.end_a,
            first.chromosome_b,
            first.start_b,
            first.end_b,
            _context(target_key),
        )
        state = query.state.value
        if issues and state == TopologyState.SUPPORTED.value:
            state = TopologyState.PARTIAL.value
        measurements = {
            "record_count": len(batch.records),
            "parser_issue_count": len(batch.issues),
            "query_state": query.state.value,
            "median_signal": query.median_signal,
            "replicate_spread": query.replicate_spread,
            "interaction_ids": [item.interaction_id for item in query.records],
            "source_versions": sorted({item.source_version for item in batch.records}),
            "query_address": query.content_address,
        }
        return _result(
            record,
            query.state.value,
            state,
            issue_codes=tuple(dict.fromkeys(issues)),
            measurements=measurements,
            evidence_ids=tuple(item.interaction_id for item in query.records),
        )
    except (TypeError, ValueError, KeyError) as exc:
        return _result(
            record,
            TopologyState.ABSTAINED.value,
            TopologyState.PARTIAL.value,
            issue_codes=tuple(dict.fromkeys((*issues, "invalid_contact_payload", str(exc)))),
        )


def _matrix_result(record: TopologyContextFrontierRecord) -> TopologyContextFrontierAdapterResult:
    rows = _rows(record, "contacts")
    target_key = str(
        record.payload.get("target_context_key", TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY)
    )
    try:
        batch = ContactMatrixParser().parse_text(
            json.dumps({"records": rows}),
            source_id=record.source_ids[0],
            assay=TopologyAssay.HI_C,
            input_format="json",
        )
        if batch.records and not any(item.context_key == target_key for item in batch.records):
            return _result(
                record,
                TopologyState.OUT_OF_DOMAIN.value,
                issue_codes=("context_mismatch",),
                measurements={
                    "record_count": len(batch.records),
                    "parser_issue_count": len(batch.issues),
                },
            )
        qc = ContactMatrixQcEvaluator().evaluate(
            tuple(item for item in batch.records if item.context_key == target_key),
            normalization_method=str(record.payload.get("normalization_method", "mean")),
        )
        normalized = ContactMatrixNormalizer().normalize(
            tuple(item for item in batch.records if item.context_key == target_key),
            method=str(record.payload.get("normalization_method", "mean")),
        )
        issues = tuple(item.code for item in batch.issues)
        state = (
            TopologyState.PARTIAL.value
            if issues and qc.state is TopologyState.SUPPORTED
            else qc.state.value
        )
        if not batch.records:
            state = TopologyState.ABSTAINED.value
            issues = tuple(dict.fromkeys((*issues, "no_contact_rows")))
        return _result(
            record,
            qc.state.value,
            state,
            issue_codes=issues,
            measurements={
                "record_count": qc.record_count,
                "unique_pair_count": qc.unique_pair_count,
                "duplicate_count": qc.duplicate_count,
                "zero_signal_count": qc.zero_signal_count,
                "mean_signal": qc.mean_signal,
                "normalized_state": normalized.state.value,
                "normalization_method": normalized.qc.normalization_method,
                "normalization_address": normalized.content_address,
            },
            evidence_ids=tuple(item.interaction_id for item in batch.records),
        )
    except (TypeError, ValueError, KeyError) as exc:
        return _result(
            record,
            TopologyState.ABSTAINED.value,
            "invalid",
            issue_codes=("invalid_matrix_payload", str(exc)),
        )


def _boundary_result(record: TopologyContextFrontierRecord) -> TopologyContextFrontierAdapterResult:
    rows = _rows(record, "boundaries")
    target_key = str(
        record.payload.get("target_context_key", TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY)
    )
    try:
        batch = TadBoundaryParser().parse_text(
            json.dumps({"boundaries": rows}),
            source_id=record.source_ids[0],
            assay=TopologyAssay.HI_C,
            input_format="json",
        )
        result = TadBoundaryEnsembleBuilder().build(
            batch.observations,
            chromosome="7",
            region_start=900,
            region_end=3100,
            context=_context(target_key),
            tolerance=50,
        )
        issues = [item.code for item in batch.issues]
        if batch.observations and not any(
            item.context_key == target_key for item in batch.observations
        ):
            issues.append("context_mismatch")
        state = (
            TopologyState.PARTIAL.value
            if issues and result.state is TopologyState.SUPPORTED
            else result.state.value
        )
        return _result(
            record,
            result.state.value,
            state,
            issue_codes=tuple(dict.fromkeys(issues)),
            measurements={
                "observation_count": len(batch.observations),
                "parser_issue_count": len(batch.issues),
                "representative_position": result.representative_position,
                "agreement": result.agreement,
                "cluster_count": len(result.clusters),
                "cluster_addresses": [content_hash(item.to_dict()) for item in result.clusters],
            },
            evidence_ids=tuple(item.boundary_id for item in batch.observations),
        )
    except (TypeError, ValueError, KeyError) as exc:
        return _result(
            record,
            TopologyState.ABSTAINED.value,
            "invalid",
            issue_codes=("invalid_boundary_payload", str(exc)),
        )


def _insulation_result(
    record: TopologyContextFrontierRecord,
) -> TopologyContextFrontierAdapterResult:
    target_key = str(
        record.payload.get("target_context_key", TOPOLOGY_CONTEXT_FRONTIER_CONTEXT_KEY)
    )
    raw = record.payload.get("measurement")
    if target_key != record.context_key:
        return _result(record, TopologyState.OUT_OF_DOMAIN.value, issue_codes=("context_mismatch",))
    if not isinstance(raw, dict):
        return _result(
            record,
            TopologyState.ABSTAINED.value,
            "invalid",
            issue_codes=("invalid_insulation_payload",),
        )
    try:
        reference = raw.get("reference_score")
        alternate = raw.get("alternate_score")
        measurement = InsulationScoreMeasurement(
            measurement_id=str(raw["measurement_id"]),
            variant_id=str(raw["variant_id"]),
            context_key=record.context_key,
            reference_score=None if reference is None else float(reference),
            alternate_score=None if alternate is None else float(alternate),
            source_id=record.source_ids[0],
            raw_hash=content_hash(raw),
            replicate_count=int(raw.get("replicate_count", 1)),
        )
        result = InsulationScoreDeltaEstimator().estimate(measurement)
        issues = ("missing_insulation_score",) if result.state is TopologyState.ABSTAINED else ()
        return _result(
            record,
            result.state.value,
            issue_codes=issues,
            measurements={
                "variant_id": result.variant_id,
                "delta": result.delta,
                "relative_delta": result.relative_delta,
                "direction": result.direction,
                "replicate_count": result.replicate_count,
                "result_address": result.content_address,
            },
            evidence_ids=(result.variant_id,),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _result(
            record,
            TopologyState.ABSTAINED.value,
            "invalid",
            issue_codes=("invalid_insulation_score", str(exc)),
        )


def execute_topology_context_frontier_record(
    record: TopologyContextFrontierRecord,
) -> TopologyContextFrontierAdapterResult:
    if record.operation is TopologyContextFrontierOperation.CONTACT_IMPORT:
        return _contact_result(record)
    if record.operation is TopologyContextFrontierOperation.MATRIX_QC:
        return _matrix_result(record)
    if record.operation is TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE:
        return _boundary_result(record)
    return _insulation_result(record)


def build_topology_context_frontier_adapters() -> TopologyContextFrontierAdapterRegistry:
    specs = (
        TopologyContextFrontierAdapterSpec(
            TopologyContextFrontierOperation.CONTACT_IMPORT,
            "topology-contact-parser-v1",
            "ContactMatrixParser + TopologyContactRetriever",
            ("contacts", "target_context_key", "normalization_method"),
            ("record_count", "query_state", "median_signal", "interaction_ids"),
            "Contact retrieval is context and assay qualified, not a causal claim.",
        ),
        TopologyContextFrontierAdapterSpec(
            TopologyContextFrontierOperation.MATRIX_QC,
            "topology-matrix-qc-v1",
            "ContactMatrixQcEvaluator + ContactMatrixNormalizer",
            ("contacts", "target_context_key", "normalization_method"),
            ("duplicate_count", "zero_signal_count", "normalized_state"),
            "Mean and max scaling do not establish assay bias correction.",
        ),
        TopologyContextFrontierAdapterSpec(
            TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE,
            "topology-boundary-ensemble-v1",
            "TadBoundaryParser + TadBoundaryEnsembleBuilder",
            ("boundaries", "target_context_key"),
            ("representative_position", "agreement", "cluster_count"),
            "Boundary clustering is measured topology evidence only.",
        ),
        TopologyContextFrontierAdapterSpec(
            TopologyContextFrontierOperation.INSULATION_DELTA,
            "topology-insulation-delta-v1",
            "InsulationScoreDeltaEstimator",
            ("measurement", "target_context_key"),
            ("delta", "relative_delta", "direction"),
            "Insulation deltas are assay-derived comparisons, not effects.",
        ),
    )
    return TopologyContextFrontierAdapterRegistry(
        specs=specs,
        accepted=len(specs) == len(TopologyContextFrontierOperation),
    )


__all__ = [
    "TopologyContextFrontierAdapterRegistry",
    "TopologyContextFrontierAdapterResult",
    "TopologyContextFrontierAdapterSpec",
    "build_topology_context_frontier_adapters",
    "execute_topology_context_frontier_record",
]
