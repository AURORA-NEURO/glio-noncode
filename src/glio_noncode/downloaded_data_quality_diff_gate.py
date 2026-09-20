"""Policy-governed release decisions over downloaded-data quality diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate"
GATE_PREFIX = "glio-noncode-download-quality-diff-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
FINDING_PREFIX = GATE_PREFIX + "-finding"
DEFAULT_POLICY_ID = POLICY_PREFIX
DEFAULT_GATE_ID = GATE_PREFIX
OUTCOMES = ("safe", "review", "blocked")
STATES = ("eligible", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
REASON_CODES = (
    "unchanged",
    "improved",
    "changed",
    "added",
    "removed",
    "regressed",
    "direction_not_allowed",
    "maximum_regressed_exceeded",
    "maximum_changed_exceeded",
    "maximum_added_exceeded",
    "maximum_removed_exceeded",
    "diff_audit_failed",
    "query_audit_failed",
    "query_truncated",
)
POLICY_FIELDS = (
    "policy_id",
    "allowed_directions",
    "maximum_regressed",
    "maximum_changed",
    "maximum_added",
    "maximum_removed",
    "require_diff_audit",
    "require_query_audit",
    "require_complete_query",
    "content_address",
)
FINDING_FIELDS = (
    "ordinal",
    "identity",
    "change",
    "direction",
    "outcome",
    "reason_codes",
    "left_address",
    "right_address",
    "diff_item_address",
    "content_address",
)
GATE_FIELDS = (
    "gate_id",
    "version",
    "boundary",
    "diff_id",
    "diff_address",
    "diff",
    "policy",
    "diff_audit_address",
    "diff_audit_accepted",
    "diff_query_address",
    "diff_query_audit_address",
    "diff_query_audit_accepted",
    "diff_query_truncated",
    "findings",
    "finding_count",
    "safe_count",
    "review_count",
    "blocked_count",
    "allowed_direction_count",
    "disallowed_direction_count",
    "state",
    "decision",
    "accepted",
    "content_address",
)
MAX_FINDINGS = diff_model.MAX_ITEMS


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


class DownloadedDataQualityDiffGatePolicy:
    """Explicit thresholds for promoting a quality-diff candidate."""

    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, allowed_directions: Sequence[str], maximum_regressed: int, maximum_changed: int, maximum_added: int, maximum_removed: int, require_diff_audit: bool, require_query_audit: bool, require_complete_query: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "quality diff gate policy ID")
        self.allowed_directions = _ordered_labels(allowed_directions, "quality diff gate allowed directions", diff_model.DIRECTIONS)
        self.maximum_regressed = _count(maximum_regressed, "maximum regressed quality findings", MAX_FINDINGS)
        self.maximum_changed = _count(maximum_changed, "maximum changed quality findings", MAX_FINDINGS)
        self.maximum_added = _count(maximum_added, "maximum added quality findings", MAX_FINDINGS)
        self.maximum_removed = _count(maximum_removed, "maximum removed quality findings", MAX_FINDINGS)
        self.require_diff_audit = _bool(require_diff_audit, "require quality diff audit")
        self.require_query_audit = _bool(require_query_audit, "require quality diff query audit")
        self.require_complete_query = _bool(require_complete_query, "require complete quality diff query")
        self.content_address = _address(content_address, "quality diff gate policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate policy crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("quality diff gate policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGatePolicy":
        value = _mapping(value, "downloaded data quality diff gate policy")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: DownloadedDataQualityDiffGatePolicy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_policy(*, policy_id: str = DEFAULT_POLICY_ID) -> DownloadedDataQualityDiffGatePolicy:
    provisional = DownloadedDataQualityDiffGatePolicy(policy_id, ("improved", "changed", "unchanged", "added", "removed"), 0, MAX_FINDINGS, MAX_FINDINGS, MAX_FINDINGS, True, True, True, POLICY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGatePolicy(provisional.policy_id, provisional.allowed_directions, provisional.maximum_regressed, provisional.maximum_changed, provisional.maximum_added, provisional.maximum_removed, provisional.require_diff_audit, provisional.require_query_audit, provisional.require_complete_query, address_policy(provisional))


class DownloadedDataQualityDiffGateFinding:
    """One policy classification for a quality-diff item."""

    FIELDS = FINDING_FIELDS

    def __init__(self, ordinal: int, identity: str, change: str, direction: str, outcome: str, reason_codes: Sequence[str], left_address: str, right_address: str, diff_item_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff gate finding ordinal", MAX_FINDINGS, positive=True)
        self.identity = _text(identity, "quality diff gate finding identity", 4096)
        self.change = _label(change, "quality diff gate finding change")
        if self.change not in diff_model.CHANGES:
            raise ValidationError("quality diff gate finding change is unsupported")
        self.direction = _label(direction, "quality diff gate finding direction")
        if self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("quality diff gate finding direction is unsupported")
        self.outcome = _label(outcome, "quality diff gate finding outcome")
        if self.outcome not in OUTCOMES:
            raise ValidationError("quality diff gate finding outcome is unsupported")
        self.reason_codes = _ordered_labels(reason_codes, "quality diff gate finding reason codes", REASON_CODES, empty=False)
        self.left_address = _address(left_address, "quality diff gate finding left address", optional=True)
        self.right_address = _address(right_address, "quality diff gate finding right address", optional=True)
        self.diff_item_address = _address(diff_item_address, "quality diff gate finding diff item address", diff_model.ITEM_PREFIX)
        self.content_address = _address(content_address, "quality diff gate finding address", FINDING_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_address or not self.right_address):
            raise ValidationError("added quality diff gate finding has invalid sides")
        if self.change == "removed" and (not self.left_address or self.right_address):
            raise ValidationError("removed quality diff gate finding has invalid sides")
        if self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address):
            raise ValidationError("paired quality diff gate finding is missing a side")
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate finding crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("quality diff gate finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateFinding":
        value = _mapping(value, "downloaded data quality diff gate finding")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: DownloadedDataQualityDiffGateFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def classify_item(item: diff_model.DownloadedDataQualityDiffItem, *, policy: DownloadedDataQualityDiffGatePolicy) -> tuple[str, tuple[str, ...]]:
    if not isinstance(item, diff_model.DownloadedDataQualityDiffItem) or not isinstance(policy, DownloadedDataQualityDiffGatePolicy):
        raise ValidationError("quality diff gate classification requires typed values")
    if item.direction in policy.allowed_directions:
        return "safe", (item.direction,)
    if item.direction == "regressed":
        return "blocked", (item.direction, "direction_not_allowed")
    return "review", (item.direction, "direction_not_allowed")


class DownloadedDataQualityDiffGate:
    """Fail-closed release decision over one quality diff."""

    FIELDS = GATE_FIELDS

    def __init__(self, gate_id: str, version: str, boundary: str, diff_id: str, diff_address: str, diff: diff_model.DownloadedDataQualityDiff | Mapping[str, Any], policy: DownloadedDataQualityDiffGatePolicy | Mapping[str, Any], diff_audit_address: str, diff_audit_accepted: bool, diff_query_address: str, diff_query_audit_address: str, diff_query_audit_accepted: bool, diff_query_truncated: bool, findings: Sequence[DownloadedDataQualityDiffGateFinding | Mapping[str, Any]], finding_count: int, safe_count: int, review_count: int, blocked_count: int, allowed_direction_count: int, disallowed_direction_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.gate_id = _label(gate_id, "quality diff gate ID")
        self.version = _text(version, "quality diff gate version")
        self.boundary = _text(boundary, "quality diff gate boundary", 512)
        self.diff_id = _label(diff_id, "quality diff gate diff ID")
        self.diff_address = _address(diff_address, "quality diff gate diff address", diff_model.DIFF_PREFIX)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataQualityDiff) else diff_model.diff_from_mapping(diff)
        self.policy = policy if isinstance(policy, DownloadedDataQualityDiffGatePolicy) else DownloadedDataQualityDiffGatePolicy.from_mapping(policy)
        self.diff_audit_address = _address(diff_audit_address, "quality diff gate diff audit address", "glio-noncode-download-quality-diff-audit")
        self.diff_audit_accepted = _bool(diff_audit_accepted, "quality diff gate diff audit acceptance")
        self.diff_query_address = _address(diff_query_address, "quality diff gate query address", "glio-noncode-download-quality-diff-query")
        self.diff_query_audit_address = _address(diff_query_audit_address, "quality diff gate query audit address", "glio-noncode-download-quality-diff-query-audit")
        self.diff_query_audit_accepted = _bool(diff_query_audit_accepted, "quality diff gate query audit acceptance")
        self.diff_query_truncated = _bool(diff_query_truncated, "quality diff gate query truncation")
        self.findings = tuple(item if isinstance(item, DownloadedDataQualityDiffGateFinding) else DownloadedDataQualityDiffGateFinding.from_mapping(item) for item in _sequence(findings, "quality diff gate findings", MAX_FINDINGS))
        for field in ("finding_count", "safe_count", "review_count", "blocked_count", "allowed_direction_count", "disallowed_direction_count"):
            setattr(self, field, _count(locals()[field], f"quality diff gate {field}", MAX_FINDINGS))
        self.state = _label(state, "quality diff gate state")
        self.decision = _label(decision, "quality diff gate decision")
        self.accepted = _bool(accepted, "quality diff gate acceptance")
        self.content_address = _address(content_address, "quality diff gate address", GATE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.state not in STATES or self.decision not in DECISIONS:
            raise ValidationError("quality diff gate version, boundary, or disposition is invalid")
        if self.diff_id != self.diff.diff_id or self.diff_address != self.diff.content_address:
            raise ValidationError("quality diff gate diff linkage does not replay")
        if len(self.findings) != self.finding_count or tuple(item.ordinal for item in self.findings) != tuple(range(1, self.finding_count + 1)):
            raise ValidationError("quality diff gate finding order is not conserved")
        counts = tuple(sum(item.outcome == outcome for item in self.findings) for outcome in OUTCOMES)
        if (self.safe_count, self.review_count, self.blocked_count) != counts or self.finding_count != sum(counts) or self.allowed_direction_count + self.disallowed_direction_count != self.finding_count:
            raise ValidationError("quality diff gate outcome counts are not conserved")
        expected_allowed = sum(item.direction in self.policy.allowed_directions for item in self.findings)
        if self.allowed_direction_count != expected_allowed:
            raise ValidationError("quality diff gate direction count does not replay")
        hard_failure = self.blocked_count > 0 or self.diff.regressed_count > self.policy.maximum_regressed or (self.policy.require_diff_audit and not self.diff_audit_accepted) or (self.policy.require_query_audit and not self.diff_query_audit_accepted)
        soft_failure = self.review_count > 0 or self.diff.changed_count > self.policy.maximum_changed or self.diff.added_count > self.policy.maximum_added or self.diff.removed_count > self.policy.maximum_removed or (self.policy.require_complete_query and self.diff_query_truncated)
        expected_state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
        expected_decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[expected_state]
        if self.state != expected_state or self.decision != expected_decision or self.accepted != (expected_state == "eligible"):
            raise ValidationError("quality diff gate disposition does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_gate(self) != self.content_address:
            raise ValidationError("quality diff gate address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "version": self.version, "boundary": self.boundary, "diff_id": self.diff_id, "diff_address": self.diff_address, "diff": self.diff.to_dict(), "policy": self.policy.to_dict(), "diff_audit_address": self.diff_audit_address, "diff_audit_accepted": self.diff_audit_accepted, "diff_query_address": self.diff_query_address, "diff_query_audit_address": self.diff_query_audit_address, "diff_query_audit_accepted": self.diff_query_audit_accepted, "diff_query_truncated": self.diff_query_truncated, "findings": tuple(item.to_dict() for item in self.findings), "finding_count": self.finding_count, "safe_count": self.safe_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "allowed_direction_count": self.allowed_direction_count, "disallowed_direction_count": self.disallowed_direction_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"diff", "policy", "findings"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGate":
        value = _mapping(value, "downloaded data quality diff gate")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate")
        return cls(*(value[field] for field in cls.FIELDS))


def address_gate(value: DownloadedDataQualityDiffGate) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def _finding(item: diff_model.DownloadedDataQualityDiffItem, ordinal: int, policy: DownloadedDataQualityDiffGatePolicy) -> DownloadedDataQualityDiffGateFinding:
    outcome, reasons = classify_item(item, policy=policy)
    body = {"ordinal": ordinal, "identity": item.identity, "change": item.change, "direction": item.direction, "outcome": outcome, "reason_codes": tuple(sorted(set(reasons), key=REASON_CODES.index)), "left_address": item.left_address, "right_address": item.right_address, "diff_item_address": item.content_address, "content_address": FINDING_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateFinding(**body)
    return DownloadedDataQualityDiffGateFinding(**(body | {"content_address": address_finding(provisional)}))


def evaluate(diff: diff_model.DownloadedDataQualityDiff, *, policy: DownloadedDataQualityDiffGatePolicy | None = None, gate_id: str = DEFAULT_GATE_ID) -> DownloadedDataQualityDiffGate:
    """Evaluate one quality diff with fresh audit and complete-query receipts."""

    if not isinstance(diff, diff_model.DownloadedDataQualityDiff):
        raise ValidationError("quality diff gate evaluation requires a typed diff")
    resolved_policy = default_policy() if policy is None else policy
    if not isinstance(resolved_policy, DownloadedDataQualityDiffGatePolicy):
        raise ValidationError("quality diff gate policy must be typed")
    from . import downloaded_data_quality_diff_audit as diff_audit_model
    from . import downloaded_data_quality_diff_query as diff_query_model
    from . import downloaded_data_quality_diff_query_audit as diff_query_audit_model

    diff_audit = diff_audit_model.audit_diff(diff)
    query_limit = min(diff_query_model.MAX_LIMIT, diff_query_model.MAX_TOTAL_COUNT)
    diff_query = diff_query_model.query_diff(diff, resources=("summary", "items"), limit=query_limit)
    diff_query_audit = diff_query_audit_model.audit_query(diff_query)
    findings = tuple(_finding(item, ordinal, resolved_policy) for ordinal, item in enumerate(diff.items, 1))
    counts = tuple(sum(item.outcome == outcome for item in findings) for outcome in OUTCOMES)
    allowed = sum(item.direction in resolved_policy.allowed_directions for item in findings)
    body = {"gate_id": gate_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": diff.diff_id, "diff_address": diff.content_address, "diff": diff, "policy": resolved_policy, "diff_audit_address": diff_audit.content_address, "diff_audit_accepted": diff_audit.accepted, "diff_query_address": diff_query.content_address, "diff_query_audit_address": diff_query_audit.content_address, "diff_query_audit_accepted": diff_query_audit.accepted, "diff_query_truncated": diff_query.truncated, "findings": findings, "finding_count": len(findings), "safe_count": counts[0], "review_count": counts[1], "blocked_count": counts[2], "allowed_direction_count": allowed, "disallowed_direction_count": len(findings) - allowed}
    hard_failure = counts[2] > 0 or diff.regressed_count > resolved_policy.maximum_regressed or (resolved_policy.require_diff_audit and not diff_audit.accepted) or (resolved_policy.require_query_audit and not diff_query_audit.accepted)
    soft_failure = counts[1] > 0 or diff.changed_count > resolved_policy.maximum_changed or diff.added_count > resolved_policy.maximum_added or diff.removed_count > resolved_policy.maximum_removed or (resolved_policy.require_complete_query and diff_query.truncated)
    state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
    decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[state]
    provisional = DownloadedDataQualityDiffGate(**body, state=state, decision=decision, accepted=state == "eligible", content_address=GATE_PREFIX + ":pending")
    return DownloadedDataQualityDiffGate(**body, state=state, decision=decision, accepted=state == "eligible", content_address=address_gate(provisional))


def gate_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGate:
    return DownloadedDataQualityDiffGate.from_mapping(value)


def policy_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGatePolicy:
    return DownloadedDataQualityDiffGatePolicy.from_mapping(value)


def gate_json(value: DownloadedDataQualityDiffGate) -> str:
    return canonical_json(DownloadedDataQualityDiffGate.from_mapping(value.to_dict()).to_dict())


def policy_json(value: DownloadedDataQualityDiffGatePolicy) -> str:
    return canonical_json(DownloadedDataQualityDiffGatePolicy.from_mapping(value.to_dict()).to_dict())


def gate_csv(value: DownloadedDataQualityDiffGate) -> str:
    value = DownloadedDataQualityDiffGate.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FINDING_FIELDS)
    writer.writerows(tuple(";".join(item.reason_codes) if field == "reason_codes" else item.to_dict()[field] for field in FINDING_FIELDS) for item in value.findings)
    return stream.getvalue()


def render_gate_markdown(value: DownloadedDataQualityDiffGate) -> str:
    value = DownloadedDataQualityDiffGate.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate", "", f"- Decision: `{value.decision}`", f"- State: `{value.state}`", f"- Findings: `{value.finding_count}`", f"- Safe / review / blocked: `{value.safe_count} / {value.review_count} / {value.blocked_count}`", f"- Regressed: `{value.diff.regressed_count}`", f"- Diff: `{value.diff_address}`", f"- Policy: `{value.policy.content_address}`", f"- Address: `{value.content_address}`", "", "| # | identity | direction | outcome | reasons |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.identity}` | `{item.direction}` | `{item.outcome}` | {', '.join(item.reason_codes)} |" for item in value.findings)
    return "\n".join(lines) + "\n"


def finding_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate finding", "type": "object", "additionalProperties": False, "required": list(FINDING_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "change": {"enum": list(diff_model.CHANGES)}, "direction": {"enum": list(diff_model.DIRECTIONS)}, "outcome": {"enum": list(OUTCOMES)}, "reason_codes": {"type": "array", "items": {"enum": list(REASON_CODES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "diff_item_address": {"type": "string"}, "content_address": {"type": "string"}}}


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {"policy_id": {"type": "string"}, "allowed_directions": {"type": "array", "items": {"enum": list(diff_model.DIRECTIONS)}}, "maximum_regressed": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "maximum_changed": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "maximum_added": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "maximum_removed": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "require_diff_audit": {"type": "boolean"}, "require_query_audit": {"type": "boolean"}, "require_complete_query": {"type": "boolean"}, "content_address": {"type": "string"}}}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate", "type": "object", "additionalProperties": False, "required": list(GATE_FIELDS), "properties": {"gate_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "diff": diff_model.diff_schema(), "policy": policy_schema(), "diff_audit_address": {"type": "string"}, "diff_audit_accepted": {"type": "boolean"}, "diff_query_address": {"type": "string"}, "diff_query_audit_address": {"type": "string"}, "diff_query_audit_accepted": {"type": "boolean"}, "diff_query_truncated": {"type": "boolean"}, "findings": {"type": "array", "items": finding_schema(), "maxItems": MAX_FINDINGS}, "finding_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "safe_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "review_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "blocked_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "allowed_direction_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "disallowed_direction_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "outcomes": OUTCOMES, "states": STATES, "decisions": DECISIONS, "directions": diff_model.DIRECTIONS, "reason_codes": REASON_CODES, "operations": ("default_policy", "classify_item", "evaluate", "gate_from_mapping", "policy_from_mapping", "gate_json", "policy_json", "gate_csv", "render_gate_markdown"), "limits": {"max_findings": MAX_FINDINGS}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_GATE_ID", "DEFAULT_POLICY_ID", "FINDING_FIELDS", "FINDING_PREFIX", "GATE_FIELDS", "GATE_PREFIX", "MAX_FINDINGS", "OUTCOMES", "POLICY_FIELDS", "POLICY_PREFIX", "REASON_CODES", "STATES", "VERSION", "DownloadedDataQualityDiffGate", "DownloadedDataQualityDiffGateFinding", "DownloadedDataQualityDiffGatePolicy", "address_finding", "address_gate", "address_policy", "capabilities", "classify_item", "default_policy", "evaluate", "finding_schema", "gate_csv", "gate_from_mapping", "gate_json", "gate_schema", "policy_from_mapping", "policy_json", "policy_schema", "render_gate_markdown"]
