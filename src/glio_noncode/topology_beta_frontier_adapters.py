"""Typed execution adapters for the Domain 09 C05-C08 aggregate fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta import (
    ActivityByContactScorer,
    EnhancerPromoterContactScorer,
    LoopStripeAdapter,
    PromoterCaptureContactAdapter,
)
from .topology_beta_frontier_public_data import (
    TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY,
    TopologyBetaFrontierOperation,
    TopologyBetaFrontierRecord,
)
from .topology_context import TopologyState


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierAdapterSpec:
    operation: TopologyBetaFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    state_rules: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierAdapterResult:
    record_id: str
    operation: TopologyBetaFrontierOperation
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
class TopologyBetaFrontierAdapterRegistry:
    specs: tuple[TopologyBetaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: TopologyBetaFrontierOperation | str) -> TopologyBetaFrontierAdapterSpec:
        value = TopologyBetaFrontierOperation(str(operation))
        for spec in self.specs:
            if spec.operation is value:
                return spec
        raise KeyError(value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _result(
    record: TopologyBetaFrontierRecord,
    primitive_state: str,
    state: str | None = None,
    *,
    issue_codes: tuple[str, ...] = (),
    measurements: dict[str, Any] | None = None,
    evidence_ids: tuple[str, ...] = (),
) -> TopologyBetaFrontierAdapterResult:
    value = state or primitive_state
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "primitive_state": primitive_state,
        "state": value,
        "issues": issue_codes,
        "measurements": measurements or {},
        "evidence_ids": evidence_ids,
    }
    return TopologyBetaFrontierAdapterResult(
        record.record_id,
        record.operation,
        value,
        primitive_state,
        issue_codes,
        measurements or {},
        record.source_ids,
        evidence_ids,
        content_hash(body),
    )


def _loop_stripe(record: TopologyBetaFrontierRecord) -> TopologyBetaFrontierAdapterResult:
    payload = record.payload
    batch = LoopStripeAdapter().parse_text(
        json.dumps({"features": payload.get("features", [])}),
        source_id=record.source_ids[0],
        source_version="loop-v4",
        input_format="json",
        coordinate_system="bed",
    )
    issues = [item.code for item in batch.issues]
    if not batch.observations:
        return _result(record, TopologyState.ABSTAINED.value, issue_codes=tuple(dict.fromkeys(issues or ["no_loop_stripe_observations"])), measurements={"observation_count": 0, "parser_issue_count": len(batch.issues)})
    if any(item.context_key != TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY for item in batch.observations) or record.context_key != TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY:
        return _result(record, TopologyState.OUT_OF_DOMAIN.value, issue_codes=tuple(dict.fromkeys((*issues, "context_mismatch"))), measurements={"observation_count": len(batch.observations), "parser_issue_count": len(batch.issues), "feature_kinds": sorted({item.feature_kind.value for item in batch.observations})}, evidence_ids=tuple(item.feature_id for item in batch.observations))
    metadata_missing = any(item.resolution is None or item.caller is None for item in batch.observations)
    signals = tuple(item.signal for item in batch.observations)
    disagreement = len(signals) > 1 and max(signals) - min(signals) > 3.0
    if disagreement:
        state = TopologyState.AMBIGUOUS.value
        issues.append("replicate_disagreement")
    elif metadata_missing:
        state = TopologyState.PARTIAL.value
        issues.append("missing_loop_metadata")
    else:
        state = TopologyState.SUPPORTED.value
    return _result(record, TopologyState.SUPPORTED.value, state, issue_codes=tuple(dict.fromkeys(issues)), measurements={"observation_count": len(batch.observations), "parser_issue_count": len(batch.issues), "feature_kinds": sorted({item.feature_kind.value for item in batch.observations}), "signals": signals, "resolutions": sorted({item.resolution for item in batch.observations if item.resolution is not None}), "callers": sorted({item.caller for item in batch.observations if item.caller}), "source_versions": sorted({item.source_version for item in batch.observations})}, evidence_ids=tuple(item.feature_id for item in batch.observations))


def _promoter_capture(record: TopologyBetaFrontierRecord) -> TopologyBetaFrontierAdapterResult:
    payload = record.payload
    batch = PromoterCaptureContactAdapter().parse_text(
        json.dumps({"contacts": payload.get("contacts", [])}),
        source_id=record.source_ids[0],
        source_version="pc-v3",
        input_format="json",
        coordinate_system="one_based",
    )
    issues = [item.code for item in batch.issues]
    if not batch.contacts:
        return _result(record, TopologyState.ABSTAINED.value, issue_codes=tuple(dict.fromkeys(issues or ["no_promoter_capture_contacts"])), measurements={"contact_count": 0, "parser_issue_count": len(batch.issues)})
    if any(item.context_key != TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY for item in batch.contacts) or record.context_key != TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY:
        return _result(record, TopologyState.OUT_OF_DOMAIN.value, issue_codes=tuple(dict.fromkeys((*issues, "context_mismatch"))), measurements={"contact_count": len(batch.contacts), "parser_issue_count": len(batch.issues), "promoters": sorted({item.promoter_id for item in batch.contacts}), "targets": sorted({item.target_element_id for item in batch.contacts})}, evidence_ids=tuple(item.contact_id for item in batch.contacts))
    missing_bait = any(item.bait_id is None for item in batch.contacts)
    signals = tuple(item.signal for item in batch.contacts)
    disagreement = len(signals) > 1 and max(signals) - min(signals) > 3.0
    if disagreement:
        state = TopologyState.AMBIGUOUS.value
        issues.append("replicate_disagreement")
    elif missing_bait:
        state = TopologyState.PARTIAL.value
        issues.append("missing_bait_id")
    else:
        state = TopologyState.SUPPORTED.value
    return _result(record, TopologyState.SUPPORTED.value, state, issue_codes=tuple(dict.fromkeys(issues)), measurements={"contact_count": len(batch.contacts), "parser_issue_count": len(batch.issues), "promoters": sorted({item.promoter_id for item in batch.contacts}), "targets": sorted({item.target_element_id for item in batch.contacts}), "signals": signals, "bait_ids": sorted({item.bait_id for item in batch.contacts if item.bait_id}), "source_versions": sorted({item.source_version for item in batch.contacts})}, evidence_ids=tuple(item.contact_id for item in batch.contacts))


def _enhancer_promoter(record: TopologyBetaFrontierRecord) -> TopologyBetaFrontierAdapterResult:
    payload = record.payload
    observations = payload.get("observations", ())
    score = EnhancerPromoterContactScorer().score(observations, enhancer_id=str(payload.get("enhancer_id", "enh-1")), promoter_id=str(payload.get("promoter_id", "GENE1")), context_key=TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY, signal_scale=10.0, ambiguity_tolerance=3.0)
    issues: list[str] = []
    if score.state is TopologyState.ABSENT:
        issues.append("no_contact_observations")
    elif score.state is TopologyState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    elif score.state is TopologyState.AMBIGUOUS:
        issues.append("replicate_disagreement")
    return _result(record, score.state.value, issue_codes=tuple(issues), measurements={"observation_count": len(score.observations), "median_signal": score.median_signal, "signal_spread": score.signal_spread, "normalized_contact_score": score.normalized_contact_score, "source_ids": score.source_ids, "source_versions": score.source_versions}, evidence_ids=tuple(item.contact_id for item in score.observations))


def _activity_by_contact(record: TopologyBetaFrontierRecord) -> TopologyBetaFrontierAdapterResult:
    payload = record.payload
    result = ActivityByContactScorer().score(payload.get("contacts", ()), payload.get("activities", ()), enhancer_id=str(payload.get("enhancer_id", "enh-1")), promoter_id=str(payload.get("promoter_id", "GENE1")), context_key=TOPOLOGY_BETA_FRONTIER_CONTEXT_KEY, model_id=str(payload.get("model_id", "abc-aggregate")), model_version=str(payload.get("model_version", "2026.08")), contact_scale=10.0, activity_scale=1.0, ambiguity_tolerance=0.3)
    issues: list[str] = []
    if result.state is TopologyState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    elif result.state is TopologyState.ABSTAINED and not result.activity_observations:
        issues.append("missing_activity")
    elif result.state is TopologyState.AMBIGUOUS:
        issues.append("component_disagreement")
    evidence_ids = tuple(item.contact_id for item in result.contact_observations) + tuple(item.raw_hash for item in result.activity_observations)
    return _result(record, result.state.value, issue_codes=tuple(issues), measurements={"contact_count": len(result.contact_observations), "activity_count": len(result.activity_observations), "contact_component": result.contact_component, "activity_component": result.activity_component, "activity_by_contact_score": result.activity_by_contact_score, "contact_state": result.contact_state.value, "activity_state": result.activity_state.value, "model_id": result.model_id, "model_version": result.model_version, "source_ids": result.source_ids, "source_versions": result.source_versions}, evidence_ids=evidence_ids)


def execute_topology_beta_frontier_record(record: TopologyBetaFrontierRecord) -> TopologyBetaFrontierAdapterResult:
    if record.operation is TopologyBetaFrontierOperation.LOOP_STRIPE:
        return _loop_stripe(record)
    if record.operation is TopologyBetaFrontierOperation.PROMOTER_CAPTURE:
        return _promoter_capture(record)
    if record.operation is TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT:
        return _enhancer_promoter(record)
    if record.operation is TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT:
        return _activity_by_contact(record)
    raise ValueError(f"unsupported topology beta frontier operation: {record.operation}")


def build_topology_beta_frontier_adapters() -> TopologyBetaFrontierAdapterRegistry:
    specs = (
        TopologyBetaFrontierAdapterSpec(TopologyBetaFrontierOperation.LOOP_STRIPE, "d09-c05-loop-stripe", "LoopStripeAdapter", ("features", "context_key", "source_version"), ("two_anchor_coordinates", "feature_kind", "signal", "resolution", "caller"), ("supported", "partial", "ambiguous", "out_of_domain"), "External feature schema conformance and caller calibration remain separate."),
        TopologyBetaFrontierAdapterSpec(TopologyBetaFrontierOperation.PROMOTER_CAPTURE, "d09-c06-promoter-capture", "PromoterCaptureContactAdapter", ("contacts", "promoter_id", "target_element_id", "bait_id"), ("promoter_identity", "target_identity", "signal", "bait_id", "context_key"), ("supported", "partial", "ambiguous", "out_of_domain"), "Bait design and cross-assay calibration remain separate."),
        TopologyBetaFrontierAdapterSpec(TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, "d09-c07-enhancer-promoter", "EnhancerPromoterContactScorer", ("observations", "enhancer_id", "promoter_id", "context_key"), ("median_signal", "signal_spread", "normalized_contact_score", "source_versions"), ("supported", "ambiguous", "absent", "out_of_domain"), "The bounded score is descriptive and is not a probability."),
        TopologyBetaFrontierAdapterSpec(TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, "d09-c08-activity-by-contact", "ActivityByContactScorer", ("contacts", "activities", "model_id", "model_version"), ("contact_component", "activity_component", "combined_score", "missingness"), ("supported", "ambiguous", "abstained", "out_of_domain"), "Model calibration and transport evaluation remain separate."),
    )
    return TopologyBetaFrontierAdapterRegistry(specs, len(specs) == 4)


__all__ = [
    "TopologyBetaFrontierAdapterRegistry",
    "TopologyBetaFrontierAdapterResult",
    "TopologyBetaFrontierAdapterSpec",
    "build_topology_beta_frontier_adapters",
    "execute_topology_beta_frontier_record",
]
