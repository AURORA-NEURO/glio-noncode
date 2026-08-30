"""Deterministic, value-free remediation actions for compatibility findings."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation"
REMEDIATION_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation"
ACTION_PREFIX = REMEDIATION_PREFIX + "-action"
PLAN_PREFIX = REMEDIATION_PREFIX + "-plan"
DEFAULT_PLAN_ID = PLAN_PREFIX
ACTION_KINDS = ("none", "review", "repair", "migrate", "restore", "investigate")
PRIORITIES = ("low", "medium", "high", "critical")
STATES = ("clear", "review", "blocked")
DECISIONS = ("close", "hold", "block")
ACTION_FIELDS = (
    "ordinal",
    "resource",
    "identity",
    "change",
    "outcome",
    "reason_codes",
    "action",
    "priority",
    "required",
    "evidence_addresses",
    "detail",
    "content_address",
)
PLAN_FIELDS = (
    "plan_id",
    "version",
    "boundary",
    "gate_id",
    "gate_address",
    "gate",
    "actions",
    "action_count",
    "none_count",
    "review_count",
    "repair_count",
    "migrate_count",
    "restore_count",
    "investigate_count",
    "required_action_count",
    "state",
    "decision",
    "accepted",
    "content_address",
)
MAX_ACTIONS = compatibility_model.MAX_FINDINGS


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _ordered_labels(value: Any, field: str, allowed: Sequence[str], *, empty: bool = False) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels and not empty:
        raise ValidationError(f"{field} must not be empty")
    if len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
        raise ValidationError(f"{field} contains unsupported or unordered labels")
    return labels


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def address_action(value: DownloadedDataProfileContractCompatibilityRemediationAction) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationAction):
        raise ValidationError("remediation action address requires a typed action")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ACTION_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationAction:
    """One deterministic action over one compatibility finding."""

    FIELDS = ACTION_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, outcome: str, reason_codes: Sequence[str], action: str, priority: str, required: bool, evidence_addresses: Sequence[str], detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "remediation action ordinal", MAX_ACTIONS, positive=True)
        self.resource = _label(resource, "remediation action resource")
        if self.resource not in compatibility_model.diff_model.RESOURCES:
            raise ValidationError("remediation action resource is unsupported")
        self.identity = _text(identity, "remediation action identity", 4096)
        self.change = _label(change, "remediation action change")
        if self.change not in compatibility_model.diff_model.CHANGES:
            raise ValidationError("remediation action change is unsupported")
        self.outcome = _label(outcome, "remediation action outcome")
        if self.outcome not in compatibility_model.OUTCOMES:
            raise ValidationError("remediation action outcome is unsupported")
        self.reason_codes = _ordered_labels(reason_codes, "remediation action reason codes", compatibility_model.REASON_CODES, empty=True)
        self.action = _label(action, "remediation action kind")
        if self.action not in ACTION_KINDS:
            raise ValidationError("remediation action kind is unsupported")
        self.priority = _label(priority, "remediation action priority")
        if self.priority not in PRIORITIES:
            raise ValidationError("remediation action priority is unsupported")
        self.required = _bool(required, "remediation action requiredness")
        self.evidence_addresses = tuple(sorted({_address(item, "remediation action evidence address") for item in _sequence(evidence_addresses, "remediation action evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("remediation actions require evidence")
        self.detail = _text(detail, "remediation action detail", 1024)
        self.content_address = _address(content_address, "remediation action address", ACTION_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.outcome == "safe" and (self.action != "none" or self.priority != "low" or self.required):
            raise ValidationError("safe remediation actions must be low-priority no-ops")
        if self.outcome != "safe" and (self.action == "none" or not self.required):
            raise ValidationError("review and breaking findings require action")
        if self.outcome == "breaking" and self.priority != "critical":
            raise ValidationError("breaking remediation actions must be critical")
        if self.outcome == "review" and self.priority not in {"medium", "high"}:
            raise ValidationError("review remediation actions must be medium or high priority")
        if not _public(self.to_dict()):
            raise ValidationError("remediation action crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_action(self) != self.content_address:
            raise ValidationError("remediation action address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationAction:
        value = _mapping(value, "remediation action")
        _strict(value, set(cls.FIELDS), "remediation action")
        return cls(*(value[field] for field in cls.FIELDS))


def _action_spec(finding: compatibility_model.DownloadedDataProfileContractCompatibilityFinding) -> tuple[str, str, bool, str]:
    if finding.outcome == "safe":
        return "none", "low", False, "No structural remediation is required."
    reasons = set(finding.reason_codes)
    if "member_removed" in reasons:
        return "restore", "critical", True, "Restore the removed structural member or update the consumer contract."
    if "field_added_required" in reasons or "field_removed_required" in reasons or "field_requiredness_changed" in reasons:
        return "migrate", "critical" if finding.outcome == "breaking" else "high", True, "Define and verify an explicit schema migration before promotion."
    if "field_type_changed" in reasons or "member_shape_changed" in reasons:
        return "repair", "critical", True, "Repair the contract or producer shape before promotion."
    if "resource_not_allowed" in reasons or "type_distribution_changed" in reasons:
        return "investigate", "critical" if finding.outcome == "breaking" else "medium", True, "Investigate the structural evidence and record a bounded disposition."
    return "review", "high" if finding.outcome == "review" else "critical", True, "Review the structural change and confirm downstream expectations."


def _action(finding: compatibility_model.DownloadedDataProfileContractCompatibilityFinding, ordinal: int, gate_address: str) -> DownloadedDataProfileContractCompatibilityRemediationAction:
    action, priority, required, detail = _action_spec(finding)
    reasons = tuple(sorted(set(finding.reason_codes), key=compatibility_model.REASON_CODES.index))
    body = {"ordinal": ordinal, "resource": finding.resource, "identity": finding.identity, "change": finding.change, "outcome": finding.outcome, "reason_codes": reasons, "action": action, "priority": priority, "required": required, "evidence_addresses": (gate_address, finding.diff_item_address, finding.content_address), "detail": detail, "content_address": ACTION_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationAction(**body)
    return DownloadedDataProfileContractCompatibilityRemediationAction(**(body | {"content_address": address_action(provisional)}))


class DownloadedDataProfileContractCompatibilityRemediationPlan:
    """Complete action plan for one value-free compatibility gate."""

    FIELDS = PLAN_FIELDS

    def __init__(self, plan_id: str, version: str, boundary: str, gate_id: str, gate_address: str, gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate | Mapping[str, Any], actions: Sequence[DownloadedDataProfileContractCompatibilityRemediationAction | Mapping[str, Any]], action_count: int, none_count: int, review_count: int, repair_count: int, migrate_count: int, restore_count: int, investigate_count: int, required_action_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.plan_id = _label(plan_id, "remediation plan ID")
        self.version = _text(version, "remediation plan version")
        self.boundary = _text(boundary, "remediation plan boundary", 512)
        self.gate_id = _label(gate_id, "remediation plan gate ID")
        self.gate_address = _address(gate_address, "remediation plan gate address", compatibility_model.GATE_PREFIX)
        self.gate = gate if isinstance(gate, compatibility_model.DownloadedDataProfileContractCompatibilityGate) else compatibility_model.compatibility_from_mapping(gate)
        self.actions = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationAction) else DownloadedDataProfileContractCompatibilityRemediationAction.from_mapping(item) for item in _sequence(actions, "remediation actions", MAX_ACTIONS))
        self.action_count = _count(action_count, "remediation action count", MAX_ACTIONS)
        self.none_count = _count(none_count, "remediation no-op count", MAX_ACTIONS)
        self.review_count = _count(review_count, "remediation review count", MAX_ACTIONS)
        self.repair_count = _count(repair_count, "remediation repair count", MAX_ACTIONS)
        self.migrate_count = _count(migrate_count, "remediation migration count", MAX_ACTIONS)
        self.restore_count = _count(restore_count, "remediation restore count", MAX_ACTIONS)
        self.investigate_count = _count(investigate_count, "remediation investigation count", MAX_ACTIONS)
        self.required_action_count = _count(required_action_count, "remediation required action count", MAX_ACTIONS)
        self.state = _label(state, "remediation plan state")
        if self.state not in STATES:
            raise ValidationError("remediation plan state is unsupported")
        self.decision = _label(decision, "remediation plan decision")
        if self.decision not in DECISIONS:
            raise ValidationError("remediation plan decision is unsupported")
        self.accepted = _bool(accepted, "remediation plan acceptance")
        self.content_address = _address(content_address, "remediation plan address", PLAN_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("remediation plan version or boundary is not current")
        if self.gate_id != self.gate.gate_id or self.gate_address != self.gate.content_address:
            raise ValidationError("remediation plan gate linkage does not replay")
        if len(self.actions) != self.action_count or tuple(item.ordinal for item in self.actions) != tuple(range(1, self.action_count + 1)):
            raise ValidationError("remediation action order is not conserved")
        counts = tuple(sum(item.action == action for item in self.actions) for action in ACTION_KINDS)
        if counts != (self.none_count, self.review_count, self.repair_count, self.migrate_count, self.restore_count, self.investigate_count):
            raise ValidationError("remediation action counts do not replay")
        if self.required_action_count != sum(item.required for item in self.actions) or self.action_count != sum(counts):
            raise ValidationError("remediation requiredness does not replay")
        expected_state = "blocked" if any(item.outcome == "breaking" for item in self.actions) else "review" if self.required_action_count else "clear"
        expected_decision = {"clear": "close", "review": "hold", "blocked": "block"}[expected_state]
        if self.state != expected_state or self.decision != expected_decision or self.accepted != (expected_state == "clear"):
            raise ValidationError("remediation plan disposition does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation plan crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_plan(self) != self.content_address:
            raise ValidationError("remediation plan address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_id": self.plan_id, "version": self.version, "boundary": self.boundary, "gate_id": self.gate_id, "gate_address": self.gate_address, "gate": self.gate.to_dict(), "actions": tuple(item.to_dict() for item in self.actions), "action_count": self.action_count, "none_count": self.none_count, "review_count": self.review_count, "repair_count": self.repair_count, "migrate_count": self.migrate_count, "restore_count": self.restore_count, "investigate_count": self.investigate_count, "required_action_count": self.required_action_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"gate", "actions"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationPlan:
        value = _mapping(value, "remediation plan")
        _strict(value, set(cls.FIELDS), "remediation plan")
        return cls(*(value[field] for field in cls.FIELDS))


def address_plan(value: DownloadedDataProfileContractCompatibilityRemediationPlan) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationPlan):
        raise ValidationError("remediation plan address requires a typed plan")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PLAN_PREFIX)


def build_plan(gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate, *, plan_id: str = DEFAULT_PLAN_ID) -> DownloadedDataProfileContractCompatibilityRemediationPlan:
    if not isinstance(gate, compatibility_model.DownloadedDataProfileContractCompatibilityGate):
        raise ValidationError("remediation plan requires a typed compatibility gate")
    actions = tuple(_action(item, ordinal, gate.content_address) for ordinal, item in enumerate(gate.findings, 1))
    counts = tuple(sum(item.action == action for item in actions) for action in ACTION_KINDS)
    body = {"plan_id": plan_id, "version": VERSION, "boundary": BOUNDARY, "gate_id": gate.gate_id, "gate_address": gate.content_address, "gate": gate, "actions": actions, "action_count": len(actions), "none_count": counts[0], "review_count": counts[1], "repair_count": counts[2], "migrate_count": counts[3], "restore_count": counts[4], "investigate_count": counts[5], "required_action_count": sum(item.required for item in actions)}
    expected_state = "blocked" if any(item.outcome == "breaking" for item in actions) else "review" if body["required_action_count"] else "clear"
    provisional = DownloadedDataProfileContractCompatibilityRemediationPlan(**body, state=expected_state, decision={"clear": "close", "review": "hold", "blocked": "block"}[expected_state], accepted=expected_state == "clear", content_address=PLAN_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationPlan(**body, state=provisional.state, decision=provisional.decision, accepted=provisional.accepted, content_address=address_plan(provisional))


def plan_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationPlan:
    return DownloadedDataProfileContractCompatibilityRemediationPlan.from_mapping(value)


def remediation_json(value: DownloadedDataProfileContractCompatibilityRemediationPlan) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationPlan.from_mapping(value.to_dict()).to_dict())


def remediation_csv(value: DownloadedDataProfileContractCompatibilityRemediationPlan) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationPlan.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ACTION_FIELDS)
    writer.writerows(tuple(";".join(item.reason_codes) if field == "reason_codes" else ";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in ACTION_FIELDS) for item in value.actions)
    return stream.getvalue()


def render_remediation_markdown(value: DownloadedDataProfileContractCompatibilityRemediationPlan) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationPlan.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation", "", f"- Plan: `{value.plan_id}`", f"- Gate: `{value.gate_address}`", f"- Actions: `{value.action_count}`", f"- Required: `{value.required_action_count}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | outcome | action | priority | required |", "| ---: | --- | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.identity}` | `{item.outcome}` | `{item.action}` | `{item.priority}` | `{item.required}` |" for item in value.actions)
    return "\n".join(lines) + "\n"


def action_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation action", "type": "object", "additionalProperties": False, "required": list(ACTION_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(compatibility_model.diff_model.RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": list(compatibility_model.diff_model.CHANGES)}, "outcome": {"enum": list(compatibility_model.OUTCOMES)}, "reason_codes": {"type": "array", "items": {"enum": list(compatibility_model.REASON_CODES)}}, "action": {"enum": list(ACTION_KINDS)}, "priority": {"enum": list(PRIORITIES)}, "required": {"type": "boolean"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def plan_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation plan", "type": "object", "additionalProperties": False, "required": list(PLAN_FIELDS), "properties": {"plan_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "gate": compatibility_model.compatibility_schema(), "actions": {"type": "array", "items": action_schema(), "maxItems": MAX_ACTIONS}, "action_count": {"type": "integer", "minimum": 0}, "none_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "repair_count": {"type": "integer", "minimum": 0}, "migrate_count": {"type": "integer", "minimum": 0}, "restore_count": {"type": "integer", "minimum": 0}, "investigate_count": {"type": "integer", "minimum": 0}, "required_action_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "states": STATES, "decisions": DECISIONS, "actions": ACTION_KINDS, "priorities": PRIORITIES, "operations": ("build_plan", "plan_from_mapping", "remediation_json", "remediation_csv", "render_remediation_markdown"), "limits": {"max_actions": MAX_ACTIONS}}


__all__ = ["ACTION_FIELDS", "ACTION_KINDS", "ACTION_PREFIX", "BOUNDARY", "DEFAULT_PLAN_ID", "DECISIONS", "MAX_ACTIONS", "PLAN_FIELDS", "PLAN_PREFIX", "PRIORITIES", "REMEDIATION_PREFIX", "STATES", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationAction", "DownloadedDataProfileContractCompatibilityRemediationPlan", "action_schema", "address_action", "address_plan", "build_plan", "capabilities", "plan_from_mapping", "plan_schema", "remediation_csv", "remediation_json", "render_remediation_markdown"]
