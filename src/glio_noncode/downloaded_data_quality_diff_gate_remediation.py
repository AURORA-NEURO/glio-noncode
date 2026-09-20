"""Value-free remediation plans for downloaded-data quality gate findings.

The release gate answers whether a quality diff may proceed.  This boundary
answers the next operational question without touching the source data: what
bounded, evidence-linked action should a reviewer take for every finding?

Plans are deterministic projections of a gate.  They do not mutate files,
retry ingestion, or silently relax policy.  Every action retains the finding,
gate, and diff-item addresses needed for a later human or external workflow.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation"
PLAN_PREFIX = "glio-noncode-download-quality-diff-gate-remediation"
ACTION_PREFIX = PLAN_PREFIX + "-action"
DEFAULT_PLAN_ID = PLAN_PREFIX
ACTION_KINDS = ("none", "repair", "investigate", "policy_review", "data_review", "accept")
PRIORITIES = ("low", "medium", "high", "critical")
STATES = ("clear", "review", "blocked")
DECISIONS = ("close", "hold", "block")
ACTION_FIELDS = (
    "ordinal", "finding_address", "identity", "change", "direction", "outcome",
    "reason_codes", "action", "priority", "required", "evidence_addresses",
    "detail", "content_address",
)
PLAN_FIELDS = (
    "plan_id", "version", "boundary", "gate_id", "gate_address", "gate",
    "actions", "action_count", "none_count", "repair_count", "investigate_count",
    "policy_review_count", "data_review_count", "accept_count", "required_action_count",
    "critical_action_count", "state", "decision", "accepted", "content_address",
)
MAX_ACTIONS = gate_model.MAX_FINDINGS


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    namespace, digest = value.split(":", 1)
    if not namespace or (digest != "pending" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
        raise ValidationError(f"{field} must be a canonical content address")
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


class DownloadedDataQualityDiffGateRemediationAction:
    """One evidence-linked action generated from one gate finding."""

    FIELDS = ACTION_FIELDS

    def __init__(self, ordinal: int, finding_address: str, identity: str, change: str, direction: str, outcome: str, reason_codes: Sequence[str], action: str, priority: str, required: bool, evidence_addresses: Sequence[str], detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate remediation action ordinal", MAX_ACTIONS, positive=True)
        self.finding_address = _address(finding_address, "quality gate remediation finding address", gate_model.FINDING_PREFIX)
        self.identity = _text(identity, "quality gate remediation identity", 4096)
        self.change = _label(change, "quality gate remediation change")
        if self.change not in gate_model.diff_model.CHANGES:
            raise ValidationError("quality gate remediation change is unsupported")
        self.direction = _label(direction, "quality gate remediation direction")
        if self.direction not in gate_model.diff_model.DIRECTIONS:
            raise ValidationError("quality gate remediation direction is unsupported")
        self.outcome = _label(outcome, "quality gate remediation outcome")
        if self.outcome not in gate_model.OUTCOMES:
            raise ValidationError("quality gate remediation outcome is unsupported")
        self.reason_codes = _ordered_labels(reason_codes, "quality gate remediation reason codes", gate_model.REASON_CODES)
        self.action = _label(action, "quality gate remediation action")
        if self.action not in ACTION_KINDS:
            raise ValidationError("quality gate remediation action is unsupported")
        self.priority = _label(priority, "quality gate remediation priority")
        if self.priority not in PRIORITIES:
            raise ValidationError("quality gate remediation priority is unsupported")
        self.required = _bool(required, "quality gate remediation requiredness")
        self.evidence_addresses = tuple(sorted({_address(item, "quality gate remediation evidence address") for item in _sequence(evidence_addresses, "quality gate remediation evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("quality gate remediation actions require evidence")
        self.detail = _text(detail, "quality gate remediation detail", 1024)
        self.content_address = _address(content_address, "quality gate remediation action address", ACTION_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.outcome == "safe" and (self.action != "none" or self.priority != "low" or self.required):
            raise ValidationError("safe quality gate actions must be low-priority no-ops")
        if self.outcome != "safe" and (self.action == "none" or not self.required):
            raise ValidationError("review and blocked quality findings require action")
        if self.outcome == "blocked" and self.priority != "critical":
            raise ValidationError("blocked quality gate actions must be critical")
        if self.outcome == "review" and self.priority not in {"medium", "high"}:
            raise ValidationError("review quality gate actions must be medium or high priority")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation action crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_action(self) != self.content_address:
            raise ValidationError("quality gate remediation action address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationAction":
        value = _mapping(value, "quality gate remediation action")
        _strict(value, set(cls.FIELDS), "quality gate remediation action")
        return cls(*(value[field] for field in cls.FIELDS))


def address_action(value: DownloadedDataQualityDiffGateRemediationAction) -> str:
    if not isinstance(value, DownloadedDataQualityDiffGateRemediationAction):
        raise ValidationError("quality gate remediation action address requires a typed action")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ACTION_PREFIX)


def _action_spec(finding: gate_model.DownloadedDataQualityDiffGateFinding) -> tuple[str, str, bool, str]:
    if finding.outcome == "safe":
        return "none", "low", False, "No remediation is required for an allowed quality-diff direction."
    reasons = set(finding.reason_codes)
    if finding.outcome == "blocked" and ("regressed" in reasons or "maximum_regressed_exceeded" in reasons):
        return "repair", "critical", True, "Repair the producer or structural quality regression before promotion."
    if "diff_audit_failed" in reasons or "query_audit_failed" in reasons:
        return "investigate", "critical", True, "Investigate the failed assurance receipt before relying on this release decision."
    if "query_truncated" in reasons:
        return "investigate", "high", True, "Complete the bounded evidence query before accepting this disposition."
    if any(reason.startswith("maximum_") for reason in reasons):
        return "policy_review", "critical" if finding.outcome == "blocked" else "high", True, "Review the threshold policy and document a bounded exception or policy change."
    if finding.direction in {"changed", "added", "removed"}:
        return "data_review", "high", True, "Review the structural change against downstream expectations before promotion."
    return "investigate", "critical" if finding.outcome == "blocked" else "high", True, "Investigate the disallowed quality direction and record evidence for disposition."


def _action(finding: gate_model.DownloadedDataQualityDiffGateFinding, ordinal: int, gate_address: str) -> DownloadedDataQualityDiffGateRemediationAction:
    action, priority, required, detail = _action_spec(finding)
    body = {
        "ordinal": ordinal,
        "finding_address": finding.content_address,
        "identity": finding.identity,
        "change": finding.change,
        "direction": finding.direction,
        "outcome": finding.outcome,
        "reason_codes": finding.reason_codes,
        "action": action,
        "priority": priority,
        "required": required,
        "evidence_addresses": (gate_address, finding.diff_item_address, finding.content_address),
        "detail": detail,
        "content_address": ACTION_PREFIX + ":pending",
    }
    provisional = DownloadedDataQualityDiffGateRemediationAction(**body)
    return DownloadedDataQualityDiffGateRemediationAction(**(body | {"content_address": address_action(provisional)}))


class DownloadedDataQualityDiffGateRemediationPlan:
    """Complete deterministic action plan for one quality diff gate."""

    FIELDS = PLAN_FIELDS

    def __init__(self, plan_id: str, version: str, boundary: str, gate_id: str, gate_address: str, gate: gate_model.DownloadedDataQualityDiffGate | Mapping[str, Any], actions: Sequence[DownloadedDataQualityDiffGateRemediationAction | Mapping[str, Any]], action_count: int, none_count: int, repair_count: int, investigate_count: int, policy_review_count: int, data_review_count: int, accept_count: int, required_action_count: int, critical_action_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.plan_id = _label(plan_id, "quality gate remediation plan ID")
        self.version = _text(version, "quality gate remediation plan version")
        self.boundary = _text(boundary, "quality gate remediation plan boundary", 512)
        self.gate_id = _label(gate_id, "quality gate remediation plan gate ID")
        self.gate_address = _address(gate_address, "quality gate remediation plan gate address", gate_model.GATE_PREFIX)
        self.gate = gate if isinstance(gate, gate_model.DownloadedDataQualityDiffGate) else gate_model.gate_from_mapping(gate)
        self.actions = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationAction) else DownloadedDataQualityDiffGateRemediationAction.from_mapping(item) for item in _sequence(actions, "quality gate remediation actions", MAX_ACTIONS))
        for field in ("action_count", "none_count", "repair_count", "investigate_count", "policy_review_count", "data_review_count", "accept_count", "required_action_count", "critical_action_count"):
            setattr(self, field, _count(locals()[field], f"quality gate remediation {field}", MAX_ACTIONS))
        self.state = _label(state, "quality gate remediation state")
        if self.state not in STATES:
            raise ValidationError("quality gate remediation state is unsupported")
        self.decision = _label(decision, "quality gate remediation decision")
        if self.decision not in DECISIONS:
            raise ValidationError("quality gate remediation decision is unsupported")
        self.accepted = _bool(accepted, "quality gate remediation acceptance")
        self.content_address = _address(content_address, "quality gate remediation plan address", PLAN_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality gate remediation plan version or boundary is not current")
        if self.gate_id != self.gate.gate_id or self.gate_address != self.gate.content_address:
            raise ValidationError("quality gate remediation plan gate linkage does not replay")
        if len(self.actions) != self.action_count or tuple(item.ordinal for item in self.actions) != tuple(range(1, self.action_count + 1)):
            raise ValidationError("quality gate remediation action order is not conserved")
        expected = tuple(_action(item, item.ordinal, self.gate_address).to_dict() for item in self.gate.findings)
        if tuple(item.to_dict() for item in self.actions) != expected:
            raise ValidationError("quality gate remediation actions do not replay from the gate")
        counts = tuple(sum(item.action == action for item in self.actions) for action in ACTION_KINDS)
        if counts != (self.none_count, self.repair_count, self.investigate_count, self.policy_review_count, self.data_review_count, self.accept_count):
            raise ValidationError("quality gate remediation action counts do not replay")
        if self.required_action_count != sum(item.required for item in self.actions) or self.critical_action_count != sum(item.priority == "critical" for item in self.actions):
            raise ValidationError("quality gate remediation counters do not replay")
        expected_state = "blocked" if any(item.outcome == "blocked" for item in self.actions) else "review" if self.required_action_count else "clear"
        expected_decision = {"clear": "close", "review": "hold", "blocked": "block"}[expected_state]
        if self.state != expected_state or self.decision != expected_decision or self.accepted != (expected_state == "clear"):
            raise ValidationError("quality gate remediation disposition does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation plan crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_plan(self) != self.content_address:
            raise ValidationError("quality gate remediation plan address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id, "version": self.version, "boundary": self.boundary,
            "gate_id": self.gate_id, "gate_address": self.gate_address, "gate": self.gate.to_dict(),
            "actions": tuple(item.to_dict() for item in self.actions), "action_count": self.action_count,
            "none_count": self.none_count, "repair_count": self.repair_count,
            "investigate_count": self.investigate_count, "policy_review_count": self.policy_review_count,
            "data_review_count": self.data_review_count, "accept_count": self.accept_count,
            "required_action_count": self.required_action_count, "critical_action_count": self.critical_action_count,
            "state": self.state, "decision": self.decision, "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"gate", "actions"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationPlan":
        value = _mapping(value, "quality gate remediation plan")
        _strict(value, set(cls.FIELDS), "quality gate remediation plan")
        return cls(*(value[field] for field in cls.FIELDS))


def address_plan(value: DownloadedDataQualityDiffGateRemediationPlan) -> str:
    if not isinstance(value, DownloadedDataQualityDiffGateRemediationPlan):
        raise ValidationError("quality gate remediation plan address requires a typed plan")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PLAN_PREFIX)


def build_plan(gate: gate_model.DownloadedDataQualityDiffGate, *, plan_id: str = DEFAULT_PLAN_ID) -> DownloadedDataQualityDiffGateRemediationPlan:
    if not isinstance(gate, gate_model.DownloadedDataQualityDiffGate):
        raise ValidationError("quality gate remediation requires a typed gate")
    actions = tuple(_action(item, ordinal, gate.content_address) for ordinal, item in enumerate(gate.findings, 1))
    counts = tuple(sum(item.action == action for item in actions) for action in ACTION_KINDS)
    body = {
        "plan_id": plan_id, "version": VERSION, "boundary": BOUNDARY, "gate_id": gate.gate_id,
        "gate_address": gate.content_address, "gate": gate, "actions": actions, "action_count": len(actions),
        "none_count": counts[0], "repair_count": counts[1], "investigate_count": counts[2],
        "policy_review_count": counts[3], "data_review_count": counts[4], "accept_count": counts[5],
        "required_action_count": sum(item.required for item in actions),
        "critical_action_count": sum(item.priority == "critical" for item in actions),
    }
    expected_state = "blocked" if any(item.outcome == "blocked" for item in actions) else "review" if body["required_action_count"] else "clear"
    provisional = DownloadedDataQualityDiffGateRemediationPlan(**body, state=expected_state, decision={"clear": "close", "review": "hold", "blocked": "block"}[expected_state], accepted=expected_state == "clear", content_address=PLAN_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRemediationPlan(**body, state=provisional.state, decision=provisional.decision, accepted=provisional.accepted, content_address=address_plan(provisional))


def plan_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationPlan:
    return DownloadedDataQualityDiffGateRemediationPlan.from_mapping(value)


def remediation_json(value: DownloadedDataQualityDiffGateRemediationPlan) -> str:
    return canonical_json(plan_from_mapping(value.to_dict()).to_dict())


def remediation_csv(value: DownloadedDataQualityDiffGateRemediationPlan) -> str:
    value = plan_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ACTION_FIELDS)
    for item in value.actions:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field in {"reason_codes", "evidence_addresses"} else row[field] for field in ACTION_FIELDS)
    return stream.getvalue()


def render_remediation_markdown(value: DownloadedDataQualityDiffGateRemediationPlan) -> str:
    value = plan_from_mapping(value.to_dict())
    lines = [
        "# Downloaded Data Quality Diff Gate Remediation",
        "",
        f"- Plan: `{value.plan_id}`",
        f"- Gate: `{value.gate_address}`",
        f"- State / decision: `{value.state}` / `{value.decision}`",
        f"- Actions: `{value.action_count}` (`{value.required_action_count}` required, `{value.critical_action_count}` critical)",
        f"- Address: `{value.content_address}`",
        "",
        "| # | outcome | action | priority | required | identity | detail |",
        "| ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    lines.extend(f"| {item.ordinal} | `{item.outcome}` | `{item.action}` | `{item.priority}` | `{item.required}` | `{item.identity}` | {item.detail} |" for item in value.actions)
    return "\n".join(lines) + "\n"


def plan_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data quality diff gate remediation plan",
        "type": "object", "additionalProperties": False, "required": list(PLAN_FIELDS),
        "properties": {
            "plan_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY},
            "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "gate": {"type": "object"},
            "actions": {"type": "array", "maxItems": MAX_ACTIONS}, "action_count": {"type": "integer", "minimum": 0},
            "none_count": {"type": "integer", "minimum": 0}, "repair_count": {"type": "integer", "minimum": 0},
            "investigate_count": {"type": "integer", "minimum": 0}, "policy_review_count": {"type": "integer", "minimum": 0},
            "data_review_count": {"type": "integer", "minimum": 0}, "accept_count": {"type": "integer", "minimum": 0},
            "required_action_count": {"type": "integer", "minimum": 0}, "critical_action_count": {"type": "integer", "minimum": 0},
            "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"},
            "content_address": {"type": "string"},
        },
    }


def action_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data quality diff gate remediation action",
        "type": "object", "additionalProperties": False, "required": list(ACTION_FIELDS),
        "properties": {
            "ordinal": {"type": "integer", "minimum": 1}, "finding_address": {"type": "string"},
            "identity": {"type": "string"}, "change": {"type": "string"}, "direction": {"type": "string"},
            "outcome": {"type": "string"}, "reason_codes": {"type": "array", "items": {"type": "string"}},
            "action": {"enum": list(ACTION_KINDS)}, "priority": {"enum": list(PRIORITIES)},
            "required": {"type": "boolean"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
            "detail": {"type": "string"}, "content_address": {"type": "string"},
        },
    }


def capabilities() -> dict[str, Any]:
    return {
        "public": True, "independent": True, "value_free": True, "version": VERSION,
        "operations": ("build_plan", "plan_from_mapping", "remediation_json", "remediation_csv", "render_remediation_markdown"),
        "action_kinds": ACTION_KINDS, "priorities": PRIORITIES, "states": STATES, "decisions": DECISIONS,
        "limits": {"max_actions": MAX_ACTIONS},
    }


__all__ = [
    "ACTION_FIELDS", "ACTION_KINDS", "ACTION_PREFIX", "BOUNDARY", "DECISIONS", "DEFAULT_PLAN_ID",
    "MAX_ACTIONS", "PLAN_FIELDS", "PLAN_PREFIX", "PRIORITIES", "STATES", "VERSION",
    "DownloadedDataQualityDiffGateRemediationAction", "DownloadedDataQualityDiffGateRemediationPlan",
    "action_schema", "address_action", "address_plan", "build_plan", "capabilities", "plan_from_mapping",
    "plan_schema", "remediation_csv", "remediation_json", "render_remediation_markdown",
]
