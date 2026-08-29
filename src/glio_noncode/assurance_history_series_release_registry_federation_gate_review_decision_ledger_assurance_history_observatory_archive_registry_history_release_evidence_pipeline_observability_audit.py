"""Independent assurance checks for release-evidence observability.

The observability builder creates a deterministic event and metric projection.
This companion deliberately audits the public mapping instead of relying only
on the builder's typed validation.  It returns every fixed check, including
failed checks for damaged input, so an operator can diagnose a handoff without
receiving paths, timestamps, process identifiers, or attribution metadata.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability as observability_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observability_model.VERSION + "-audit-v1"
BOUNDARY = observability_model.BOUNDARY + "_audit"
AUDIT_PREFIX = observability_model.OBSERVABILITY_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "source-addresses",
    "event-sequence",
    "stage-projection",
    "transition-linkage",
    "event-addresses",
    "metric-projection",
    "metric-addresses",
    "count-conservation",
    "decision-conservation",
    "mapping-round-trip",
    "content-address",
)
STATES = ("complete", "incomplete")
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = {"pipeline_address", "state", "pipeline_accepted", "events", "metrics", "event_count", "metric_count", "accepted", "content_address"}


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _generic_address(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return pipeline_model._public(value)


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "release evidence observability audit evidence address", prefix)
    except ValidationError:
        return fallback


def _typed(value: Mapping[str, Any]) -> observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None:
    try:
        return observability_model.observability_from_mapping(value)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


class RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck:
    """One independently addressed assertion over an observability mapping."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "release evidence observability audit check ID", 128)
        self.passed = _bool(passed, "release evidence observability audit check passed")
        self.detail = _text(detail, "release evidence observability audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "release evidence observability audit evidence address", 2048)
        self.content_address = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=AUDIT_CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck:
        value = _mapping(value, "release evidence observability audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "release evidence observability audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("release evidence observability audit check content address mismatch")
        return result


class RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    """Complete or incomplete, path-free audit report for observability."""

    def __init__(self, observability_address: str, pipeline_address: str, observability_state: str, pipeline_accepted: bool, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck], content_address: str) -> None:
        self.observability_address = observability_address
        self.pipeline_address = pipeline_address
        self.observability_state = observability_state
        self.pipeline_accepted = pipeline_accepted
        self.state = state
        self.complete = complete
        self.accepted = accepted
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.observability_address, "release evidence observability audit observability address", observability_model.OBSERVABILITY_PREFIX)
        _address(self.pipeline_address, "release evidence observability audit pipeline address", pipeline_model.PIPELINE_PREFIX)
        _text(self.observability_state, "release evidence observability audit observability state", 32)
        _bool(self.pipeline_accepted, "release evidence observability audit pipeline acceptance")
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("release evidence observability audit state does not match completion")
        _bool(self.complete, "release evidence observability audit complete")
        _bool(self.accepted, "release evidence observability audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("release evidence observability audit check set is invalid")
        if any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck) for check in self.checks):
            raise ValidationError("release evidence observability audit checks must be typed")
        _count(self.passed_count, "release evidence observability audit passed count", MAX_CHECKS)
        _count(self.failed_count, "release evidence observability audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("release evidence observability audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("release evidence observability audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability audit content address")
        else:
            _address(self.content_address, "release evidence observability audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("release evidence observability audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"observability_address": self.observability_address, "pipeline_address": self.pipeline_address, "observability_state": self.observability_state, "pipeline_accepted": self.pipeline_accepted, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("observability_address", "pipeline_address", "observability_state", "pipeline_accepted", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
        value = _mapping(value, "release evidence observability audit")
        fields = {"observability_address", "pipeline_address", "observability_state", "pipeline_accepted", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address"}
        _strict(value, fields, "release evidence observability audit")
        missing = fields - set(value)
        if missing:
            raise ValidationError(f"release evidence observability audit is missing fields: {sorted(missing)}")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "release evidence observability audit checks", MAX_CHECKS))
        result = cls(value["observability_address"], value["pipeline_address"], value["observability_state"], value["pipeline_accepted"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("release evidence observability audit derived counts are not conserved")
        return result


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityAudit):
        raise ValidationError("release evidence observability audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck(check_id, passed, detail, evidence)


def _source_addresses(document: Mapping[str, Any]) -> bool:
    try:
        _address(document["pipeline_address"], "pipeline address", pipeline_model.PIPELINE_PREFIX)
        _address(document["content_address"], "observability address", observability_model.OBSERVABILITY_PREFIX)
        events = _sequence(document["events"], "events", observability_model.MAX_EVENTS)
        metrics = _sequence(document["metrics"], "metrics", observability_model.MAX_METRICS)
        for raw in events:
            raw = _mapping(raw, "event")
            _generic_address(raw["input_address"], "event input address")
            _generic_address(raw["output_address"], "event output address")
            _address(raw["content_address"], "event content address", observability_model.EVENT_PREFIX)
        for raw in metrics:
            raw = _mapping(raw, "metric")
            _address(raw["content_address"], "metric content address", observability_model.METRIC_PREFIX)
        return True
    except (ValidationError, KeyError, TypeError, ValueError):
        return False


def _event_sequence(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    return typed is not None and tuple(event.sequence for event in typed.events) == tuple(range(1, observability_model.MAX_EVENTS + 1))


def _stage_projection(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    if typed is None:
        return False
    expected_stages = (*observability_model.query_model.STAGE_IDS, "release")
    expected_types = (*(("stage_evaluated",) * len(observability_model.query_model.STAGE_IDS)), "release_decision")
    return tuple(event.stage for event in typed.events) == expected_stages and tuple(event.event_type for event in typed.events) == expected_types


def _transition_linkage(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    if typed is None:
        return False
    return bool(typed.events) and typed.events[0].input_address == typed.events[0].output_address and all(current.input_address == previous.output_address for previous, current in zip(typed.events, typed.events[1:], strict=False)) and typed.events[-1].output_address == typed.pipeline_address


def _event_addresses(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    return typed is not None and all(observability_model.address_event(event) == event.content_address for event in typed.events)


def _metric_projection(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    if typed is None:
        return False
    if tuple(metric.name for metric in typed.metrics) != observability_model.METRIC_NAMES:
        return False
    expected = (
        ("snapshot-count", "coverage", "count"),
        ("stage-count", "coverage", "count"),
        ("accepted-stage-count", "coverage", "count"),
        ("rejected-stage-count", "coverage", "count"),
        ("decision-count", "decision", "count"),
        ("accepted-decision-count", "decision", "count"),
        ("package-file-count", "handoff", "count"),
        ("event-count", "observability", "count"),
        ("query-view-count", "observability", "count"),
        ("pipeline-accepted", "decision", "boolean"),
        ("release-ready", "decision", "boolean"),
        ("public-forbidden-key-count", "public", "count"),
    )
    for metric, (metric_id, plane, unit) in zip(typed.metrics, expected, strict=True):
        if (metric.metric_id, metric.plane, metric.unit) != (metric_id, plane, unit):
            return False
    values = {metric.name: metric.value for metric in typed.metrics}
    accepted_stages = sum(event.accepted for event in typed.events[:-1])
    integer_counts = ("snapshot_count", "stage_count", "accepted_stage_count", "rejected_stage_count", "decision_count", "accepted_decision_count", "package_file_count", "event_count", "query_view_count", "pipeline_accepted", "release_ready", "public_forbidden_key_count")
    if any(isinstance(values[name], bool) or not isinstance(values[name], int) for name in integer_counts):
        return False
    return (
        0 <= values["snapshot_count"] <= history_model.MAX_SNAPSHOTS
        and values["stage_count"] == len(observability_model.query_model.STAGE_IDS)
        and values["accepted_stage_count"] == accepted_stages
        and values["rejected_stage_count"] == values["stage_count"] - accepted_stages
        and values["decision_count"] == 3
        and 0 <= values["accepted_decision_count"] <= values["decision_count"]
        and values["package_file_count"] == pipeline_model.PACKAGE_FILE_COUNT
        and values["event_count"] == observability_model.MAX_EVENTS
        and values["query_view_count"] == len(observability_model.query_model.RESOURCES) - 1
        and values["pipeline_accepted"] == int(typed.pipeline_accepted)
        and values["release_ready"] == int(typed.pipeline_accepted)
        and values["public_forbidden_key_count"] == 0
    )


def _metric_addresses(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    return typed is not None and all(observability_model.address_metric(metric) == metric.content_address for metric in typed.metrics)


def _count_conservation(document: Mapping[str, Any], typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    return typed is not None and document.get("event_count") == len(typed.events) == observability_model.MAX_EVENTS and document.get("metric_count") == len(typed.metrics) == observability_model.MAX_METRICS


def _decision_conservation(typed: observability_model.RegistryHistoryReleaseEvidencePipelineObservability | None) -> bool:
    if typed is None:
        return False
    final = typed.events[-1]
    return typed.pipeline_accepted == (typed.state == "ready") and final.event_type == "release_decision" and final.stage == "release" and final.state == typed.state and final.accepted == typed.pipeline_accepted and typed.accepted


def _audit_mapping(document: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    fallback_observability = observability_model.OBSERVABILITY_PREFIX + ":unresolved"
    fallback_pipeline = pipeline_model.PIPELINE_PREFIX + ":unresolved"
    observability_address = _safe_address(document.get("content_address"), observability_model.OBSERVABILITY_PREFIX, fallback_observability)
    pipeline_address = _safe_address(document.get("pipeline_address"), pipeline_model.PIPELINE_PREFIX, fallback_pipeline)
    typed = _typed(document)
    if typed is not None:
        observability_address = typed.content_address
        pipeline_address = typed.pipeline_address
    exact_fields = set(document) == EXPECTED_FIELDS
    public_boundary = _public(document)
    source_addresses = _source_addresses(document)
    event_sequence = _event_sequence(typed)
    stage_projection = _stage_projection(typed)
    transition_linkage = _transition_linkage(typed)
    event_addresses = _event_addresses(typed)
    metric_projection = _metric_projection(typed)
    metric_addresses = _metric_addresses(typed)
    count_conservation = _count_conservation(document, typed)
    decision_conservation = _decision_conservation(typed)
    mapping_round_trip = False
    content_address = False
    if typed is not None:
        try:
            mapping_round_trip = observability_model.observability_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
            content_address = observability_model.address_observability(typed) == typed.content_address
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip = False
            content_address = False
    checks = (
        _check("exact-fields", exact_fields, "observability document contains exactly the declared public fields", observability_address),
        _check("public-boundary", public_boundary, "observability document contains no private, path, or attribution metadata", observability_address),
        _check("source-addresses", source_addresses, "pipeline, event, metric, and projection addresses use public namespaces", observability_address),
        _check("event-sequence", event_sequence, "events use the complete ordered sequence without gaps", observability_address),
        _check("stage-projection", stage_projection, "event stages and event types conserve the pipeline stage projection", observability_address),
        _check("transition-linkage", transition_linkage, "each event input retains the previous output address", observability_address),
        _check("event-addresses", event_addresses, "every event content address reproduces from its public fields", observability_address),
        _check("metric-projection", metric_projection, "metric identities, planes, units, and denominator values are conserved", observability_address),
        _check("metric-addresses", metric_addresses, "every metric content address reproduces from its public fields", observability_address),
        _check("count-conservation", count_conservation, "event and metric counts match the fixed projection cardinalities", observability_address),
        _check("decision-conservation", decision_conservation, "the final release decision conserves pipeline acceptance and state", observability_address),
        _check("mapping-round-trip", mapping_round_trip, "the typed public mapping rehydrates without projection drift", observability_address),
        _check("content-address", content_address, "the observability content address reproduces from its public projection", observability_address),
    )
    complete = all(check.passed for check in checks)
    body = {"observability_address": observability_address, "pipeline_address": pipeline_address, "observability_state": typed.state if typed is not None else "held", "pipeline_accepted": typed.pipeline_accepted if typed is not None else False, "state": "complete" if complete else "incomplete", "complete": complete, "accepted": complete, "checks": checks}
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityAudit(**body, content_address="pending:audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityAudit(**body, content_address=address_audit(provisional))


def audit_observability(value: observability_model.RegistryHistoryReleaseEvidencePipelineObservability) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    if not isinstance(value, observability_model.RegistryHistoryReleaseEvidencePipelineObservability):
        raise ValidationError("release evidence observability audit requires a typed projection")
    observability_model.verify_observability(value)
    return _audit_mapping(value.to_dict())


def audit_pipeline(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    pipeline_model.verify_pipeline(value)
    return audit_observability(observability_model.build_observability(value))


def audit_pipeline_directory(source: str, *, package_destination: str | None = None, overwrite: bool = False) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    return audit_pipeline(pipeline_model.build_pipeline(source, package_destination, overwrite=overwrite))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    return _audit_mapping(_mapping(value, "release evidence observability audit input"))


def audit_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    """Rehydrate an already-produced audit report and verify its addresses."""

    return RegistryHistoryReleaseEvidencePipelineObservabilityAudit.from_mapping(_mapping(value, "release evidence observability audit result"))


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityAudit):
        raise ValidationError("release evidence observability audit verification requires a typed audit")
    value._validate()
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityAudit) -> str:
    verify_audit(value)
    lines = ["# Assurance History Observatory Release Evidence Observability Audit", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Observability: `{value.observability_address}`", f"- Pipeline: `{value.pipeline_address}`", f"- Observability state: `{value.observability_state}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"observability_address": {"type": "string", "pattern": "^" + observability_model.OBSERVABILITY_PREFIX + ":"}, "pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "observability_state": {"type": "string", "enum": list(pipeline_model.STATES)}, "pipeline_accepted": {"type": "boolean"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "prefixes": {"observability": observability_model.OBSERVABILITY_PREFIX, "audit": AUDIT_PREFIX, "check": AUDIT_CHECK_PREFIX}, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_events": observability_model.MAX_EVENTS, "max_metrics": observability_model.MAX_METRICS, "max_snapshots": history_model.MAX_SNAPSHOTS}, "features": ("independent public mapping audit", "fixed observability check set", "event sequence and stage conservation", "address-linked transition validation", "metric identity and denominator conservation", "pipeline decision conservation", "incomplete tamper diagnostics", "content-address replay", "downloaded-history audit", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "EXPECTED_FIELDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityAudit",
    "RegistryHistoryReleaseEvidencePipelineObservabilityAuditCheck",
    "address_audit",
    "audit_from_mapping",
    "audit_json",
    "audit_observability",
    "audit_pipeline",
    "audit_pipeline_directory",
    "audit_result_from_mapping",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
