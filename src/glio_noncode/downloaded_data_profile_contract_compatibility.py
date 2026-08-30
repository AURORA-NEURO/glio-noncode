"""Value-free compatibility policy and release gate for contract diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility"
COMPATIBILITY_PREFIX = "glio-noncode-download-profile-contract-compatibility"
POLICY_PREFIX = COMPATIBILITY_PREFIX + "-policy"
FINDING_PREFIX = COMPATIBILITY_PREFIX + "-finding"
GATE_PREFIX = COMPATIBILITY_PREFIX + "-gate"
DEFAULT_POLICY_ID = COMPATIBILITY_PREFIX + "-policy"
DEFAULT_GATE_ID = COMPATIBILITY_PREFIX + "-gate"
OUTCOMES = ("safe", "review", "breaking")
STATES = ("eligible", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
REASON_CODES = (
    "field_added_optional",
    "field_added_required",
    "field_removed_optional",
    "field_removed_required",
    "field_type_changed",
    "field_coverage_changed",
    "field_requiredness_changed",
    "member_added",
    "member_removed",
    "member_shape_changed",
    "member_coverage_changed",
    "type_distribution_changed",
    "resource_not_allowed",
    "unchanged",
)
POLICY_FIELDS = (
    "policy_id",
    "allowed_outcomes",
    "maximum_review_findings",
    "maximum_breaking_findings",
    "allowed_resources",
    "require_diff_audit",
    "require_diff_query_audit",
    "require_complete_diff_query",
    "content_address",
)
FINDING_FIELDS = (
    "ordinal",
    "resource",
    "identity",
    "change",
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
    "breaking_count",
    "allowed_outcome_count",
    "disallowed_outcome_count",
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


class DownloadedDataProfileContractCompatibilityPolicy:
    """Explicit structural thresholds for a contract-diff release decision."""

    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, allowed_outcomes: Sequence[str], maximum_review_findings: int, maximum_breaking_findings: int, allowed_resources: Sequence[str], require_diff_audit: bool, require_diff_query_audit: bool, require_complete_diff_query: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "compatibility policy ID")
        self.allowed_outcomes = _ordered_labels(allowed_outcomes, "compatibility allowed outcomes", OUTCOMES)
        self.maximum_review_findings = _count(maximum_review_findings, "maximum review findings", MAX_FINDINGS)
        self.maximum_breaking_findings = _count(maximum_breaking_findings, "maximum breaking findings", MAX_FINDINGS)
        self.allowed_resources = _ordered_labels(allowed_resources, "compatibility allowed resources", diff_model.RESOURCES)
        self.require_diff_audit = _bool(require_diff_audit, "require diff audit")
        self.require_diff_query_audit = _bool(require_diff_query_audit, "require diff query audit")
        self.require_complete_diff_query = _bool(require_complete_diff_query, "require complete diff query")
        self.content_address = _address(content_address, "compatibility policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("compatibility policy crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("compatibility policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityPolicy:
        value = _mapping(value, "compatibility policy")
        _strict(value, set(cls.FIELDS), "compatibility policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: DownloadedDataProfileContractCompatibilityPolicy) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityPolicy):
        raise ValidationError("compatibility policy address requires a typed policy")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_policy(*, policy_id: str = DEFAULT_POLICY_ID) -> DownloadedDataProfileContractCompatibilityPolicy:
    provisional = DownloadedDataProfileContractCompatibilityPolicy(policy_id, ("safe", "review"), MAX_FINDINGS, 0, diff_model.RESOURCES, True, True, False, POLICY_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityPolicy(provisional.policy_id, provisional.allowed_outcomes, provisional.maximum_review_findings, provisional.maximum_breaking_findings, provisional.allowed_resources, provisional.require_diff_audit, provisional.require_diff_query_audit, provisional.require_complete_diff_query, address_policy(provisional))


class DownloadedDataProfileContractCompatibilityFinding:
    """One value-free compatibility classification for a diff item."""

    FIELDS = FINDING_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, outcome: str, reason_codes: Sequence[str], left_address: str, right_address: str, diff_item_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "compatibility finding ordinal", MAX_FINDINGS, positive=True)
        self.resource = _label(resource, "compatibility finding resource")
        if self.resource not in diff_model.RESOURCES:
            raise ValidationError("compatibility finding resource is unsupported")
        self.identity = _text(identity, "compatibility finding identity", 4096)
        self.change = _label(change, "compatibility finding change")
        if self.change not in diff_model.CHANGES:
            raise ValidationError("compatibility finding change is unsupported")
        self.outcome = _label(outcome, "compatibility finding outcome")
        if self.outcome not in OUTCOMES:
            raise ValidationError("compatibility finding outcome is unsupported")
        self.reason_codes = _ordered_labels(reason_codes, "compatibility finding reason codes", REASON_CODES, empty=True)
        self.left_address = _address(left_address, "compatibility finding left address", optional=True)
        self.right_address = _address(right_address, "compatibility finding right address", optional=True)
        self.diff_item_address = _address(diff_item_address, "compatibility finding diff item address", diff_model.ITEM_PREFIX)
        self.content_address = _address(content_address, "compatibility finding address", FINDING_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.outcome == "safe" and not self.reason_codes:
            raise ValidationError("safe compatibility findings require a reason")
        if self.outcome != "safe" and not self.reason_codes:
            raise ValidationError("non-safe compatibility findings require reasons")
        if self.change == "added" and (self.left_address or not self.right_address):
            raise ValidationError("added compatibility finding has invalid sides")
        if self.change == "removed" and (not self.left_address or self.right_address):
            raise ValidationError("removed compatibility finding has invalid sides")
        if self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address):
            raise ValidationError("paired compatibility finding is missing a side")
        if self.change == "unchanged" and self.outcome != "safe":
            raise ValidationError("unchanged compatibility finding must be safe")
        if not _public(self.to_dict()):
            raise ValidationError("compatibility finding crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("compatibility finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityFinding:
        value = _mapping(value, "compatibility finding")
        _strict(value, set(cls.FIELDS), "compatibility finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: DownloadedDataProfileContractCompatibilityFinding) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityFinding):
        raise ValidationError("compatibility finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def _snapshot(item: diff_model.DownloadedDataProfileContractDiffItem, side: str) -> Mapping[str, Any]:
    return item.left_snapshot if side == "left" else item.right_snapshot


def _classification(item: diff_model.DownloadedDataProfileContractDiffItem) -> tuple[str, tuple[str, ...]]:
    """Classify only structural metadata; source values are never inspected."""

    if item.change == "unchanged":
        return "safe", ("unchanged",)
    left = _snapshot(item, "left")
    right = _snapshot(item, "right")
    reasons: list[str] = []
    outcome = "safe"
    if item.resource == "fields":
        if item.change == "added":
            outcome = "safe" if not bool(right.get("required")) else "breaking"
            reasons.append("field_added_optional" if outcome == "safe" else "field_added_required")
        elif item.change == "removed":
            outcome = "review" if not bool(left.get("required")) else "breaking"
            reasons.append("field_removed_optional" if outcome == "review" else "field_removed_required")
        else:
            changed = set(item.changed_attributes)
            if {"dominant_value_type", "type_counts", "type_consistent"}.intersection(changed):
                outcome = "breaking"
                reasons.append("field_type_changed")
            if "required" in changed:
                if bool(right.get("required")) and not bool(left.get("required")):
                    outcome = "breaking"
                    reasons.append("field_requiredness_changed")
                elif "field_requiredness_changed" not in reasons:
                    outcome = max(outcome, "review", key=OUTCOMES.index)
                    reasons.append("field_requiredness_changed")
            if {"observed_count", "missing_count", "member_count", "state", "member_addresses"}.intersection(changed):
                outcome = max(outcome, "review", key=OUTCOMES.index)
                reasons.append("field_coverage_changed")
            if not reasons:
                outcome = "review"
                reasons.append("field_coverage_changed")
    elif item.resource == "members":
        if item.change == "added":
            outcome, reasons = "review", ["member_added"]
        elif item.change == "removed":
            outcome, reasons = "breaking", ["member_removed"]
        else:
            changed = set(item.changed_attributes)
            if {"data_kind", "field_names", "required_field_names", "mixed_type_field_names"}.intersection(changed):
                outcome = "breaking"
                reasons.append("member_shape_changed")
            if {"record_count", "member_name", "member_ordinal"}.intersection(changed):
                outcome = max(outcome, "review", key=OUTCOMES.index)
                reasons.append("member_coverage_changed")
            if not reasons:
                outcome, reasons = "review", ["member_coverage_changed"]
    else:
        outcome, reasons = "review", ["type_distribution_changed"]
    return outcome, tuple(dict.fromkeys(reasons))


def classify_item(item: diff_model.DownloadedDataProfileContractDiffItem, *, allowed_resources: Sequence[str] = diff_model.RESOURCES) -> tuple[str, tuple[str, ...]]:
    if not isinstance(item, diff_model.DownloadedDataProfileContractDiffItem):
        raise ValidationError("compatibility classification requires a typed diff item")
    if item.resource not in tuple(allowed_resources):
        return "breaking", ("resource_not_allowed",)
    return _classification(item)


def _finding(item: diff_model.DownloadedDataProfileContractDiffItem, ordinal: int, allowed_resources: Sequence[str]) -> DownloadedDataProfileContractCompatibilityFinding:
    outcome, reasons = classify_item(item, allowed_resources=allowed_resources)
    reasons = tuple(sorted(set(reasons), key=REASON_CODES.index))
    body = {"ordinal": ordinal, "resource": item.resource, "identity": item.identity, "change": item.change, "outcome": outcome, "reason_codes": reasons, "left_address": item.left_address, "right_address": item.right_address, "diff_item_address": item.content_address, "content_address": FINDING_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityFinding(**body)
    return DownloadedDataProfileContractCompatibilityFinding(**(body | {"content_address": address_finding(provisional)}))


class DownloadedDataProfileContractCompatibilityGate:
    """Fail-closed compatibility decision over one verified contract diff."""

    FIELDS = GATE_FIELDS

    def __init__(self, gate_id: str, version: str, boundary: str, diff_id: str, diff_address: str, diff: diff_model.DownloadedDataProfileContractDiff | Mapping[str, Any], policy: DownloadedDataProfileContractCompatibilityPolicy | Mapping[str, Any], diff_audit_address: str, diff_audit_accepted: bool, diff_query_address: str, diff_query_audit_address: str, diff_query_audit_accepted: bool, diff_query_truncated: bool, findings: Sequence[DownloadedDataProfileContractCompatibilityFinding | Mapping[str, Any]], finding_count: int, safe_count: int, review_count: int, breaking_count: int, allowed_outcome_count: int, disallowed_outcome_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.gate_id = _label(gate_id, "compatibility gate ID")
        self.version = _text(version, "compatibility gate version")
        self.boundary = _text(boundary, "compatibility gate boundary", 512)
        self.diff_id = _label(diff_id, "compatibility gate diff ID")
        self.diff_address = _address(diff_address, "compatibility gate diff address", diff_model.DIFF_PREFIX)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataProfileContractDiff) else diff_model.diff_from_mapping(diff)
        self.policy = policy if isinstance(policy, DownloadedDataProfileContractCompatibilityPolicy) else DownloadedDataProfileContractCompatibilityPolicy.from_mapping(policy)
        self.diff_audit_address = _address(diff_audit_address, "compatibility diff audit address", "glio-noncode-download-profile-contract-diff-audit")
        self.diff_audit_accepted = _bool(diff_audit_accepted, "compatibility diff audit acceptance")
        self.diff_query_address = _address(diff_query_address, "compatibility diff query address", "glio-noncode-download-profile-contract-diff-query")
        self.diff_query_audit_address = _address(diff_query_audit_address, "compatibility diff query audit address", "glio-noncode-download-profile-contract-diff-query-audit")
        self.diff_query_audit_accepted = _bool(diff_query_audit_accepted, "compatibility diff query audit acceptance")
        self.diff_query_truncated = _bool(diff_query_truncated, "compatibility diff query truncation")
        self.findings = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityFinding) else DownloadedDataProfileContractCompatibilityFinding.from_mapping(item) for item in _sequence(findings, "compatibility findings", MAX_FINDINGS))
        self.finding_count = _count(finding_count, "compatibility finding count", MAX_FINDINGS)
        self.safe_count = _count(safe_count, "compatibility safe count", MAX_FINDINGS)
        self.review_count = _count(review_count, "compatibility review count", MAX_FINDINGS)
        self.breaking_count = _count(breaking_count, "compatibility breaking count", MAX_FINDINGS)
        self.allowed_outcome_count = _count(allowed_outcome_count, "compatibility allowed outcome count", MAX_FINDINGS)
        self.disallowed_outcome_count = _count(disallowed_outcome_count, "compatibility disallowed outcome count", MAX_FINDINGS)
        self.state = _label(state, "compatibility gate state")
        self.decision = _label(decision, "compatibility gate decision")
        self.accepted = _bool(accepted, "compatibility gate acceptance")
        self.content_address = _address(content_address, "compatibility gate address", GATE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.state not in STATES or self.decision not in DECISIONS:
            raise ValidationError("compatibility gate version, boundary, or disposition is invalid")
        if self.diff_id != self.diff.diff_id or self.diff_address != self.diff.content_address:
            raise ValidationError("compatibility gate diff linkage does not replay")
        if len(self.findings) != self.finding_count or tuple(item.ordinal for item in self.findings) != tuple(range(1, self.finding_count + 1)):
            raise ValidationError("compatibility finding order is not conserved")
        counts = tuple(sum(item.outcome == outcome for item in self.findings) for outcome in OUTCOMES)
        if (self.safe_count, self.review_count, self.breaking_count) != counts or self.finding_count != sum(counts) or self.allowed_outcome_count + self.disallowed_outcome_count != self.finding_count:
            raise ValidationError("compatibility outcome counts are not conserved")
        expected_allowed = sum(item.outcome in self.policy.allowed_outcomes for item in self.findings)
        if self.allowed_outcome_count != expected_allowed:
            raise ValidationError("compatibility policy outcome count does not replay")
        hard_failure = self.breaking_count > self.policy.maximum_breaking_findings or any(item.outcome == "breaking" and item.outcome not in self.policy.allowed_outcomes for item in self.findings) or (self.policy.require_diff_audit and not self.diff_audit_accepted) or (self.policy.require_diff_query_audit and not self.diff_query_audit_accepted)
        soft_failure = self.review_count > self.policy.maximum_review_findings or any(item.outcome == "review" and item.outcome not in self.policy.allowed_outcomes for item in self.findings) or (self.policy.require_complete_diff_query and self.diff_query_truncated)
        expected_state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
        expected_decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[expected_state]
        if self.state != expected_state or self.decision != expected_decision or self.accepted != (expected_state == "eligible"):
            raise ValidationError("compatibility gate disposition does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("compatibility gate crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_gate(self) != self.content_address:
            raise ValidationError("compatibility gate address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "version": self.version, "boundary": self.boundary, "diff_id": self.diff_id, "diff_address": self.diff_address, "diff": self.diff.to_dict(), "policy": self.policy.to_dict(), "diff_audit_address": self.diff_audit_address, "diff_audit_accepted": self.diff_audit_accepted, "diff_query_address": self.diff_query_address, "diff_query_audit_address": self.diff_query_audit_address, "diff_query_audit_accepted": self.diff_query_audit_accepted, "diff_query_truncated": self.diff_query_truncated, "findings": tuple(item.to_dict() for item in self.findings), "finding_count": self.finding_count, "safe_count": self.safe_count, "review_count": self.review_count, "breaking_count": self.breaking_count, "allowed_outcome_count": self.allowed_outcome_count, "disallowed_outcome_count": self.disallowed_outcome_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"diff", "policy", "findings"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityGate:
        value = _mapping(value, "compatibility gate")
        _strict(value, set(cls.FIELDS), "compatibility gate")
        return cls(*(value[field] for field in cls.FIELDS))


def address_gate(value: DownloadedDataProfileContractCompatibilityGate) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityGate):
        raise ValidationError("compatibility gate address requires a typed gate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def evaluate(diff: diff_model.DownloadedDataProfileContractDiff, *, policy: DownloadedDataProfileContractCompatibilityPolicy | None = None, gate_id: str = DEFAULT_GATE_ID) -> DownloadedDataProfileContractCompatibilityGate:
    """Evaluate a contract diff with independently generated source receipts."""

    if not isinstance(diff, diff_model.DownloadedDataProfileContractDiff):
        raise ValidationError("compatibility evaluation requires a typed contract diff")
    policy = default_policy() if policy is None else policy
    if not isinstance(policy, DownloadedDataProfileContractCompatibilityPolicy):
        raise ValidationError("compatibility policy must be typed")
    from . import downloaded_data_profile_contract_diff_audit as diff_audit_model
    from . import downloaded_data_profile_contract_diff_query as diff_query_model
    from . import downloaded_data_profile_contract_diff_query_audit as diff_query_audit_model

    diff_audit = diff_audit_model.audit_diff(diff)
    query_limit = min(diff_query_model.MAX_LIMIT, diff_query_model.MAX_TOTAL_COUNT)
    diff_query = diff_query_model.query_diff(diff, resources=diff_query_model.RESOURCES, limit=query_limit)
    diff_query_audit = diff_query_audit_model.audit_query(diff_query)
    findings = tuple(_finding(item, ordinal, policy.allowed_resources) for ordinal, item in enumerate(diff.items, 1))
    counts = tuple(sum(item.outcome == outcome for item in findings) for outcome in OUTCOMES)
    allowed = sum(item.outcome in policy.allowed_outcomes for item in findings)
    body = {"gate_id": gate_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": diff.diff_id, "diff_address": diff.content_address, "diff": diff, "policy": policy, "diff_audit_address": diff_audit.content_address, "diff_audit_accepted": diff_audit.accepted, "diff_query_address": diff_query.content_address, "diff_query_audit_address": diff_query_audit.content_address, "diff_query_audit_accepted": diff_query_audit.accepted, "diff_query_truncated": diff_query.truncated, "findings": findings, "finding_count": len(findings), "safe_count": counts[0], "review_count": counts[1], "breaking_count": counts[2], "allowed_outcome_count": allowed, "disallowed_outcome_count": len(findings) - allowed}
    hard_failure = counts[2] > policy.maximum_breaking_findings or any(item.outcome == "breaking" and item.outcome not in policy.allowed_outcomes for item in findings) or (policy.require_diff_audit and not diff_audit.accepted) or (policy.require_diff_query_audit and not diff_query_audit.accepted)
    soft_failure = counts[1] > policy.maximum_review_findings or any(item.outcome == "review" and item.outcome not in policy.allowed_outcomes for item in findings) or (policy.require_complete_diff_query and diff_query.truncated)
    state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
    decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[state]
    final = DownloadedDataProfileContractCompatibilityGate(**body, state=state, decision=decision, accepted=state == "eligible", content_address=GATE_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityGate(**body, state=state, decision=decision, accepted=state == "eligible", content_address=address_gate(final))


def compatibility_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityGate:
    return DownloadedDataProfileContractCompatibilityGate.from_mapping(value)


def compatibility_json(value: DownloadedDataProfileContractCompatibilityGate) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityGate.from_mapping(value.to_dict()).to_dict())


def compatibility_csv(value: DownloadedDataProfileContractCompatibilityGate) -> str:
    value = DownloadedDataProfileContractCompatibilityGate.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FINDING_FIELDS)
    writer.writerows(tuple(";".join(item.reason_codes) if field == "reason_codes" else item.to_dict()[field] for field in FINDING_FIELDS) for item in value.findings)
    return stream.getvalue()


def render_compatibility_markdown(value: DownloadedDataProfileContractCompatibilityGate) -> str:
    value = DownloadedDataProfileContractCompatibilityGate.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility", "", f"- Decision: `{value.decision}`", f"- State: `{value.state}`", f"- Findings: `{value.finding_count}`", f"- Safe / review / breaking: `{value.safe_count} / {value.review_count} / {value.breaking_count}`", f"- Diff: `{value.diff_address}`", f"- Policy: `{value.policy.content_address}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | change | outcome | reasons |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.identity}` | `{item.change}` | `{item.outcome}` | {', '.join(item.reason_codes)} |" for item in value.findings)
    return "\n".join(lines) + "\n"


def finding_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility finding", "type": "object", "additionalProperties": False, "required": list(FINDING_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(diff_model.RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": list(diff_model.CHANGES)}, "outcome": {"enum": list(OUTCOMES)}, "reason_codes": {"type": "array", "items": {"enum": list(REASON_CODES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "diff_item_address": {"type": "string"}, "content_address": {"type": "string"}}}


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {"policy_id": {"type": "string"}, "allowed_outcomes": {"type": "array", "items": {"enum": list(OUTCOMES)}}, "maximum_review_findings": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "maximum_breaking_findings": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "allowed_resources": {"type": "array", "items": {"enum": list(diff_model.RESOURCES)}}, "require_diff_audit": {"type": "boolean"}, "require_diff_query_audit": {"type": "boolean"}, "require_complete_diff_query": {"type": "boolean"}, "content_address": {"type": "string"}}}


def compatibility_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility gate", "type": "object", "additionalProperties": False, "required": list(GATE_FIELDS), "properties": {"gate_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "diff": diff_model.diff_schema(), "policy": policy_schema(), "diff_audit_address": {"type": "string"}, "diff_audit_accepted": {"type": "boolean"}, "diff_query_address": {"type": "string"}, "diff_query_audit_address": {"type": "string"}, "diff_query_audit_accepted": {"type": "boolean"}, "diff_query_truncated": {"type": "boolean"}, "findings": {"type": "array", "items": finding_schema(), "maxItems": MAX_FINDINGS}, "finding_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "safe_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "review_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "breaking_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "allowed_outcome_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "disallowed_outcome_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "outcomes": OUTCOMES, "states": STATES, "decisions": DECISIONS, "reason_codes": REASON_CODES, "operations": ("default_policy", "classify_item", "evaluate", "compatibility_from_mapping", "compatibility_json", "compatibility_csv", "render_compatibility_markdown"), "limits": {"max_findings": MAX_FINDINGS}}


__all__ = ["BOUNDARY", "COMPATIBILITY_PREFIX", "DECISIONS", "DEFAULT_GATE_ID", "DEFAULT_POLICY_ID", "FINDING_FIELDS", "FINDING_PREFIX", "GATE_FIELDS", "GATE_PREFIX", "MAX_FINDINGS", "OUTCOMES", "POLICY_FIELDS", "POLICY_PREFIX", "REASON_CODES", "STATES", "VERSION", "DownloadedDataProfileContractCompatibilityFinding", "DownloadedDataProfileContractCompatibilityGate", "DownloadedDataProfileContractCompatibilityPolicy", "address_finding", "address_gate", "address_policy", "capabilities", "classify_item", "compatibility_csv", "compatibility_from_mapping", "compatibility_json", "compatibility_schema", "default_policy", "evaluate", "finding_schema", "policy_schema", "render_compatibility_markdown"]
