"""Typed remediation plans derived from consensus actions.

Remediation is an operator-facing projection.  It describes what must be
reviewed or repaired, but it never performs the action and never discards
source evidence.  A plan is safe to publish because it contains labels,
addresses, counts, and bounded instructions only.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = consensus_model.VERSION + "-remediation-v1"
BOUNDARY = consensus_model.BOUNDARY + "_remediation"
REMEDIATION_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-remediation"
STEP_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-remediation-step"
DEFAULT_REMEDIATION_ID = "consensus-remediation"
MAX_STEPS = consensus_model.MAX_ACTIONS
STATUSES = ("required", "recommended")
CHECK_IDS = ("exact-fields", "public-boundary", "consensus-link", "step-conservation", "action-conservation", "status-conservation", "blocking-conservation", "readiness-conservation", "address-conservation", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusRemediationStep:
    FIELDS = ("ordinal", "action_id", "package_id", "kind", "severity", "status", "instruction", "peer_ids", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, action_id: str, package_id: str, kind: str, severity: str, status: str, instruction: str, peer_ids: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "remediation step ordinal", MAX_STEPS, positive=True)
        self.action_id = _label(action_id, "remediation action ID")
        self.package_id = _label(package_id, "remediation package ID")
        self.kind = _label(kind, "remediation kind")
        if severity not in consensus_model.SEVERITIES or status not in STATUSES:
            raise ValidationError("remediation severity or status is unsupported")
        self.severity, self.status = severity, status
        self.instruction = _text(instruction, "remediation instruction", 4096, required=True)
        self.peer_ids = _labels(peer_ids, "remediation peer IDs", consensus_model.MAX_PEERS)
        self.evidence_addresses = _addresses(evidence_addresses, "remediation evidence addresses", 32)
        if not self.evidence_addresses:
            raise ValidationError("remediation evidence is required")
        self.content_address = _address(content_address, "remediation step content address", STEP_PREFIX)
        if not self.content_address.endswith(":pending") and address_step(self) != self.content_address:
            raise ValidationError("remediation step content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation step crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "action_id": self.action_id, "package_id": self.package_id, "kind": self.kind, "severity": self.severity, "status": self.status, "instruction": self.instruction, "peer_ids": self.peer_ids, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationStep:
        value = _mapping(value, "remediation step")
        _strict(value, set(cls.FIELDS), "remediation step")
        return cls(value["ordinal"], value["action_id"], value["package_id"], value["kind"], value["severity"], value["status"], value["instruction"], value["peer_ids"], value["evidence_addresses"], value["content_address"])


def address_step(value: RegistryFederationConsensusRemediationStep) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationStep):
        raise ValidationError("remediation step address requires a typed step")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=STEP_PREFIX)


class RegistryFederationConsensusRemediation:
    FIELDS = ("remediation_id", "consensus_address", "steps", "step_count", "blocking_count", "review_count", "ready", "content_address")

    def __init__(self, remediation_id: str, consensus_address: str, steps: Sequence[RegistryFederationConsensusRemediationStep], step_count: int, blocking_count: int, review_count: int, ready: bool, content_address: str) -> None:
        self.remediation_id = _label(remediation_id, "remediation ID")
        self.consensus_address = _address(consensus_address, "remediation consensus address", consensus_model.CONSENSUS_PREFIX)
        self.steps = tuple(steps)
        self.step_count = _count(step_count, "remediation step count", MAX_STEPS)
        self.blocking_count = _count(blocking_count, "remediation blocking count", self.step_count)
        self.review_count = _count(review_count, "remediation review count", self.step_count)
        self.ready = _bool(ready, "remediation readiness")
        self.content_address = _address(content_address, "remediation content address", REMEDIATION_PREFIX)
        if len(self.steps) != self.step_count or tuple(item.ordinal for item in self.steps) != tuple(range(1, self.step_count + 1)) or self.blocking_count != sum(item.severity == "blocking" for item in self.steps) or self.review_count != sum(item.severity == "review" for item in self.steps) or self.ready != (self.blocking_count == 0):
            raise ValidationError("remediation counters or readiness are not conserved")
        if not self.content_address.endswith(":pending") and address_remediation(self) != self.content_address:
            raise ValidationError("remediation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"remediation_id": self.remediation_id, "consensus_address": self.consensus_address, "steps": tuple(item.to_dict() for item in self.steps), "step_count": self.step_count, "blocking_count": self.blocking_count, "review_count": self.review_count, "ready": self.ready, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "steps"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediation:
        value = _mapping(value, "consensus remediation")
        _strict(value, set(cls.FIELDS), "consensus remediation")
        return cls(value["remediation_id"], value["consensus_address"], tuple(RegistryFederationConsensusRemediationStep.from_mapping(item) for item in value["steps"]), value["step_count"], value["blocking_count"], value["review_count"], value["ready"], value["content_address"])


def address_remediation(value: RegistryFederationConsensusRemediation) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediation):
        raise ValidationError("remediation address requires a typed plan")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REMEDIATION_PREFIX)


def _instruction(kind: str) -> str:
    return {"inspect-divergence": "review every retained address and approve a source-of-truth decision", "replicate-missing": "verify the missing peer and replicate only after the selected address is approved", "hold-package": "keep the package out of promotion until quorum evidence is complete"}.get(kind, "review the consensus action before changing any registry")


def build_remediation(value: consensus_model.RegistryFederationConsensus, *, remediation_id: str = DEFAULT_REMEDIATION_ID) -> RegistryFederationConsensusRemediation:
    value = consensus_model.verify_consensus(value)
    steps: list[RegistryFederationConsensusRemediationStep] = []
    for action in value.actions:
        status = "required" if action.severity == "blocking" else "recommended"
        provisional = RegistryFederationConsensusRemediationStep(len(steps) + 1, action.action_id, action.package_id, action.kind, action.severity, status, _instruction(action.kind), action.peer_ids, action.evidence_addresses, STEP_PREFIX + ":pending")
        steps.append(RegistryFederationConsensusRemediationStep(provisional.ordinal, provisional.action_id, provisional.package_id, provisional.kind, provisional.severity, provisional.status, provisional.instruction, provisional.peer_ids, provisional.evidence_addresses, address_step(provisional)))
    provisional = RegistryFederationConsensusRemediation(remediation_id, value.content_address, tuple(steps), len(steps), sum(item.severity == "blocking" for item in steps), sum(item.severity == "review" for item in steps), not any(item.severity == "blocking" for item in steps), REMEDIATION_PREFIX + ":pending")
    return RegistryFederationConsensusRemediation(provisional.remediation_id, provisional.consensus_address, provisional.steps, provisional.step_count, provisional.blocking_count, provisional.review_count, provisional.ready, address_remediation(provisional))


def remediation_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusRemediation:
    return verify_remediation(RegistryFederationConsensusRemediation.from_mapping(value))


def verify_remediation(value: RegistryFederationConsensusRemediation) -> RegistryFederationConsensusRemediation:
    if not isinstance(value, RegistryFederationConsensusRemediation) or (not value.content_address.endswith(":pending") and address_remediation(value) != value.content_address):
        raise ValidationError("consensus remediation is not valid")
    return value


def remediation_json(value: RegistryFederationConsensusRemediation) -> str:
    return canonical_json(verify_remediation(value).to_dict())


def remediation_csv(value: RegistryFederationConsensusRemediation) -> str:
    value = verify_remediation(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusRemediationStep.FIELDS, lineterminator="\n")
    writer.writeheader()
    for step in value.steps:
        row = step.to_dict()
        row["peer_ids"] = "|".join(step.peer_ids)
        row["evidence_addresses"] = "|".join(step.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_remediation_markdown(value: RegistryFederationConsensusRemediation) -> str:
    value = verify_remediation(value)
    lines = ["# Consensus Remediation Plan", "", f"- Consensus: `{value.consensus_address}`", f"- Ready: `{value.ready}`", f"- Required: `{value.blocking_count}`", f"- Recommended: `{value.review_count}`", "", "| step | action | package | kind | status | instruction |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {step.ordinal} | `{step.action_id}` | `{step.package_id}` | `{step.kind}` | `{step.status}` | {step.instruction} |" for step in value.steps)
    return "\n".join(lines) + "\n"


def step_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationStep.FIELDS), "properties": {"ordinal": {"type": "integer"}, "action_id": {"type": "string"}, "package_id": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string"}, "status": {"type": "string", "enum": list(STATUSES)}, "instruction": {"type": "string"}, "peer_ids": {"type": "array"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + STEP_PREFIX + ":"}}}


def remediation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediation.FIELDS), "properties": {"remediation_id": {"type": "string"}, "consensus_address": {"type": "string"}, "steps": {"type": "array", "items": step_schema()}, "step_count": {"type": "integer"}, "blocking_count": {"type": "integer"}, "review_count": {"type": "integer"}, "ready": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + REMEDIATION_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "remediation_prefix": REMEDIATION_PREFIX, "step_prefix": STEP_PREFIX, "statuses": STATUSES, "check_ids": CHECK_IDS, "features": ("non-mutating action plan", "blocking and recommended separation", "operator-safe bounded instructions", "evidence-linked steps", "JSON CSV and Markdown exports"), "schemas": ("step", "remediation")}


__all__ = ["BOUNDARY", "CHECK_IDS", "DEFAULT_REMEDIATION_ID", "MAX_STEPS", "REMEDIATION_PREFIX", "STATUSES", "STEP_PREFIX", "RegistryFederationConsensusRemediation", "RegistryFederationConsensusRemediationStep", "VERSION", "address_remediation", "address_step", "build_remediation", "capabilities", "remediation_csv", "remediation_from_mapping", "remediation_json", "remediation_schema", "render_remediation_markdown", "step_schema", "verify_remediation"]
